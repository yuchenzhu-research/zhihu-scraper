import unittest
from pathlib import Path

from cli.config_view import build_config_snapshot, render_config_panel
from core.config import Config
from core.cookie_manager import RuntimePathResolution


class ConfigViewTests(unittest.TestCase):
    def test_build_config_snapshot_resolves_paths_and_modes(self):
        cfg = Config.from_dict(
            {
                "zhihu": {
                    "cookies": {
                        "file": ".local/cookies.json",
                        "pool_dir": ".local/cookie_pool",
                        "required": True,
                    },
                    "browser": {"headless": False},
                },
                "crawler": {"retry": {"max_attempts": 5}, "images": {"concurrency": 6}},
                "output": {"directory": "data"},
                "logging": {"file": ".local/logs/app.log", "level": "DEBUG"},
            }
        )

        snapshot = build_config_snapshot(
            cfg=cfg,
            config_path=Path("/repo/config.yaml"),
            resolve_project_path=lambda raw: Path("/repo") / raw,
            describe_cookie_file_path=lambda raw: RuntimePathResolution(
                configured_path=Path("/repo") / raw,
                active_path=Path("/active") / Path(raw).name,
                legacy_path=Path("/repo/cookies.json"),
                used_legacy_fallback=True,
            ),
            describe_cookie_pool_dir=lambda raw: RuntimePathResolution(
                configured_path=Path("/repo") / raw,
                active_path=Path("/pool") / Path(raw).name,
                legacy_path=Path("/repo/cookie_pool"),
                used_legacy_fallback=False,
            ),
        )

        self.assertEqual(snapshot.output_directory, "data")
        self.assertEqual(snapshot.browser_mode, "Visible / 有头")
        self.assertEqual(snapshot.retry_attempts, 5)
        self.assertEqual(snapshot.image_concurrency, 6)
        self.assertEqual(snapshot.configured_cookie_path, Path("/repo/.local/cookies.json"))
        self.assertEqual(snapshot.active_cookie_path, Path("/active/cookies.json"))
        self.assertEqual(snapshot.configured_pool_dir, Path("/repo/.local/cookie_pool"))
        self.assertTrue(snapshot.cookie_file_legacy_fallback)
        self.assertFalse(snapshot.cookie_pool_legacy_fallback)

    def test_render_config_panel_contains_key_labels(self):
        cfg = Config.from_dict({"output": {"directory": "data"}})
        snapshot = build_config_snapshot(
            cfg=cfg,
            config_path=Path("/repo/config.yaml"),
            resolve_project_path=lambda raw: Path("/repo") / raw,
            describe_cookie_file_path=lambda raw: RuntimePathResolution(
                configured_path=Path("/repo") / raw,
                active_path=Path("/repo") / raw,
                legacy_path=Path("/repo/cookies.json"),
                used_legacy_fallback=False,
            ),
            describe_cookie_pool_dir=lambda raw: RuntimePathResolution(
                configured_path=Path("/repo") / raw,
                active_path=Path("/repo") / raw,
                legacy_path=Path("/repo/cookie_pool"),
                used_legacy_fallback=False,
            ),
        )
        rendered = render_config_panel(snapshot)
        text = rendered.renderable.plain

        self.assertIn("Config Path", text)
        self.assertIn("Output Directory", text)
        self.assertIn("Active Cookie Pool", text)
        self.assertIn("Cookie Path Status", text)
        self.assertIn("Cookie Rotation", text)


if __name__ == "__main__":
    unittest.main()
