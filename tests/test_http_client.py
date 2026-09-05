import json
import tempfile
import unittest
from email.utils import formatdate
from pathlib import Path

from zhihu_scraper.http import (
    AccessDeniedError,
    AuthenticationError,
    CookieFileError,
    InvalidResponseError,
    RateLimitError,
    RetryWaitError,
    ServerError,
    TransportError,
    UnsafeZhihuUrlError,
    ZhihuHttpClient,
    diagnose_cookies,
    load_cookies,
)


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data: object = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if isinstance(self._json_data, BaseException):
            raise self._json_data
        return self._json_data


class FakeSession:
    def __init__(self, responses: list[FakeResponse | Exception]):
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.close_count = 0

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        self.close_count += 1


class ExplodingSession:
    def __init__(self, message: str):
        self._message = message

    def get(self, url: str, **kwargs):
        raise RuntimeError(self._message)


class VirtualTime:
    def __init__(self):
        self.elapsed = 0.0
        self.delays = []

    def monotonic(self):
        return self.elapsed

    def sleep(self, delay):
        self.delays.append(delay)
        self.elapsed += delay


class CookieLoadingTests(unittest.TestCase):
    def test_loads_browser_cookie_list_and_reports_missing_core_cookie_names(self):
        secret_value = "secret-z-c0-value"
        exported_cookies = [
            {"name": "z_c0", "value": secret_value, "domain": ".zhihu.com"},
            {"name": "other_cookie", "value": "other-secret"},
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(json.dumps(exported_cookies), encoding="utf-8")

            cookies = load_cookies(cookie_path)
            diagnostic = diagnose_cookies(cookies)

        self.assertEqual(cookies["z_c0"], secret_value)
        self.assertEqual(diagnostic.missing, ("d_c0",))
        self.assertFalse(diagnostic.is_complete)
        self.assertIn("d_c0", diagnostic.message)
        self.assertNotIn(secret_value, diagnostic.message)

    def test_loads_cookie_mapping_and_ignores_empty_non_string_values(self):
        exported_cookies = {
            "z_c0": "z-secret",
            "d_c0": "d-secret",
            "empty": "",
            "not-a-cookie": 123,
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(json.dumps(exported_cookies), encoding="utf-8")

            cookies = load_cookies(cookie_path)

        self.assertEqual(cookies, {"z_c0": "z-secret", "d_c0": "d-secret"})
        self.assertTrue(diagnose_cookies(cookies).is_complete)

    def test_browser_export_list_keeps_only_explicit_zhihu_domains(self):
        exported_cookies = [
            {"name": "z_c0", "value": "z-secret", "domain": ".zhihu.com"},
            {"name": "d_c0", "value": "d-secret", "domain": "www.zhihu.com"},
            {"name": "google-session", "value": "foreign-secret", "domain": ".google.com"},
            {"name": "lookalike", "value": "lookalike-secret", "domain": "notzhihu.com"},
            {"name": "unscoped", "value": "unknown-secret"},
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(json.dumps(exported_cookies), encoding="utf-8")

            cookies = load_cookies(cookie_path)

        self.assertEqual(cookies, {"z_c0": "z-secret", "d_c0": "d-secret"})
        self.assertNotIn("foreign-secret", repr(cookies))
        self.assertNotIn("lookalike-secret", repr(cookies))
        self.assertNotIn("unknown-secret", repr(cookies))

    def test_malformed_cookie_file_raises_a_sanitized_error(self):
        secret_value = "malformed-secret-value"

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(
                f'{{"z_c0": "{secret_value}", broken',
                encoding="utf-8",
            )

            with self.assertRaises(CookieFileError) as raised:
                load_cookies(cookie_path)

        self.assertIn("cookies.json", str(raised.exception))
        self.assertNotIn(secret_value, str(raised.exception))

    def test_placeholder_cookie_values_are_diagnosed_as_missing(self):
        exported_cookies = {
            "z_c0": "YOUR_Z_C0_HERE",
            "d_c0": "   ",
            "language": " zh-CN ",
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(json.dumps(exported_cookies), encoding="utf-8")

            cookies = load_cookies(cookie_path)
            diagnostic = diagnose_cookies(cookies)

        self.assertEqual(cookies, {"language": "zh-CN"})
        self.assertEqual(diagnostic.missing, ("z_c0", "d_c0"))


class ZhihuHttpClientTests(unittest.TestCase):
    def test_shared_client_spaces_json_html_and_comment_requests_with_jitter(self):
        timer = VirtualTime()
        random_values = iter((0.0, 1.0, 0.5, 0.0))
        session = FakeSession([FakeResponse() for _ in range(4)])
        client = ZhihuHttpClient(
            session=session,
            request_interval=0.5,
            request_jitter=0.5,
            sleep=timer.sleep,
            monotonic=timer.monotonic,
            random=lambda: next(random_values),
        )

        client.get_json("/api/v4/articles/1")
        self.assertEqual([], timer.delays)
        client.get_html("https://zhuanlan.zhihu.com/p/1")
        client.get_json("/api/v4/questions/1/answers?offset=20")
        client.get_json("/api/v4/comment_v5/articles/1/root_comment")

        self.assertEqual([0.5, 1.0, 0.75], timer.delays)
        self.assertEqual(4, len(session.calls))

    def test_retry_pacing_obeys_server_waits_and_the_same_total_budget(self):
        cases = ((10, 0, "20", 20), (10, 0, "2", 10), (60, 60, "1", None))
        for interval, jitter, retry_after, expected_time in cases:
            with self.subTest(interval=interval, jitter=jitter, retry_after=retry_after):
                timer = VirtualTime()
                session = FakeSession(
                    [
                        FakeResponse(status_code=429, headers={"Retry-After": retry_after}),
                        FakeResponse(json_data={"ok": True}),
                    ]
                )
                client = ZhihuHttpClient(
                    session=session,
                    request_interval=interval,
                    request_jitter=jitter,
                    max_retries=1,
                    sleep=timer.sleep,
                    monotonic=timer.monotonic,
                    random=lambda: 1.0,
                )

                if expected_time is None:
                    with self.assertRaisesRegex(RetryWaitError, "60-second"):
                        client.get_json("/api/v4/items")
                    self.assertLessEqual(timer.elapsed, 60)
                    self.assertEqual(1, len(session.calls))
                else:
                    self.assertEqual({"ok": True}, client.get_json("/api/v4/items"))
                    self.assertEqual(expected_time, timer.elapsed)
                    self.assertEqual(2, len(session.calls))

    def test_direct_client_rejects_invalid_pacing_values(self):
        for name in ("request_interval", "request_jitter"):
            for value in (-0.1, 60.1, float("nan"), float("inf"), True, "0.5"):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, name):
                        ZhihuHttpClient(session=FakeSession([]), **{name: value})

    def test_elapsed_time_counts_towards_request_spacing_without_using_wall_clock(self):
        timer = VirtualTime()
        client = ZhihuHttpClient(
            session=FakeSession([FakeResponse() for _ in range(3)]),
            request_interval=1,
            sleep=timer.sleep,
            monotonic=timer.monotonic,
            clock=lambda: self.fail("Request pacing must not read the wall clock."),
        )

        client.get_json("/api/v4/articles/1")
        timer.elapsed += 2
        client.get_json("/api/v4/articles/2")
        self.assertEqual([], timer.delays)
        timer.elapsed += 0.25
        client.get_json("/api/v4/articles/3")

        self.assertEqual([0.75], timer.delays)

    def test_context_manager_closes_the_owned_session_exactly_once(self):
        session = FakeSession([])
        client = ZhihuHttpClient(session=session)

        with client:
            pass
        client.close()

        self.assertEqual(session.close_count, 1)

    def test_invalid_json_is_wrapped_without_copying_response_details(self):
        session = FakeSession([FakeResponse(json_data=ValueError("secret response body"))])

        with self.assertRaises(InvalidResponseError) as raised:
            ZhihuHttpClient(session=session).get_json("/api/v4/me")

        self.assertIn("not valid JSON", str(raised.exception))
        self.assertNotIn("secret response body", str(raised.exception))

    def test_get_json_uses_the_zhihu_origin_and_authenticated_session(self):
        cookies = {"z_c0": "z-secret", "d_c0": "d-secret"}
        session = FakeSession([FakeResponse(json_data={"id": "member-id", "name": "归档用户"})])
        client = ZhihuHttpClient(cookies=cookies, session=session)

        payload = client.get_json("/api/v4/me")

        self.assertEqual(payload, {"id": "member-id", "name": "归档用户"})
        requested_url, request_options = session.calls[0]
        self.assertEqual(requested_url, "https://www.zhihu.com/api/v4/me")
        self.assertEqual(request_options["cookies"], cookies)
        self.assertIs(request_options["allow_redirects"], False)

    def test_unexpected_redirect_is_not_followed_or_treated_as_success(self):
        session = FakeSession(
            [
                FakeResponse(
                    status_code=302,
                    headers={"Location": "https://attacker.example/cookie-sink"},
                )
            ]
        )

        with self.assertRaisesRegex(InvalidResponseError, "unexpected redirect"):
            ZhihuHttpClient(cookies={"z_c0": "secret"}, session=session).get_json(
                "/api/v4/articles/1"
            )

        self.assertEqual(1, len(session.calls))
        self.assertIs(session.calls[0][1]["allow_redirects"], False)

    def test_browser_cookie_backflow_updates_subsequent_http_requests(self):
        session = FakeSession([FakeResponse(json_data={"data": []})])
        client = ZhihuHttpClient(
            cookies={"z_c0": "initial-z"},
            session=session,
        )

        client.update_cookies(
            {
                "d_c0": "browser-d",
                "__zse_ck": "browser-challenge",
                "": "ignored",
            }
        )
        client.get_json("/api/v4/questions/1/answers")

        self.assertEqual(
            {
                "z_c0": "initial-z",
                "d_c0": "browser-d",
                "__zse_ck": "browser-challenge",
            },
            session.calls[0][1]["cookies"],
        )

    def test_get_html_preserves_absolute_url_and_applies_optional_proxy(self):
        source_url = "https://zhuanlan.zhihu.com/p/357892158"
        proxy = "http://127.0.0.1:7890"
        session = FakeSession([FakeResponse(text="<article>正文</article>")])
        client = ZhihuHttpClient(proxy=proxy, session=session)

        html = client.get_html(source_url)

        self.assertEqual(html, "<article>正文</article>")
        requested_url, request_options = session.calls[0]
        self.assertEqual(requested_url, source_url)
        self.assertEqual(request_options["proxy"], proxy)

    def test_unauthorized_error_does_not_disclose_cookie_or_proxy_values(self):
        cookie_secret = "never-print-this-cookie"
        proxy_secret = "never-print-this-proxy-password"
        session = FakeSession(
            [
                FakeResponse(
                    status_code=401,
                    text=f"server echoed {cookie_secret}",
                )
            ]
        )
        client = ZhihuHttpClient(
            cookies={"z_c0": cookie_secret},
            proxy=f"http://user:{proxy_secret}@proxy.example",
            session=session,
        )

        with self.assertRaises(AuthenticationError) as raised:
            client.get_json("/api/v4/me")

        message = str(raised.exception)
        self.assertIn("HTTP 401", message)
        self.assertIn("z_c0", message)
        self.assertIn("d_c0", message)
        self.assertNotIn(cookie_secret, message)
        self.assertNotIn(proxy_secret, message)
        self.assertEqual(len(session.calls), 1)

    def test_forbidden_response_has_a_distinct_non_retryable_error(self):
        session = FakeSession([FakeResponse(status_code=403)])
        client = ZhihuHttpClient(session=session)

        with self.assertRaises(AccessDeniedError) as raised:
            client.get_html("https://zhuanlan.zhihu.com/p/1")

        self.assertIn("HTTP 403", str(raised.exception))
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(len(session.calls), 1)

    def test_rate_limit_waits_then_returns_the_successful_retry(self):
        session = FakeSession(
            [
                FakeResponse(status_code=429, headers={"Retry-After": "0.25"}),
                FakeResponse(json_data={"items": [1, 2, 3]}),
            ]
        )
        delays: list[float] = []
        client = ZhihuHttpClient(
            session=session,
            max_retries=2,
            sleep=delays.append,
        )

        payload = client.get_json("/api/v4/items")

        self.assertEqual(payload, {"items": [1, 2, 3]})
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(delays, [0.25])

    def test_rate_limit_stops_after_the_configured_retry_budget(self):
        session = FakeSession(
            [
                FakeResponse(status_code=429),
                FakeResponse(status_code=429),
            ]
        )
        delays: list[float] = []
        client = ZhihuHttpClient(
            session=session,
            max_retries=1,
            sleep=delays.append,
        )

        with self.assertRaises(RateLimitError) as raised:
            client.get_json("/api/v4/items")

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(delays, [1.0])

    def test_excessive_retry_after_stops_without_waiting_or_requesting_early(self):
        for status in (429, 503):
            with self.subTest(status=status):
                session = FakeSession(
                    [
                        FakeResponse(status_code=status, headers={"Retry-After": "86400"}),
                        FakeResponse(json_data={"unexpected": "early retry"}),
                    ]
                )
                delays = []
                client = ZhihuHttpClient(session=session, max_retries=2, sleep=delays.append)

                with self.assertRaisesRegex(RetryWaitError, "try again later"):
                    client.get_json("/api/v4/items")

                self.assertEqual([], delays)
                self.assertEqual(1, len(session.calls))

    def test_invalid_retry_after_stops_without_guessing_an_earlier_retry(self):
        for retry_after in ("inf", "-inf", "nan", "-1", "not-a-date"):
            with self.subTest(retry_after=retry_after):
                session = FakeSession(
                    [
                        FakeResponse(status_code=429, headers={"Retry-After": retry_after}),
                        FakeResponse(json_data={"unexpected": "early retry"}),
                    ]
                )
                delays = []
                client = ZhihuHttpClient(session=session, max_retries=1, sleep=delays.append)

                with self.assertRaisesRegex(RetryWaitError, "try again later"):
                    client.get_json("/api/v4/items")

                self.assertEqual([], delays)
                self.assertEqual(1, len(session.calls))

    def test_retry_after_http_dates_respect_the_clock_and_waiting_budget(self):
        now = 1_800_000_000.0
        for seconds in (-10, 30, 86400):
            with self.subTest(seconds=seconds):
                session = FakeSession(
                    [
                        FakeResponse(
                            status_code=503,
                            headers={"retry-after": formatdate(now + seconds, usegmt=True)},
                        ),
                        FakeResponse(json_data={"ok": True}),
                    ]
                )
                delays = []
                client = ZhihuHttpClient(
                    session=session,
                    max_retries=1,
                    sleep=delays.append,
                    clock=lambda: now,
                )

                if seconds > 60:
                    with self.assertRaisesRegex(RetryWaitError, "try again later"):
                        client.get_json("/api/v4/items")
                    self.assertEqual([], delays)
                    self.assertEqual(1, len(session.calls))
                else:
                    self.assertEqual({"ok": True}, client.get_json("/api/v4/items"))
                    self.assertEqual([max(0.0, seconds)], delays)
                    self.assertEqual(2, len(session.calls))

    def test_retry_wait_budget_counts_all_server_and_transport_delays(self):
        cases = (
            (
                [
                    FakeResponse(status_code=429, headers={"Retry-After": "40"}),
                    FakeResponse(status_code=503, headers={"Retry-After": "30"}),
                ],
                [40.0],
            ),
            (
                [
                    RuntimeError("temporary network failure"),
                    FakeResponse(status_code=429, headers={"Retry-After": "60"}),
                ],
                [1.0],
            ),
        )
        for responses, expected_delays in cases:
            with self.subTest(expected_delays=expected_delays):
                session = FakeSession(responses)
                delays = []
                client = ZhihuHttpClient(session=session, max_retries=3, sleep=delays.append)

                with self.assertRaisesRegex(RetryWaitError, "60-second"):
                    client.get_json("/api/v4/items")

                self.assertEqual(expected_delays, delays)
                self.assertEqual(2, len(session.calls))

    def test_exactly_sixty_seconds_of_retry_wait_can_still_succeed(self):
        session = FakeSession(
            [
                FakeResponse(status_code=429, headers={"Retry-After": "30"}),
                FakeResponse(status_code=429, headers={"Retry-After": "30"}),
                FakeResponse(json_data={"ok": True}),
            ]
        )
        delays = []
        client = ZhihuHttpClient(session=session, max_retries=2, sleep=delays.append)

        self.assertEqual({"ok": True}, client.get_json("/api/v4/items"))
        self.assertEqual([30.0, 30.0], delays)

    def test_transport_only_backoff_also_respects_the_total_wait_budget(self):
        delays = []
        client = ZhihuHttpClient(
            session=ExplodingSession("private proxy detail"),
            max_retries=10,
            sleep=delays.append,
        )

        with self.assertRaisesRegex(RetryWaitError, "try again later"):
            client.get_json("/api/v4/items")

        self.assertEqual([1.0, 2.0, 4.0, *([8.0] * 6)], delays)

    def test_server_error_retries_then_raises_a_distinct_error(self):
        session = FakeSession(
            [
                FakeResponse(status_code=503),
                FakeResponse(status_code=503),
                FakeResponse(status_code=503),
            ]
        )
        delays: list[float] = []
        client = ZhihuHttpClient(
            session=session,
            max_retries=2,
            sleep=delays.append,
        )

        with self.assertRaises(ServerError) as raised:
            client.get_html("https://zhuanlan.zhihu.com/p/1")

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("HTTP 503", str(raised.exception))
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(delays, [1.0, 2.0])

    def test_login_check_returns_authenticated_member_identity(self):
        session = FakeSession(
            [
                FakeResponse(
                    json_data={
                        "id": "member-id",
                        "name": "归档用户",
                        "url_token": "archive-user",
                    }
                )
            ]
        )
        client = ZhihuHttpClient(session=session)

        status = client.check_login()

        self.assertTrue(status.authenticated)
        self.assertEqual(status.member_id, "member-id")
        self.assertEqual(status.name, "归档用户")
        self.assertEqual(session.calls[0][0], "https://www.zhihu.com/api/v4/me")

    def test_login_check_turns_rejected_session_into_an_unauthenticated_status(self):
        session = FakeSession([FakeResponse(status_code=401)])
        client = ZhihuHttpClient(session=session)

        status = client.check_login()

        self.assertFalse(status.authenticated)
        self.assertEqual(status.reason, "authentication_rejected")
        self.assertIsNone(status.member_id)

    def test_transport_failure_is_wrapped_without_disclosing_cookie_values(self):
        secret_value = "transport-secret-cookie"
        client = ZhihuHttpClient(
            cookies={"z_c0": secret_value},
            session=ExplodingSession(f"network failed with {secret_value}"),
            max_retries=0,
        )

        with self.assertRaises(TransportError) as raised:
            client.get_json("/api/v4/me")

        self.assertIn("request failed", str(raised.exception))
        self.assertNotIn(secret_value, str(raised.exception))

    def test_refuses_to_send_zhihu_cookies_to_an_external_host(self):
        secret_value = "host-safety-secret"
        session = FakeSession([])
        client = ZhihuHttpClient(
            cookies={"z_c0": secret_value},
            session=session,
        )

        with self.assertRaises(UnsafeZhihuUrlError) as raised:
            client.get_html("https://attacker.example/collect")

        self.assertEqual(session.calls, [])
        self.assertNotIn(secret_value, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
