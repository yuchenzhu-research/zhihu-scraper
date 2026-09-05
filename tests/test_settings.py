import json
import tempfile
import unittest
from pathlib import Path

from zhihu_scraper.settings import (
    ArchiveSettings,
    BrowserFallback,
    SettingsError,
    generate_default_settings,
    load_settings,
)


class ArchiveSettingsTests(unittest.TestCase):
    def test_request_pacing_defaults_are_generated_loaded_and_reported(self):
        defaults = ArchiveSettings()
        self.assertEqual(0.5, defaults.request_interval)
        self.assertEqual(0.5, defaults.request_jitter)

        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.toml"
            generate_default_settings(settings_path)
            generated = load_settings(settings_path)
        self.assertEqual(0.5, generated.request_interval)
        self.assertEqual(0.5, generated.request_jitter)

        configured = ArchiveSettings.from_mapping(
            {"network": {"request_interval": 2, "request_jitter": 0.25}}
        )
        self.assertEqual(2.0, configured.request_interval)
        self.assertEqual(0.25, configured.request_jitter)
        network = configured.to_safe_summary()["network"]
        self.assertEqual(2.0, network["request_interval"])
        self.assertEqual(0.25, network["request_jitter"])

    def test_request_pacing_requires_finite_numbers_between_zero_and_sixty(self):
        for name in ("request_interval", "request_jitter"):
            for value in (-0.1, 60.1, float("inf"), float("nan"), True, "0.5"):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(SettingsError, f"network.{name}"):
                        ArchiveSettings.from_mapping({"network": {name: value}})
                    with self.assertRaisesRegex(SettingsError, f"network.{name}"):
                        ArchiveSettings(**{name: value})
            for value in (0, 60):
                with self.subTest(name=name, allowed=value):
                    self.assertEqual(float(value), getattr(ArchiveSettings(**{name: value}), name))

    def test_defaults_favor_a_complete_local_archive_without_optional_features(self):
        settings = ArchiveSettings()

        self.assertEqual(settings.output_dir, Path("知乎归档"))
        self.assertTrue(settings.markdown)
        self.assertFalse(settings.html)
        self.assertFalse(settings.pdf)
        self.assertFalse(settings.comments)
        self.assertEqual(settings.comment_roots, 10)
        self.assertEqual(settings.comment_replies, 10)
        self.assertTrue(settings.media_download)
        self.assertIsNone(settings.cookie_file)
        self.assertIsNone(settings.proxy)
        self.assertEqual(settings.browser_fallback, BrowserFallback.AUTO)
        self.assertFalse(settings.headless)
        self.assertGreater(settings.timeout, 0)
        self.assertGreaterEqual(settings.retries, 0)
        self.assertGreater(settings.page_size, 0)

    def test_loads_all_supported_sections_and_expands_user_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.toml"
            settings_path.write_text(
                """
[archive]
output_dir = "~/my-zhihu"
markdown = false
html = true
pdf = true
comments = true
comment_roots = 8
comment_replies = 6
media_download = false

[network]
cookie_file = "~/.private/zhihu-cookies.json"
proxy = "http://user:password@127.0.0.1:7890"
timeout = 45.5
retries = 5
page_size = 30

[browser]
fallback = "never"
headless = true
cdp_url = "http://127.0.0.1:9222"
""".strip(),
                encoding="utf-8",
            )

            settings = load_settings(settings_path)

        self.assertEqual(settings.output_dir, Path("~/my-zhihu").expanduser())
        self.assertFalse(settings.markdown)
        self.assertTrue(settings.html)
        self.assertTrue(settings.pdf)
        self.assertTrue(settings.comments)
        self.assertEqual(settings.comment_roots, 8)
        self.assertEqual(settings.comment_replies, 6)
        self.assertFalse(settings.media_download)
        self.assertEqual(
            settings.cookie_file,
            Path("~/.private/zhihu-cookies.json").expanduser(),
        )
        self.assertEqual(settings.proxy, "http://user:password@127.0.0.1:7890")
        self.assertEqual(settings.timeout, 45.5)
        self.assertEqual(settings.retries, 5)
        self.assertEqual(settings.page_size, 30)
        self.assertEqual(settings.browser_fallback, BrowserFallback.NEVER)
        self.assertTrue(settings.headless)
        self.assertEqual(settings.cdp_url, "http://127.0.0.1:9222")

    def test_invalid_types_and_ranges_have_readable_chinese_errors(self):
        invalid_documents = (
            ('[archive]\ncomments = "yes"', "archive.comments", "布尔值"),
            ("[archive]\ncomment_roots = 0", "archive.comment_roots", "1"),
            ("[network]\ntimeout = -1", "network.timeout", "大于 0"),
            ("[network]\nretries = 11", "network.retries", "0 到 10"),
            ("[network]\npage_size = 101", "network.page_size", "1 到 100"),
            (
                '[network]\nproxy = "socks5://127.0.0.1:7890"',
                "network.proxy",
                "HTTP",
            ),
            ('[browser]\nfallback = "sometimes"', "browser.fallback", "auto"),
        )

        for document, field_name, expected_detail in invalid_documents:
            with self.subTest(field_name=field_name):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    settings_path = Path(temporary_directory) / "settings.toml"
                    settings_path.write_text(document, encoding="utf-8")

                    with self.assertRaises(SettingsError) as raised:
                        load_settings(settings_path)

                message = str(raised.exception)
                self.assertIn(field_name, message)
                self.assertIn(expected_detail, message)

    def test_loading_paths_does_not_create_archive_or_cookie_locations(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            output_dir = temporary_path / "not-created" / "archive"
            cookie_file = temporary_path / "not-created" / "cookies.json"
            settings_path = temporary_path / "settings.toml"
            settings_path.write_text(
                (
                    "[archive]\n"
                    f"output_dir = {json.dumps(str(output_dir))}\n"
                    "[network]\n"
                    f"cookie_file = {json.dumps(str(cookie_file))}\n"
                ),
                encoding="utf-8",
            )

            settings = load_settings(settings_path)

            self.assertEqual(settings.output_dir, output_dir)
            self.assertEqual(settings.cookie_file, cookie_file)
            self.assertFalse(output_dir.exists())
            self.assertFalse(cookie_file.parent.exists())

    def test_unknown_sections_and_fields_are_rejected(self):
        invalid_documents = (
            ("[archive]\nsqlite = true", "archive.sqlite"),
            ("[archive]\nhtlm = true", "archive.htlm"),
            ('[network]\nz_c0 = "secret"', "network.cookie_file"),
            ("[experimental]\nenabled = true", "experimental"),
        )

        for document, expected_detail in invalid_documents:
            with self.subTest(document=document):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    settings_path = Path(temporary_directory) / "settings.toml"
                    settings_path.write_text(document, encoding="utf-8")

                    with self.assertRaises(SettingsError) as raised:
                        load_settings(settings_path)

                self.assertIn(expected_detail, str(raised.exception))

    def test_generate_default_settings_never_overwrites_an_existing_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "nested" / "settings.toml"

            self.assertTrue(generate_default_settings(settings_path))
            generated = settings_path.read_text(encoding="utf-8")
            settings_path.write_text("keep = true", encoding="utf-8")

            self.assertFalse(generate_default_settings(settings_path))

            self.assertEqual(settings_path.read_text(encoding="utf-8"), "keep = true")
            self.assertIn("[archive]", generated)
            self.assertIn("html = false", generated)
            self.assertIn("[network]", generated)
            self.assertIn("[browser]", generated)
            self.assertNotIn("z_c0", generated)
            self.assertNotIn("d_c0", generated)

    def test_safe_summary_discloses_only_whether_secrets_are_configured(self):
        proxy = "http://account:do-not-print@proxy.example:7890"
        cookie_file = Path("/private/do-not-print/cookies.json")
        settings = ArchiveSettings(
            proxy=proxy,
            cookie_file=cookie_file,
            cdp_url="http://127.0.0.1:9222",
        )

        summary = settings.to_safe_summary()
        rendered = repr(summary)

        self.assertTrue(summary["network"]["proxy_configured"])
        self.assertTrue(summary["network"]["cookie_file_configured"])
        self.assertTrue(summary["browser"]["cdp_configured"])
        self.assertNotIn(proxy, rendered)
        self.assertNotIn(str(cookie_file), rendered)
        self.assertNotIn("do-not-print", rendered)


if __name__ == "__main__":
    unittest.main()
