import tempfile
import unittest
from unittest.mock import patch

import typer

import cli.optional_deps as optional_deps
from cli.app import _get_questionary, build_output_folder_name
from cli.healthcheck import summarize_playwright_failure
from core.config import Config
from core.monitor import CollectionMonitor
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


class MonitorContractTests(unittest.TestCase):
    def test_collection_monitor_counts_unsupported_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.monitor.ZhihuAPIClient") as mock_client_cls:
                mock_client = mock_client_cls.return_value
                mock_client.get_collection_page.return_value = {
                    "data": [
                        {"content": {"id": "900", "type": "video", "title": "Unsupported"}},
                        {
                            "content": {
                                "id": "901",
                                "type": "answer",
                                "question": {"id": "12", "title": "Demo Question"},
                            }
                        },
                    ],
                    "paging": {"is_end": True},
                }

                monitor = CollectionMonitor(data_dir=tmpdir)
                delta = monitor.get_new_items("78170682")

        self.assertTrue(delta.has_new_activity)
        self.assertTrue(delta.has_supported_items)
        self.assertEqual(delta.next_pointer, "900")
        self.assertEqual(delta.unseen_count, 2)
        self.assertEqual(delta.unsupported_count, 1)
        self.assertEqual(len(delta.items), 1)
        self.assertEqual(delta.items[0]["url"], "https://www.zhihu.com/question/12/answer/901")

    def test_collection_monitor_clears_pointer_when_head_is_already_known(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.monitor.ZhihuAPIClient") as mock_client_cls:
                mock_client = mock_client_cls.return_value
                mock_client.get_collection_page.return_value = {
                    "data": [
                        {
                            "content": {
                                "id": "known-id",
                                "type": "answer",
                                "question": {"id": "12", "title": "Demo Question"},
                            }
                        }
                    ],
                    "paging": {"is_end": True},
                }

                monitor = CollectionMonitor(data_dir=tmpdir)
                monitor.state["78170682"] = "known-id"
                delta = monitor.get_new_items("78170682")

        self.assertFalse(delta.has_new_activity)
        self.assertFalse(delta.has_supported_items)
        self.assertIsNone(delta.next_pointer)
        self.assertEqual(delta.unseen_count, 0)
        self.assertEqual(delta.unsupported_count, 0)
        self.assertEqual(delta.items, ())


if __name__ == "__main__":
    unittest.main()
