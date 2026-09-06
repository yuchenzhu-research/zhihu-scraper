import io
import sys
import tempfile
import unittest
from contextlib import chdir, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from zhihu_scraper.application import ArchiveReport
from zhihu_scraper.archive import ArchiveReceipt
from zhihu_scraper.cli import run_cli
from zhihu_scraper.facade import LoginReport, LoginTimeoutError
from zhihu_scraper.http import CookieDiagnostic, LoginStatus
from zhihu_scraper.normalize import normalize_article


class NewCommandLineTests(unittest.TestCase):
    def test_login_accepts_cookie_destination_and_cdp_and_prints_config_guidance(self):
        output = io.StringIO()
        cookie_file = Path(".local/renewed-cookies.json")
        with patch(
            "zhihu_scraper.cli.login_session",
            return_value=LoginReport(cookie_file=cookie_file, authenticated=True),
        ) as login:
            with redirect_stdout(output):
                result = run_cli(
                    [
                        "login",
                        "--cookie-file",
                        str(cookie_file),
                        "--cdp",
                        "http://localhost:9222",
                    ]
                )

        self.assertEqual(0, result)
        settings = login.call_args.args[0]
        self.assertEqual(cookie_file, settings.cookie_file)
        self.assertEqual("http://localhost:9222", settings.cdp_url)
        self.assertIn("登录状态已验证", output.getvalue())
        self.assertIn("zhihu check --cookie-file", output.getvalue())
        self.assertIn("cookie_file =", output.getvalue())
        self.assertIn("zhihu fetch URL -s", output.getvalue())

    def test_login_without_settings_does_not_create_a_settings_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory, chdir(temporary_directory):
            with patch(
                "zhihu_scraper.cli.login_session",
                return_value=LoginReport(Path(".local/cookies.json"), True),
            ) as login:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(0, run_cli(["login"]))
            self.assertIsNone(login.call_args.args[0].cookie_file)
            self.assertEqual([], list(Path(".").iterdir()))

    def test_login_keeps_existing_settings_unchanged_and_reports_cancellation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.toml"
            original = '[network]\ncookie_file = ".local/existing.json"\n'
            settings_path.write_text(original, encoding="utf-8")
            for error, expected_exit in (
                (KeyboardInterrupt(), 130),
                (LoginTimeoutError("超时"), 1),
            ):
                with self.subTest(error=type(error).__name__):
                    with (
                        patch("zhihu_scraper.cli.login_session", side_effect=error) as login,
                        redirect_stdout(io.StringIO()),
                        redirect_stderr(io.StringIO()),
                    ):
                        self.assertEqual(
                            expected_exit, run_cli(["login", "-s", str(settings_path)])
                        )
                    self.assertEqual(
                        Path(".local/existing.json"), login.call_args.args[0].cookie_file
                    )
                    self.assertEqual(original, settings_path.read_text(encoding="utf-8"))

    def test_chinese_output_survives_windows_legacy_redirect_encoding(self):
        stdout_bytes = io.BytesIO()
        stderr_bytes = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_bytes, encoding="cp1252", errors="strict")
        stderr = io.TextIOWrapper(stderr_bytes, encoding="cp1252", errors="strict")

        try:
            with (
                patch.object(sys, "stdout", stdout),
                patch.object(
                    sys,
                    "stderr",
                    stderr,
                ),
            ):
                with self.assertRaises(SystemExit) as raised:
                    run_cli(["--help"])
                with patch(
                    "zhihu_scraper.cli.archive_url",
                    side_effect=RuntimeError("抓取失败"),
                ):
                    exit_code = run_cli(["fetch", "https://zhuanlan.zhihu.com/p/1"])
                stdout.flush()
                stderr.flush()

            self.assertEqual(0, raised.exception.code)
            self.assertEqual(1, exit_code)
            self.assertIn("把知乎文章", stdout_bytes.getvalue().decode("utf-8"))
            self.assertIn("错误：抓取失败", stderr_bytes.getvalue().decode("utf-8"))
        finally:
            stdout.detach()
            stderr.detach()

    def test_help_exposes_only_the_small_supported_command_surface(self):
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            run_cli(["--help"])

        self.assertEqual(0, raised.exception.code)
        rendered = output.getvalue()
        self.assertIn("fetch", rendered)
        self.assertIn("check", rendered)
        self.assertIn("init", rendered)
        self.assertIn("login", rendered)
        self.assertIn("zhihu fetch --html URL", rendered)
        self.assertIn("zhihu fetch --comments URL", rendered)
        self.assertNotIn("tui", rendered.casefold())
        self.assertNotIn("translate", rendered.casefold())

    def test_version_reports_the_current_installed_project_version(self):
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            run_cli(["--version"])

        self.assertEqual(0, raised.exception.code)
        self.assertEqual("zhihu 4.0.0", output.getvalue().strip())

    def test_fetch_applies_command_overrides_and_prints_readable_paths(self):
        receipt = ArchiveReceipt(
            entry_directory=Path("/archive/文章"),
            markdown_path=Path("/archive/文章/文章.md"),
            html_path=Path("/archive/文章/文章.html"),
        )
        report = ArchiveReport(
            target=normalize_article({"id": 1, "title": "文章", "content": "<p>正文</p>"}),
            receipt=receipt,
            used_browser=False,
        )
        output = io.StringIO()

        with patch("zhihu_scraper.cli.archive_url", return_value=report) as archive:
            with redirect_stdout(output):
                exit_code = run_cli(
                    [
                        "fetch",
                        "https://zhuanlan.zhihu.com/p/1",
                        "--output",
                        "/archive",
                        "--comments",
                        "--html",
                        "--no-media",
                        "--browser",
                        "never",
                    ]
                )

        self.assertEqual(0, exit_code)
        settings = archive.call_args.args[1]
        self.assertEqual(Path("/archive"), settings.output_dir)
        self.assertTrue(settings.comments)
        self.assertTrue(settings.html)
        self.assertFalse(settings.media_download)
        self.assertEqual("never", settings.browser_fallback.value)
        self.assertIn("归档完成：文章", output.getvalue())
        self.assertIn("HTTP/API", output.getvalue())
        self.assertNotIn("SQLite", output.getvalue())

    def test_fetch_without_comment_option_keeps_comments_disabled(self):
        receipt = ArchiveReceipt(
            entry_directory=Path("/archive/文章"),
            markdown_path=Path("/archive/文章/文章.md"),
            html_path=Path("/archive/文章/文章.html"),
        )
        report = ArchiveReport(
            target=normalize_article({"id": 1, "title": "文章", "content": "<p>正文</p>"}),
            receipt=receipt,
            used_browser=False,
        )

        with patch("zhihu_scraper.cli.archive_url", return_value=report) as archive:
            with redirect_stdout(io.StringIO()):
                exit_code = run_cli(["fetch", "https://zhuanlan.zhihu.com/p/1"])

        self.assertEqual(0, exit_code)
        self.assertFalse(archive.call_args.args[1].comments)
        self.assertFalse(archive.call_args.args[1].html)

    def test_no_html_overrides_a_settings_file_that_enables_html(self):
        receipt = ArchiveReceipt(
            entry_directory=Path("/archive/文章"),
            markdown_path=Path("/archive/文章/文章.md"),
            html_path=None,
        )
        report = ArchiveReport(
            target=normalize_article({"id": 1, "title": "文章", "content": "<p>正文</p>"}),
            receipt=receipt,
            used_browser=False,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.toml"
            settings_path.write_text("[archive]\nhtml = true\n", encoding="utf-8")
            with patch("zhihu_scraper.cli.archive_url", return_value=report) as archive:
                with redirect_stdout(io.StringIO()):
                    exit_code = run_cli(
                        [
                            "fetch",
                            "https://zhuanlan.zhihu.com/p/1",
                            "--settings",
                            str(settings_path),
                            "--no-html",
                        ]
                    )

        self.assertEqual(0, exit_code)
        self.assertFalse(archive.call_args.args[1].html)

    def test_check_reports_real_status_without_printing_identity_or_cookie_values(self):
        report = SimpleNamespace(
            cookie_diagnostic=CookieDiagnostic(missing=()),
            login_status=LoginStatus(
                authenticated=True,
                member_id="private-member-id",
                name="private-name",
            ),
        )
        output = io.StringIO()

        with patch("zhihu_scraper.cli.check_session", return_value=report):
            with redirect_stdout(output):
                exit_code = run_cli(["check"])

        rendered = output.getvalue()
        self.assertEqual(0, exit_code)
        self.assertIn("登录状态有效", rendered)
        self.assertNotIn("private-member-id", rendered)
        self.assertNotIn("private-name", rendered)

    def test_fetch_reports_nonfatal_media_failures_without_marking_archive_failed(self):
        receipt = ArchiveReceipt(
            entry_directory=Path("/archive/文章"),
            markdown_path=Path("/archive/文章/文章.md"),
            html_path=Path("/archive/文章/文章.html"),
        )
        failure = SimpleNamespace(display_message="正文媒体下载失败，已保留远程链接：image-1")
        report = ArchiveReport(
            target=normalize_article({"id": 1, "title": "文章", "content": "<p>正文</p>"}),
            receipt=receipt,
            used_browser=False,
            media_failures=(failure,),
        )
        output = io.StringIO()

        with patch("zhihu_scraper.cli.archive_url", return_value=report):
            with redirect_stdout(output):
                exit_code = run_cli(["fetch", "https://zhuanlan.zhihu.com/p/1"])

        self.assertEqual(0, exit_code)
        self.assertIn("媒体警告：1 个", output.getvalue())
        self.assertIn("image-1", output.getvalue())

    def test_init_never_overwrites_existing_settings(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "settings.toml"

            self.assertEqual(0, run_cli(["init", str(path)]))
            generated = path.read_text(encoding="utf-8")
            path.write_text("keep = true", encoding="utf-8")
            self.assertEqual(0, run_cli(["init", str(path)]))

            self.assertIn("[archive]", generated)
            self.assertEqual("keep = true", path.read_text(encoding="utf-8"))

    def test_errors_use_stderr_and_nonzero_exit_code(self):
        error_output = io.StringIO()

        with patch(
            "zhihu_scraper.cli.archive_url",
            side_effect=RuntimeError("抓取失败"),
        ):
            with redirect_stderr(error_output):
                exit_code = run_cli(["fetch", "https://zhuanlan.zhihu.com/p/1"])

        self.assertEqual(1, exit_code)
        self.assertIn("错误：抓取失败", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()


def test_pdf_flag_enables_output_and_reports_its_path(capsys):
    report = ArchiveReport(
        target=normalize_article({"id": 1, "title": "文章", "content": "<p>正文</p>"}),
        receipt=ArchiveReceipt(Path("archive"), None, None, pdf_path=Path("archive/文章.pdf")),
        used_browser=False,
    )
    with patch("zhihu_scraper.cli.archive_url", return_value=report) as archive:
        assert run_cli(["fetch", "https://zhuanlan.zhihu.com/p/1", "--pdf"]) == 0
    assert archive.call_args.args[1].pdf is True
    assert "PDF：" in capsys.readouterr().out


def test_no_pdf_overrides_persistent_pdf_choice(tmp_path):
    settings = tmp_path / "settings.toml"
    settings.write_text("[archive]\npdf = true\n", encoding="utf-8")
    report = ArchiveReport(
        target=normalize_article({"id": 1, "title": "文章", "content": "<p>正文</p>"}),
        receipt=ArchiveReceipt(Path("archive"), Path("archive/article.md"), None),
        used_browser=False,
    )
    with patch("zhihu_scraper.cli.archive_url", return_value=report) as archive:
        assert (
            run_cli(["fetch", "https://zhuanlan.zhihu.com/p/1", "-s", str(settings), "--no-pdf"])
            == 0
        )
    assert archive.call_args.args[1].pdf is False


def test_batch_cli_prints_saved_progress_before_a_later_failure(capsys, tmp_path):
    from zhihu_scraper.application import BatchProgress

    def archive(_url, _settings, *, progress):
        progress(BatchProgress("started", 0, 2, progress_path=tmp_path / "归档进度.md"))
        progress(BatchProgress("saved", 1, 2, current_title="已经完成的文章"))
        progress(BatchProgress("interrupted", 1, 2, progress_path=tmp_path / "归档进度.md"))
        raise RuntimeError("分页暂时不可用")

    with patch("zhihu_scraper.cli.archive_url", side_effect=archive):
        assert run_cli(["fetch", "https://www.zhihu.com/column/example"]) == 1

    output = capsys.readouterr()
    assert "归档完成" not in output.out
    assert "已保存 1 项" in output.err
    assert "已经完成的文章" in output.err
    assert "归档进度.md" in output.err
    assert "分页暂时不可用" in output.err
