import unittest
from pathlib import Path

from cli.manual_content import build_manual_text


REPO_ROOT = Path(__file__).resolve().parent.parent


class DocsSyncTests(unittest.TestCase):
    def test_readmes_reference_platform_support_boundary(self):
        readme_cn = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_en = (REPO_ROOT / "README_EN.md").read_text(encoding="utf-8")

        self.assertIn("docs/PLATFORM_SUPPORT.md", readme_cn)
        self.assertIn("docs/PLATFORM_SUPPORT.md", readme_en)

    def test_readmes_keep_textual_tui_and_legacy_fallback_wording(self):
        readme_cn = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_en = (REPO_ROOT / "README_EN.md").read_text(encoding="utf-8")

        self.assertIn("Textual TUI", readme_cn)
        self.assertIn("interactive --legacy", readme_cn)
        self.assertIn("Textual TUI", readme_en)
        self.assertIn("interactive --legacy", readme_en)

    def test_manual_mentions_platform_boundary_and_launcher_flow(self):
        manual_text = build_manual_text(Path("data"))
        self.assertIn("docs/PLATFORM_SUPPORT.md", manual_text)
        self.assertIn("cli/launcher_flow.py", manual_text)
        self.assertIn("--legacy", manual_text)

    def test_manual_mentions_monitor_pointer_rule_for_unsupported_items(self):
        manual_text = build_manual_text(Path("data"))
        self.assertIn("unsupported-only new collection items still advance the pointer", manual_text)


if __name__ == "__main__":
    unittest.main()
