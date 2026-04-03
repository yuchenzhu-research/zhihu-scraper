import unittest
from pathlib import Path
from unittest.mock import patch

import typer

import cli.optional_deps as optional_deps
from cli.app import _get_questionary, build_output_folder_name
from cli.healthcheck import collect_environment_checks, summarize_playwright_failure
from core.config import Config
from core.cookie_manager import RuntimePathResolution
from core.utils import sanitize_filename


class ConfigCompatibilityTests(unittest.TestCase):
    def test_output_download_images_is_accepted_for_backward_compatibility(self):
        config = Config.from_dict(
            {
                "output": {
                    "directory": "data",
                    "folder_format": "[{date}] {title}",
                    "download_images": True,
                }
            }
        )
        self.assertEqual(config.output.directory, "data")
        self.assertEqual(config.output.folder_format, "[{date}] {title}")
        self.assertTrue(config.output.download_images)

    def test_build_output_folder_name_is_shell_safe(self):
        folder = build_output_folder_name(
            "2026-03-31",
            "如何看待伊朗驻华大使馆认为日本是二战受害者？",
            "玄睛",
            "answer-2022365612303741181",
        )
        self.assertIn("2026-03-31", folder)
        self.assertIn("answer-2022365612303741181", folder)
        self.assertNotIn("[", folder)
        self.assertNotIn("]", folder)
        self.assertNotIn("(", folder)
        self.assertNotIn(")", folder)
        self.assertNotIn(" ", folder)

    def test_shell_safe_filename_removes_common_shell_metacharacters(self):
        value = sanitize_filename("[draft] hello (world) & more", shell_safe=True)
        self.assertEqual(value, "draft_hello_world_more")


class LauncherDependencyTests(unittest.TestCase):
    def test_questionary_missing_raises_clean_exit(self):
        with patch.object(optional_deps.importlib, "import_module", side_effect=ModuleNotFoundError):
            with patch.object(optional_deps.sys.stderr, "isatty", return_value=False):
                with patch.object(optional_deps, "rprint") as mocked_print:
                    with self.assertRaises(typer.Exit):
                        _get_questionary()
                    mocked_print.assert_not_called()

    def test_questionary_missing_interactive_tty_prints_guidance(self):
        with patch.object(optional_deps.importlib, "import_module", side_effect=ModuleNotFoundError):
            with patch.object(optional_deps.sys.stderr, "isatty", return_value=True):
                with patch.object(optional_deps, "rprint") as mocked_print:
                    with self.assertRaises(typer.Exit):
                        _get_questionary()
                    self.assertGreaterEqual(mocked_print.call_count, 1)


class HealthcheckSummaryTests(unittest.TestCase):
    def test_playwright_permission_failure_is_summarized(self):
        detail, hint = summarize_playwright_failure(
            RuntimeError(
                "BrowserType.launch: Target page, context or browser has been closed\n"
                "[FATAL] bootstrap_check_in org.chromium.Chromium: Permission denied (1100)"
            )
        )
        self.assertIn("Chromium", detail)
        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertIn("受限沙箱", hint)

    def test_playwright_missing_binary_failure_is_summarized(self):
        detail, hint = summarize_playwright_failure(RuntimeError("Executable doesn't exist at /tmp/chromium"))
        self.assertIn("Playwright 浏览器未安装完整", detail)
        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertIn("playwright install chromium", hint)

    def test_collect_environment_checks_reports_legacy_cookie_fallback(self):
        cfg = Config.from_dict(
            {
                "zhihu": {
                    "cookies": {
                        "file": ".local/cookies.json",
                        "pool_dir": ".local/cookie_pool",
                        "required": True,
                    }
                }
            }
        )
        with patch("cli.healthcheck.get_config", return_value=cfg):
            with patch("core.cookie_manager.has_real_cookie_values", return_value=True):
                with patch("core.cookie_manager.count_available_cookie_sources", return_value=2):
                    with patch(
                        "core.cookie_manager.describe_cookie_file_path",
                        return_value=RuntimePathResolution(
                            configured_path=Path("/repo/.local/cookies.json"),
                            active_path=Path("/repo/cookies.json"),
                            legacy_path=Path("/repo/cookies.json"),
                            used_legacy_fallback=True,
                        ),
                    ):
                        with patch(
                            "core.cookie_manager.describe_cookie_pool_dir",
                            return_value=RuntimePathResolution(
                                configured_path=Path("/repo/.local/cookie_pool"),
                                active_path=Path("/repo/.local/cookie_pool"),
                                legacy_path=Path("/repo/cookie_pool"),
                                used_legacy_fallback=False,
                            ),
                        ):
                            with patch(
                                "cli.healthcheck.asyncio.run",
                                side_effect=lambda coro: coro.close(),
                            ):
                                items = collect_environment_checks()

        compatibility = next(item for item in items if item.label == "Cookie 路径兼容 / Cookie path compatibility")
        self.assertEqual(compatibility.status, "warn")
        self.assertIn("configured /repo/.local/cookies.json -> active /repo/cookies.json", compatibility.detail)
        self.assertIsNotNone(compatibility.hint)
        assert compatibility.hint is not None
        self.assertIn(".local/", compatibility.hint)


if __name__ == "__main__":
    unittest.main()
