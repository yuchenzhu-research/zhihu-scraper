import unittest
from pathlib import Path

from cli.app import app
from cli.manual_content import build_manual_text


REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_COMMANDS = {
    "batch",
    "check",
    "config",
    "creator",
    "fetch",
    "interactive",
    "manual",
    "monitor",
    "onboard",
    "query",
}
EXPECTED_DOC_SNIPPETS = (
    "zhihu onboard",
    "zhihu fetch",
    "zhihu creator",
    "zhihu batch",
    "zhihu monitor",
    "zhihu query",
    "zhihu interactive",
    "zhihu config --show",
    "zhihu check",
    "zhihu manual",
)


class CommandSurfaceTests(unittest.TestCase):
    def test_typer_registered_commands_match_expected_surface(self):
        registered = {command.name for command in app.registered_commands}
        self.assertEqual(registered, EXPECTED_COMMANDS)

    def test_manual_mentions_current_module_boundaries(self):
        manual_text = build_manual_text(Path("data"))
        self.assertIn("cli/config_view.py", manual_text)
        self.assertIn("cli/save_pipeline.py", manual_text)
        self.assertIn("core/scraper_payloads.py", manual_text)

    def test_bilingual_readmes_keep_core_command_snippets(self):
        readme_cn = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_en = (REPO_ROOT / "README_EN.md").read_text(encoding="utf-8")

        for snippet in EXPECTED_DOC_SNIPPETS:
            self.assertIn(snippet, readme_cn)
            self.assertIn(snippet, readme_en)


if __name__ == "__main__":
    unittest.main()
