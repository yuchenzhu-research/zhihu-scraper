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
        self.assertIn("cli/archive_execution.py", manual_text)
        self.assertIn("cli/config_view.py", manual_text)
        self.assertIn("cli/save_pipeline.py", manual_text)
        self.assertIn("core/scraper_payloads.py", manual_text)
        self.assertIn("Textual TUI", manual_text)
        self.assertIn("home launcher", manual_text)

    def test_tui_and_legacy_use_execution_bridge_instead_of_cli_app_privates(self):
        runner_text = (REPO_ROOT / "cli" / "tui" / "runner.py").read_text(encoding="utf-8")
        legacy_text = (REPO_ROOT / "cli" / "interactive_legacy.py").read_text(encoding="utf-8")

        self.assertIn("from cli.archive_execution import fetch_and_save_result", runner_text)
        self.assertNotIn("from cli.app import _fetch_and_save_result", runner_text)
        self.assertIn("from cli.archive_execution import fetch_and_save", legacy_text)
        self.assertNotIn("from cli.app import _fetch_and_save", legacy_text)

    def test_launcher_marks_textual_tui_as_recommended_path(self):
        launcher_text = (REPO_ROOT / "cli" / "launcher_flow.py").read_text(encoding="utf-8")

        self.assertIn("Textual TUI 归档工作台（推荐）", launcher_text)
        self.assertIn("`zhihu interactive` 会直达推荐的 Textual TUI", launcher_text)
        self.assertIn("`zhihu interactive --legacy` 仅用于兼容回退", launcher_text)

    def test_cli_app_no_longer_keeps_dead_save_or_batch_helpers(self):
        app_text = (REPO_ROOT / "cli" / "app.py").read_text(encoding="utf-8")

        self.assertNotIn("def print_result(", app_text)
        self.assertNotIn("def build_output_folder_name(", app_text)
        self.assertNotIn("def resolve_entries_output_dir(", app_text)
        self.assertNotIn("def resolve_creator_output_dir(", app_text)
        self.assertNotIn("def _batch_concurrent(", app_text)

    def test_tui_runner_reuses_workflow_scrape_config_helper(self):
        runner_text = (REPO_ROOT / "cli" / "tui" / "runner.py").read_text(encoding="utf-8")

        self.assertIn("build_scrape_config_for_url", runner_text)
        self.assertNotIn("def _build_scrape_config(", runner_text)

    def test_bilingual_readmes_keep_core_command_snippets(self):
        readme_cn = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_en = (REPO_ROOT / "README_EN.md").read_text(encoding="utf-8")

        for snippet in EXPECTED_DOC_SNIPPETS:
            self.assertIn(snippet, readme_cn)
            self.assertIn(snippet, readme_en)


if __name__ == "__main__":
    unittest.main()
