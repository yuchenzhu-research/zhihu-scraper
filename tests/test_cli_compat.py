import unittest
from unittest.mock import patch

import typer

from cli.app import _get_questionary, build_output_folder_name
from core.config import Config
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
        with patch("cli.app.importlib.import_module", side_effect=ModuleNotFoundError):
            with self.assertRaises(typer.Exit):
                _get_questionary()


if __name__ == "__main__":
    unittest.main()
