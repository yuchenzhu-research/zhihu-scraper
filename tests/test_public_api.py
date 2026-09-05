import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from zhihu_scraper.archive import ArchiveReceipt
from zhihu_scraper.domain import Article
from zhihu_scraper.facade import archive_url, build_workflow, check_session
from zhihu_scraper.http import LoginStatus
from zhihu_scraper.settings import ArchiveSettings, BrowserFallback


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_json(self, url):
        self.calls.append(url)
        return {
            "id": 1,
            "title": "公共接口文章",
            "content": "<p>正文</p>",
            "author": {"id": "author", "name": "作者"},
        }

    def get_html(self, url):
        raise AssertionError("HTML fallback should not be used")


class FakeSink:
    def __init__(self):
        self.saved = []

    def archive(self, target):
        self.saved.append(target)
        return ArchiveReceipt(Path("saved"), None, None)


class FakeLoginBrowser:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.open_count = 0
        self.closed = False

    def open_login_page(self):
        self.open_count += 1

    def cookie_dict(self):
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class LoginTimer:
    def __init__(self):
        self.elapsed = 0.0

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds


class PublicApiTests(unittest.TestCase):
    def test_login_waits_for_browser_cookies_verifies_identity_and_saves_once(self):
        from zhihu_scraper.facade import login_session

        timer = LoginTimer()
        cookies = {"z_c0": "private-session", "d_c0": "private-device"}
        browser = FakeLoginBrowser([{}, cookies])
        client = Mock()
        client.check_login.return_value = LoginStatus(authenticated=True, member_id="private-id")
        create_client = Mock(return_value=client)
        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"

            report = login_session(
                ArchiveSettings(cookie_file=cookie_path),
                timeout=10,
                poll_interval=1,
                browser_factory=lambda: browser,
                client_factory=create_client,
                sleep=timer.sleep,
                monotonic=timer.monotonic,
            )

            self.assertEqual(cookies, json.loads(cookie_path.read_text(encoding="utf-8")))
            self.assertEqual(cookie_path, report.cookie_file)
        self.assertTrue(report.authenticated)
        for secret in ("private-session", "private-device", "private-id"):
            self.assertNotIn(secret, repr(report))
        self.assertEqual(1, browser.open_count)
        self.assertTrue(browser.closed)
        create_client.assert_called_once_with(cookies, 9.0)
        client.check_login.assert_called_once_with()
        client.close.assert_called_once_with()

    def test_login_timeout_or_cancellation_preserves_previous_cookie_file(self):
        from zhihu_scraper.facade import LoginTimeoutError, login_session

        for cancellation in (False, True):
            with self.subTest(cancellation=cancellation):
                timer = LoginTimer()
                browser = FakeLoginBrowser([{"z_c0": "unverified-session"}])
                client = Mock()
                client.check_login.return_value = LoginStatus(authenticated=False)
                if cancellation:
                    client.check_login.side_effect = KeyboardInterrupt
                with tempfile.TemporaryDirectory() as temporary_directory:
                    cookie_path = Path(temporary_directory) / "cookies.json"
                    cookie_path.write_text("previous-cookie-file", encoding="utf-8")

                    with self.assertRaises(
                        KeyboardInterrupt if cancellation else LoginTimeoutError
                    ):
                        login_session(
                            ArchiveSettings(cookie_file=cookie_path),
                            timeout=5,
                            poll_interval=2,
                            browser_factory=lambda: browser,
                            client_factory=lambda cookies, remaining: client,
                            sleep=timer.sleep,
                            monotonic=timer.monotonic,
                        )

                    self.assertEqual(
                        "previous-cookie-file", cookie_path.read_text(encoding="utf-8")
                    )
                    self.assertEqual([cookie_path], list(cookie_path.parent.iterdir()))
                self.assertTrue(browser.closed)
                self.assertEqual(1 if cancellation else 3, client.close.call_count)
                self.assertLessEqual(timer.elapsed, 5)

    def test_login_does_not_save_a_verification_that_finishes_after_the_deadline(self):
        from zhihu_scraper.facade import LoginTimeoutError, login_session

        timer = LoginTimer()
        browser = FakeLoginBrowser([{"z_c0": "private-session"}])
        client = Mock()

        def late_success():
            timer.elapsed += 3
            return LoginStatus(authenticated=True)

        client.check_login.side_effect = late_success
        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            with self.assertRaises(LoginTimeoutError):
                login_session(
                    ArchiveSettings(cookie_file=cookie_path),
                    timeout=2,
                    browser_factory=lambda: browser,
                    client_factory=lambda cookies, remaining: client,
                    sleep=timer.sleep,
                    monotonic=timer.monotonic,
                )
            self.assertFalse(cookie_path.exists())
        self.assertTrue(browser.closed)
        client.close.assert_called_once_with()

    def test_login_does_not_start_a_request_when_less_than_one_millisecond_remains(self):
        from zhihu_scraper.facade import LoginTimeoutError, login_session

        timer = LoginTimer()
        browser = FakeLoginBrowser([{}])

        def almost_out_of_time():
            timer.elapsed = 1.9999
            return {"z_c0": "private-session"}

        browser.cookie_dict = almost_out_of_time
        client = Mock()
        client.check_login.return_value = LoginStatus(authenticated=True)
        create_client = Mock(return_value=client)
        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            with self.assertRaises(LoginTimeoutError):
                login_session(
                    ArchiveSettings(cookie_file=cookie_path),
                    timeout=2,
                    browser_factory=lambda: browser,
                    client_factory=create_client,
                    sleep=timer.sleep,
                    monotonic=timer.monotonic,
                )
            self.assertFalse(cookie_path.exists())
        create_client.assert_not_called()

    def test_login_composes_a_visible_browser_and_a_single_bounded_identity_request(self):
        from zhihu_scraper.facade import login_session

        browser = FakeLoginBrowser([{"z_c0": "private-session"}])
        client = Mock()
        client.check_login.return_value = LoginStatus(authenticated=True)
        with tempfile.TemporaryDirectory() as temporary_directory:
            with (
                patch(
                    "zhihu_scraper.facade.BrowserFallback", return_value=browser
                ) as create_browser,
                patch("zhihu_scraper.facade.ZhihuHttpClient", return_value=client) as create_client,
            ):
                login_session(
                    ArchiveSettings(
                        cookie_file=Path(temporary_directory) / "cookies.json",
                        headless=True,
                        cdp_url="http://localhost:9222",
                        timeout=30,
                        proxy="http://127.0.0.1:7890",
                    ),
                    timeout=10,
                    monotonic=lambda: 0.0,
                )

        self.assertFalse(create_browser.call_args.kwargs["headless"])
        self.assertEqual("http://localhost:9222", create_browser.call_args.kwargs["cdp_url"])
        self.assertEqual(10_000, create_browser.call_args.kwargs["timeout_ms"])
        self.assertEqual(0, create_client.call_args.kwargs["max_retries"])
        self.assertEqual(10, create_client.call_args.kwargs["timeout"])
        self.assertEqual("http://127.0.0.1:7890", create_client.call_args.kwargs["proxy"])

    def test_invalid_output_settings_do_not_acquire_http_resources(self):
        for settings, error in (
            (ArchiveSettings(pdf=True), NotImplementedError),
            (ArchiveSettings(markdown=False, html=False), ValueError),
        ):
            with (
                self.subTest(settings=settings),
                patch("zhihu_scraper.facade.ZhihuHttpClient") as create_client,
            ):
                with self.assertRaises(error):
                    archive_url("https://zhuanlan.zhihu.com/p/1", settings)
                create_client.assert_not_called()

    def test_cookie_save_replaces_an_existing_file_with_valid_json(self):
        from zhihu_scraper.http import save_cookies

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text('{"z_c0":"old"}', encoding="utf-8")

            saved = save_cookies(cookie_path, {"z_c0": "new-secret", "d_c0": "device"})

            self.assertEqual(cookie_path, saved)
            self.assertEqual(
                {"z_c0": "new-secret", "d_c0": "device"},
                json.loads(cookie_path.read_text(encoding="utf-8")),
            )
            self.assertEqual([cookie_path], list(cookie_path.parent.iterdir()))

    def test_cookie_save_requires_private_permissions_before_writing_and_preserves_old_file(self):
        from zhihu_scraper.http import CookieFileError, save_cookies

        def reject_permissions(temporary_path):
            self.assertEqual(b"", temporary_path.read_bytes())
            raise OSError("private-permission-error-detail")

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text("old-file", encoding="utf-8")
            with patch(
                "zhihu_scraper.http.RuntimePlatform.secure_private_file",
                side_effect=reject_permissions,
            ):
                with self.assertRaises(CookieFileError) as raised:
                    save_cookies(cookie_path, {"z_c0": "new-secret"})
            self.assertEqual("old-file", cookie_path.read_text(encoding="utf-8"))
            self.assertEqual([cookie_path], list(cookie_path.parent.iterdir()))
            self.assertNotIn("private-permission-error-detail", str(raised.exception))
            self.assertNotIn("new-secret", str(raised.exception))

    def test_archive_url_closes_the_internally_built_workflow(self):
        workflow = Mock()
        workflow.run.return_value = "report"
        with patch("zhihu_scraper.facade.build_workflow", return_value=workflow):
            result = archive_url(
                "https://zhuanlan.zhihu.com/p/1",
                ArchiveSettings(media_download=False),
            )

        self.assertEqual(result, "report")
        workflow.close.assert_called_once_with()

    def test_build_workflow_exposes_injectable_source_and_sink_boundaries(self):
        client = FakeClient()
        sink = FakeSink()
        workflow = build_workflow(
            ArchiveSettings(
                media_download=False,
                browser_fallback=BrowserFallback.NEVER,
            ),
            client=client,
            sink=sink,
        )

        report = workflow.run("https://zhuanlan.zhihu.com/p/1")

        self.assertIsInstance(report.target, Article)
        self.assertEqual(Path("saved"), report.receipt.entry_directory)
        self.assertEqual(["/api/v4/articles/1"], client.calls)
        self.assertEqual([report.target], sink.saved)

    def test_session_check_without_cookie_file_is_local_and_reports_both_names(self):
        report = check_session(ArchiveSettings())

        self.assertEqual(("z_c0", "d_c0"), report.cookie_diagnostic.missing)
        self.assertIsNone(report.login_status)

    def test_session_check_loads_configured_file_but_never_returns_cookie_values(self):
        secret = "must-not-appear-in-report"
        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(
                '{"z_c0": "' + secret + '", "d_c0": "another-secret"}',
                encoding="utf-8",
            )
            fake_client = Mock()
            fake_client.check_login.return_value = LoginStatus(
                authenticated=True,
                member_id="member",
                name="用户",
            )
            with patch(
                "zhihu_scraper.facade.ZhihuHttpClient",
                return_value=fake_client,
            ):
                report = check_session(ArchiveSettings(cookie_file=cookie_path))

        self.assertTrue(report.cookie_diagnostic.is_complete)
        self.assertTrue(report.login_status.authenticated)
        self.assertNotIn(secret, repr(report))
        fake_client.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
