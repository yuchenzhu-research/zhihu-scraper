import io
import tempfile
import unittest
from http.client import IncompleteRead
from pathlib import Path
from socket import AF_INET, SOCK_STREAM
from unittest.mock import patch
from urllib.request import HTTPRedirectHandler, Request

from zhihu_scraper.media import (
    MediaCandidate,
    MediaDownloadError,
    download_media,
    select_highest_resolution,
)


class FakeHttpResponse:
    def __init__(self, *, status: int, body: bytes, headers: dict[str, str]):
        self.status = status
        self.headers = headers
        self._body = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._body.close()

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


class InterruptingHttpResponse(FakeHttpResponse):
    def __init__(
        self,
        *,
        first_chunk: bytes,
        expected_total: int,
        failure: BaseException | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            status=200,
            body=first_chunk,
            headers={"Content-Length": str(expected_total), **(headers or {})},
        )
        self._read_count = 0
        self._failure = failure or ConnectionError("connection interrupted")

    def read(self, size: int = -1) -> bytes:
        self._read_count += 1
        if self._read_count == 1:
            return super().read(size)
        raise self._failure


class RecordingTransport:
    def __init__(self, response: FakeHttpResponse):
        self.response = response
        self.requests: list[Request] = []

    def __call__(self, request: Request):
        self.requests.append(request)
        return self.response


class RecordingOpener:
    def __init__(self, response: FakeHttpResponse):
        self.response = response
        self.requests: list[Request] = []
        self.timeouts: list[float | None] = []

    def open(self, request: Request, *, timeout: float | None = None):
        self.requests.append(request)
        self.timeouts.append(timeout)
        return self.response


class SequencedTransport:
    def __init__(self, *responses: FakeHttpResponse):
        self.responses = list(responses)
        self.requests: list[Request] = []

    def __call__(self, request: Request):
        self.requests.append(request)
        return self.responses.pop(0)


class MediaQualitySelectionTests(unittest.TestCase):
    def test_selects_highest_resolution_and_keeps_the_first_exact_tie(self):
        first_full_hd = MediaCandidate(
            source_url="https://media.example/first-1080p.mp4",
            width=1920,
            height=1080,
        )
        candidates = (
            MediaCandidate(
                source_url="https://media.example/720p.mp4",
                width=1280,
                height=720,
            ),
            first_full_hd,
            MediaCandidate(
                source_url="https://media.example/second-1080p.mp4",
                width=1920,
                height=1080,
            ),
        )

        self.assertIs(select_highest_resolution(candidates), first_full_hd)


