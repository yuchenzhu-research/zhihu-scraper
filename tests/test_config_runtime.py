import tempfile
import unittest
from pathlib import Path

from core.config import Config, resolve_project_path, summarize_text_for_logs
from core.config_runtime import ConfigLoader


class ConfigRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.loader = ConfigLoader()
        self.original_config = self.loader._config
        self.loader._config = None

    def tearDown(self):
        self.loader._config = self.original_config

    def test_loader_reads_explicit_yaml_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                "output:\n"
                "  directory: custom-data\n"
                "logging:\n"
                "  level: DEBUG\n",
                encoding="utf-8",
            )

            config = self.loader.load(config_path)

        self.assertIsInstance(config, Config)
        self.assertEqual(config.output.directory, "custom-data")
        self.assertEqual(config.logging.level, "DEBUG")

    def test_loader_missing_file_falls_back_to_defaults(self):
        config = self.loader.load(Path("/tmp/definitely-missing-config.yaml"))
        self.assertEqual(config.output.directory, "data")
        self.assertTrue(config.zhihu.cookies_required)

    def test_config_facade_reexports_path_and_log_helpers(self):
        project_path = resolve_project_path("data")
        summary = summarize_text_for_logs("secret-cookie", kind="cookie")

        self.assertTrue(project_path.is_absolute())
        self.assertIn("cookie_redacted", summary)


if __name__ == "__main__":
    unittest.main()