class ResumableMediaDownloadTests(unittest.TestCase):
    def setUp(self):
        self.public_dns = patch(
            "zhihu_scraper.media.getaddrinfo",
            return_value=[
                (
                    AF_INET,
                    SOCK_STREAM,
                    6,
                    "",
                    ("93.184.216.34", 443),
                )
            ],
        )
        self.public_dns.start()
        self.addCleanup(self.public_dns.stop)

    def _interrupt_download(self, destination, *, headers, source_url=None):
        with self.assertRaises(MediaDownloadError):
            download_media(
                source_url or "https://media.example/video.mp4",
                destination,
                transport=RecordingTransport(
                    InterruptingHttpResponse(
                        first_chunk=b"hello", expected_total=11, headers=headers
                    )
                ),
                max_retries=0,
            )

    def test_matching_known_size_reuses_the_file_without_network(self):
        transport = SequencedTransport()
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "image.jpg"
            destination.write_bytes(b"complete")

            receipt = download_media(
                "https://media.example/image.jpg", destination, expected_size=8, transport=transport
            )

            self.assertEqual(receipt.bytes_total, 8)
            self.assertEqual(transport.requests, [])

    def test_known_size_replaces_an_existing_truncated_file_without_a_head_request(self):
        transport = RecordingTransport(
            FakeHttpResponse(status=200, body=b"complete", headers={"Content-Length": "8"})
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "image.jpg"
            destination.write_bytes(b"bad")

            receipt = download_media(
                "https://media.example/image.jpg", destination, expected_size=8, transport=transport
            )

            self.assertEqual(destination.read_bytes(), b"complete")
            self.assertEqual(receipt.bytes_total, 8)
            self.assertEqual([request.get_method() for request in transport.requests], ["GET"])

    def test_response_must_match_the_known_size_even_without_content_length(self):
        transport = RecordingTransport(FakeHttpResponse(status=200, body=b"short", headers={}))
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "image.jpg"
            with self.assertRaises(MediaDownloadError):
                download_media(
                    "https://media.example/image.jpg",
                    destination,
                    expected_size=8,
                    transport=transport,
                    max_retries=0,
                )
            self.assertFalse(destination.exists())

    def test_known_size_rejects_invalid_values_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "new" / "image.jpg"
            for expected_size in (0, -1, True, 1.5):
                with self.subTest(expected_size=expected_size), self.assertRaises(ValueError):
                    download_media(
                        "https://media.example/image.jpg", destination, expected_size=expected_size
                    )
            self.assertFalse(destination.parent.exists())

    def test_persisted_etag_guards_resume_after_a_signed_url_refresh(self):
        transport = SequencedTransport(
            InterruptingHttpResponse(
                first_chunk=b"hello", expected_total=11, headers={"ETag": '"version-1"'}
            ),
            FakeHttpResponse(
                status=206,
                body=b" world",
                headers={
                    "Content-Length": "6",
                    "Content-Range": "bytes 5-10/11",
                    "ETag": '"version-1"',
                },
            ),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            with self.assertRaises(MediaDownloadError):
                download_media(
                    "https://media.example/video.mp4?pkey=old&expiration=1",
                    destination,
                    transport=transport,
                    max_retries=0,
                )

            receipt = download_media(
                "https://media.example/video.mp4?pkey=new&expiration=2",
                destination,
                transport=transport,
            )

            self.assertEqual(transport.requests[1].get_header("If-range"), '"version-1"')
            self.assertEqual(transport.requests[1].get_header("Range"), "bytes=5-")
            self.assertEqual(destination.read_bytes(), b"hello world")
            self.assertEqual(receipt.resumed_from, 5)
            self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_a_changed_etag_in_a_partial_response_never_appends_new_version_bytes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            self._interrupt_download(destination, headers={"ETag": '"old"'})
            transport = RecordingTransport(
                FakeHttpResponse(
                    status=206,
                    body=b" world",
                    headers={"Content-Range": "bytes 5-10/11", "ETag": '"new"'},
                )
            )
            with self.assertRaisesRegex(MediaDownloadError, "validator"):
                download_media("https://media.example/video.mp4", destination, transport=transport)

            self.assertFalse(destination.exists())
            self.assertEqual(destination.with_suffix(".mp4.part").read_bytes(), b"hello")

    def test_last_modified_is_used_only_when_it_is_a_strong_validator(self):
        modified = "Wed, 02 Sep 2026 12:00:00 GMT"
        for response_headers, should_resume in (
            ({"Last-Modified": modified, "Date": "Wed, 02 Sep 2026 12:02:00 GMT"}, True),
            ({"Last-Modified": modified}, False),
            ({"Last-Modified": modified, "Date": modified}, False),
            (
                {
                    "ETag": 'W/"weak"',
                    "Last-Modified": modified,
                    "Date": "Wed, 02 Sep 2026 12:02:00 GMT",
                },
                False,
            ),
        ):
            with self.subTest(response_headers=response_headers):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    destination = Path(temporary_directory) / "video.mp4"
                    self._interrupt_download(destination, headers=response_headers)
                    transport = RecordingTransport(
                        FakeHttpResponse(
                            status=206 if should_resume else 200,
                            body=b" world" if should_resume else b"hello world",
                            headers={"Content-Range": "bytes 5-10/11"} if should_resume else {},
                        )
                    )
                    download_media(
                        "https://media.example/video.mp4", destination, transport=transport
                    )

                    self.assertEqual(
                        transport.requests[0].get_header("If-range"),
                        modified if should_resume else None,
                    )
                    self.assertEqual(destination.read_bytes(), b"hello world")

    def test_malformed_range_headers_cannot_publish_or_modify_the_partial_file(self):
        for response_headers in (
            {"Content-Range": "bytes 5-4/11"},
            {"Content-Range": "bytes 5-11/11"},
            {"Content-Range": "bytes 5-10/12"},
            {"Content-Range": "bytes 5-10/11", "Content-Length": "5"},
            {"Content-Range": "bytes 5-10/11", "Content-Length": "invalid"},
        ):
            with self.subTest(response_headers=response_headers):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    destination = Path(temporary_directory) / "video.mp4"
                    self._interrupt_download(destination, headers={"ETag": '"version-1"'})
                    transport = RecordingTransport(
                        FakeHttpResponse(status=206, body=b" world", headers=response_headers)
                    )
                    with self.assertRaises(MediaDownloadError):
                        download_media(
                            "https://media.example/video.mp4", destination, transport=transport
                        )
                    self.assertFalse(destination.exists())
                    self.assertEqual(destination.with_suffix(".mp4.part").read_bytes(), b"hello")

    def test_a_changed_source_does_not_resume_even_when_reusing_the_destination(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            self._interrupt_download(destination, headers={"ETag": '"version-1"'})
            transport = RecordingTransport(
                FakeHttpResponse(status=200, body=b"replacement", headers={"Content-Length": "11"})
            )

            download_media("https://media.example/new-video.mp4", destination, transport=transport)

            self.assertIsNone(transport.requests[0].get_header("Range"))
            self.assertEqual(destination.read_bytes(), b"replacement")

    def test_missing_or_corrupt_resume_state_restarts_an_orphaned_partial_file(self):
        for state_bytes in (None, b"broken state", b"\xff"):
            with self.subTest(state_bytes=state_bytes):
                transport = RecordingTransport(
                    FakeHttpResponse(status=200, body=b"complete", headers={"Content-Length": "8"})
                )
                with tempfile.TemporaryDirectory() as temporary_directory:
                    destination = Path(temporary_directory) / "image.jpg"
                    destination.with_suffix(".jpg.part").write_bytes(b"stale")
                    state_path = destination.with_suffix(".jpg.part.resume")
                    if state_bytes is not None:
                        state_path.write_bytes(state_bytes)

                    receipt = download_media(
                        "https://media.example/image.jpg", destination, transport=transport
                    )

                    self.assertIsNone(transport.requests[0].get_header("Range"))
                    self.assertEqual(receipt.resumed_from, 0)
                    self.assertEqual(destination.read_bytes(), b"complete")
                    self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_a_partial_response_with_extra_bytes_is_not_published_or_resumed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            self._interrupt_download(destination, headers={"ETag": '"version-1"'})
            oversized = RecordingTransport(
                FakeHttpResponse(
                    status=206,
                    body=b" world-extra",
                    headers={"Content-Range": "bytes 5-10/11", "ETag": '"version-1"'},
                )
            )
            with self.assertRaises(MediaDownloadError):
                download_media(
                    "https://media.example/video.mp4",
                    destination,
                    transport=oversized,
                    max_retries=0,
                )
            self.assertFalse(destination.exists())
            replacement = RecordingTransport(
                FakeHttpResponse(status=200, body=b"hello world", headers={"Content-Length": "11"})
            )

            download_media("https://media.example/video.mp4", destination, transport=replacement)

            self.assertIsNone(replacement.requests[0].get_header("Range"))
            self.assertEqual(destination.read_bytes(), b"hello world")

    def test_resume_state_does_not_persist_a_signed_url_or_leave_files_after_success(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            self._interrupt_download(
                destination,
                headers={"ETag": '"version-1"'},
                source_url="https://media.example/video.mp4?pkey=secret&expiration=123456",
            )
            saved_state = destination.with_suffix(".mp4.part.resume").read_text(encoding="utf-8")
            self.assertNotIn("secret", saved_state)
            self.assertNotIn("123456", saved_state)
            self.assertNotIn("https://", saved_state)
            transport = RecordingTransport(
                FakeHttpResponse(
                    status=200,
                    body=b"new version",
                    headers={"Content-Length": "11", "ETag": '"version-2"'},
                )
            )

            receipt = download_media(
                "https://media.example/video.mp4?pkey=renewed&expiration=123457",
                destination,
                transport=transport,
            )

            self.assertEqual(transport.requests[0].get_header("If-range"), '"version-1"')
            self.assertEqual(receipt.resumed_from, 0)
            self.assertEqual(destination.read_bytes(), b"new version")
            self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_partial_without_a_validator_restarts_without_a_range_request(self):
        transport = SequencedTransport(
            InterruptingHttpResponse(first_chunk=b"old", expected_total=8),
            FakeHttpResponse(status=200, body=b"new data", headers={"Content-Length": "8"}),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "image.jpg"
            with self.assertRaises(MediaDownloadError):
                download_media(
                    "https://media.example/image.jpg",
                    destination,
                    transport=transport,
                    max_retries=0,
                )

            receipt = download_media(
                "https://media.example/image.jpg", destination, transport=transport
            )

            self.assertIsNone(transport.requests[1].get_header("Range"))
            self.assertIsNone(transport.requests[1].get_header("If-range"))
            self.assertEqual(destination.read_bytes(), b"new data")
            self.assertEqual(receipt.resumed_from, 0)

    def test_refuses_credential_bearing_and_local_media_urls_before_network_access(self):
        transport = SequencedTransport(
            FakeHttpResponse(status=200, body=b"must-not-run", headers={}),
        )

        for source_url in (
            "file:///etc/passwd",
            "https://user:password@pic.example/image.jpg",
            "http://127.0.0.1/private",
            "http://[::1]/private",
            "http://localhost/private",
        ):
            with self.subTest(source_url=source_url):
                with (
                    tempfile.TemporaryDirectory() as temporary_directory,
                    self.assertRaisesRegex(MediaDownloadError, "trusted HTTP"),
                ):
                    download_media(
                        source_url,
                        Path(temporary_directory) / "media.bin",
                        transport=transport,
                    )

        self.assertEqual(transport.requests, [])

    def test_refuses_a_hostname_if_any_resolved_address_is_private(self):
        transport = SequencedTransport(
            FakeHttpResponse(status=200, body=b"must-not-run", headers={}),
        )

        with (
            patch(
                "zhihu_scraper.media.getaddrinfo",
                return_value=[
                    (
                        AF_INET,
                        SOCK_STREAM,
                        6,
                        "",
                        ("93.184.216.34", 443),
                    ),
                    (
                        AF_INET,
                        SOCK_STREAM,
                        6,
                        "",
                        ("10.20.30.40", 443),
                    ),
                ],
            ),
            tempfile.TemporaryDirectory() as temporary_directory,
            self.assertRaisesRegex(MediaDownloadError, "trusted HTTP"),
        ):
            download_media(
                "https://private.example/image.jpg",
                Path(temporary_directory) / "image.jpg",
                transport=transport,
            )

        self.assertEqual(transport.requests, [])

    def test_official_https_media_cdns_work_with_proxy_fake_ip_dns(self):
        for source_url in (
            "https://pic1.zhimg.com/image.jpg",
            "https://vdn6.vzuu.com/video.mp4",
        ):
            with self.subTest(source_url=source_url):
                transport = RecordingTransport(
                    FakeHttpResponse(
                        status=200,
                        body=b"official",
                        headers={"Content-Length": "8"},
                    )
                )
                with (
                    patch(
                        "zhihu_scraper.media.getaddrinfo",
                        return_value=[
                            (
                                AF_INET,
                                SOCK_STREAM,
                                6,
                                "",
                                ("198.18.0.1", 443),
                            )
                        ],
                    ) as resolver,
                    tempfile.TemporaryDirectory() as temporary_directory,
                ):
                    receipt = download_media(
                        source_url,
                        Path(temporary_directory) / "media.bin",
                        transport=transport,
                    )

                self.assertEqual(8, receipt.bytes_total)
                resolver.assert_not_called()

        for source_url in (
            "http://pic1.zhimg.com/image.jpg",
            "https://zhimg.com.attacker.example/image.jpg",
        ):
            with self.subTest(source_url=source_url):
                with (
                    patch(
                        "zhihu_scraper.media.getaddrinfo",
                        return_value=[
                            (
                                AF_INET,
                                SOCK_STREAM,
                                6,
                                "",
                                ("198.18.0.1", 443),
                            )
                        ],
                    ),
                    tempfile.TemporaryDirectory() as temporary_directory,
                    self.assertRaisesRegex(MediaDownloadError, "trusted HTTP"),
                ):
                    download_media(
                        source_url,
                        Path(temporary_directory) / "media.bin",
                        transport=RecordingTransport(
                            FakeHttpResponse(status=200, body=b"", headers={})
                        ),
                    )

    def test_refuses_a_redirect_to_a_loopback_address_before_following_it(self):
        transport = SequencedTransport(
            FakeHttpResponse(
                status=302,
                body=b"",
                headers={"Location": "http://127.0.0.1/internal"},
            ),
        )

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            self.assertRaisesRegex(MediaDownloadError, "trusted HTTP"),
        ):
            download_media(
                "https://media.example/image.jpg",
                Path(temporary_directory) / "image.jpg",
                transport=transport,
            )

        self.assertEqual(len(transport.requests), 1)

    def test_rechecks_dns_before_each_retry_to_limit_rebinding(self):
        public_resolution = [
            (
                AF_INET,
                SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", 443),
            )
        ]
        private_resolution = [
            (
                AF_INET,
                SOCK_STREAM,
                6,
                "",
                ("127.0.0.1", 443),
            )
        ]
        transport = SequencedTransport(
            FakeHttpResponse(status=503, body=b"", headers={}),
            FakeHttpResponse(
                status=200,
                body=b"must-not-run",
                headers={"Content-Length": "12"},
            ),
        )

        with (
            patch(
                "zhihu_scraper.media.getaddrinfo",
                side_effect=[public_resolution, private_resolution],
            ),
            tempfile.TemporaryDirectory() as temporary_directory,
            self.assertRaisesRegex(MediaDownloadError, "trusted HTTP"),
        ):
            download_media(
                "https://changing.example/image.jpg",
                Path(temporary_directory) / "image.jpg",
                transport=transport,
                max_retries=1,
                sleep=lambda _delay: None,
            )

        self.assertEqual(len(transport.requests), 1)

    def test_routes_media_through_the_configured_proxy(self):
        proxy = "http://account:password@127.0.0.1:7890"
        opener = RecordingOpener(
            FakeHttpResponse(
                status=200,
                body=b"proxied",
                headers={"Content-Length": "7"},
            )
        )
        proxy_handler = object()

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch("zhihu_scraper.media.ProxyHandler", return_value=proxy_handler) as handler,
            patch("zhihu_scraper.media.build_opener", return_value=opener) as build,
        ):
            destination = Path(temporary_directory) / "image.jpg"
            receipt = download_media(
                "https://pic.example/image.jpg",
                destination,
                proxy=proxy,
                timeout=12.5,
            )

        handler.assert_called_once_with({"http": proxy, "https": proxy})
        build.assert_called_once()
        opener_handlers = build.call_args.args
        self.assertIs(opener_handlers[0], proxy_handler)
        self.assertIsInstance(opener_handlers[1], HTTPRedirectHandler)
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(opener.timeouts, [12.5])
        self.assertEqual(receipt.bytes_total, 7)

    def test_retries_temporary_server_failure_with_bounded_backoff(self):
        transport = SequencedTransport(
            FakeHttpResponse(status=503, body=b"", headers={}),
            FakeHttpResponse(
                status=200,
                body=b"recovered",
                headers={"Content-Length": "9"},
            ),
        )
        sleeps = []

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "image.jpg"
            receipt = download_media(
                "https://pic.example/image.jpg",
                destination,
                transport=transport,
                max_retries=1,
                sleep=sleeps.append,
            )

        self.assertEqual(receipt.bytes_total, 9)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(sleeps, [1.0])

    def test_does_not_retry_permanent_client_failure(self):
        transport = SequencedTransport(
            FakeHttpResponse(status=404, body=b"", headers={}),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(Exception, "404"):
                download_media(
                    "https://pic.example/missing.jpg",
                    Path(temporary_directory) / "image.jpg",
                    transport=transport,
                    max_retries=3,
                    sleep=lambda _delay: self.fail("must not retry HTTP 404"),
                )

        self.assertEqual(len(transport.requests), 1)

    def test_resumes_an_existing_partial_file_with_a_range_request(self):
        source_url = "https://media.example/video.mp4"
        transport = RecordingTransport(
            FakeHttpResponse(
                status=206,
                body=b" world",
                headers={
                    "Content-Range": "bytes 5-10/11",
                    "Content-Length": "6",
                },
            )
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            partial_path = destination.with_name(f"{destination.name}.part")
            self._interrupt_download(
                destination, headers={"ETag": '"version-1"'}, source_url=source_url
            )

            receipt = download_media(source_url, destination, transport=transport)

            self.assertEqual(destination.read_bytes(), b"hello world")
            self.assertFalse(partial_path.exists())
            self.assertEqual(transport.requests[0].get_header("Range"), "bytes=5-")
            self.assertEqual(receipt.source_url, source_url)
            self.assertEqual(receipt.destination, destination)
            self.assertEqual(receipt.resumed_from, 5)
            self.assertEqual(receipt.bytes_total, 11)

    def test_restarts_safely_when_a_server_ignores_the_range_header(self):
        source_url = "https://media.example/video.mp4"
        transport = RecordingTransport(
            FakeHttpResponse(
                status=200,
                body=b"complete replacement",
                headers={"Content-Length": "20"},
            )
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            self._interrupt_download(
                destination, headers={"ETag": '"version-1"'}, source_url=source_url
            )

            receipt = download_media(source_url, destination, transport=transport)

            self.assertEqual(transport.requests[0].get_header("Range"), "bytes=5-")
            self.assertEqual(destination.read_bytes(), b"complete replacement")
            self.assertEqual(receipt.resumed_from, 0)
            self.assertEqual(receipt.bytes_total, 20)

    def test_network_read_interruptions_resume_from_the_new_partial_size(self):
        for failure in (
            IncompleteRead(b"", 6),
            ConnectionResetError("connection reset"),
            OSError("socket read failed"),
        ):
            with self.subTest(failure=type(failure).__name__):
                transport = SequencedTransport(
                    InterruptingHttpResponse(
                        first_chunk=b"hello",
                        expected_total=11,
                        failure=failure,
                        headers={"ETag": '"version-1"'},
                    ),
                    FakeHttpResponse(
                        status=206,
                        body=b" world",
                        headers={
                            "Content-Range": "bytes 5-10/11",
                            "Content-Length": "6",
                        },
                    ),
                )

                with tempfile.TemporaryDirectory() as temporary_directory:
                    destination = Path(temporary_directory) / "video.mp4"
                    receipt = download_media(
                        "https://media.example/video.mp4",
                        destination,
                        transport=transport,
                        max_retries=1,
                        sleep=lambda _delay: None,
                    )

                    self.assertEqual(destination.read_bytes(), b"hello world")
                    self.assertEqual(receipt.resumed_from, 5)
                    self.assertEqual(
                        transport.requests[1].get_header("Range"),
                        "bytes=5-",
                    )

    def test_redownloads_an_existing_zero_byte_destination(self):
        transport = RecordingTransport(
            FakeHttpResponse(
                status=200,
                body=b"complete",
                headers={"Content-Length": "8"},
            )
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "image.jpg"
            destination.touch()

            receipt = download_media(
                "https://media.example/image.jpg",
                destination,
                transport=transport,
            )

            self.assertEqual(destination.read_bytes(), b"complete")
            self.assertEqual(receipt.bytes_total, 8)
            self.assertEqual(len(transport.requests), 1)

    def test_interruption_keeps_only_a_resumable_partial_file(self):
        source_url = "https://media.example/video.mp4"
        transport = RecordingTransport(
            InterruptingHttpResponse(first_chunk=b"first chunk", expected_total=20)
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            partial_path = destination.with_name(f"{destination.name}.part")

            with self.assertRaisesRegex(MediaDownloadError, "response interrupted"):
                download_media(
                    source_url,
                    destination,
                    transport=transport,
                    max_retries=0,
                )

            self.assertFalse(destination.exists())
            self.assertEqual(partial_path.read_bytes(), b"first chunk")


if __name__ == "__main__":
    unittest.main()
