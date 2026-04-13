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

    def test_readmes_keep_textual_tui_wording(self):
        readme_cn = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_en = (REPO_ROOT / "README_EN.md").read_text(encoding="utf-8")

        self.assertIn("Textual TUI", readme_cn)
        self.assertIn("Textual TUI", readme_en)
        self.assertIn("全屏工作台", readme_cn)
        self.assertIn("full-screen workbench", readme_en)
        self.assertIn("协议优先", readme_cn)
        self.assertIn("protocol-first", readme_en)

    def test_manual_mentions_platform_boundary_and_current_entry_flow(self):
        manual_text = build_manual_text(Path("data"))
        self.assertIn("docs/PLATFORM_SUPPORT.md", manual_text)
        self.assertIn("cli/launcher_flow.py", manual_text)
        self.assertIn("--legacy", manual_text)
        self.assertIn("opens the default Textual workbench directly", manual_text)
        self.assertIn("zhihu onboard", manual_text)

    def test_manual_mentions_monitor_pointer_rule_for_unsupported_items(self):
        manual_text = build_manual_text(Path("data"))
        self.assertIn("unsupported-only new collection items still advance the pointer", manual_text)
        self.assertIn("Content Key (type:id)", manual_text)
        self.assertIn("configured vs active cookie/pool paths", manual_text)

    def test_governance_docs_reference_constitution_and_validation_baseline(self):
        agents_text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        manual_text = (REPO_ROOT / "MANUAL.md").read_text(encoding="utf-8")
        baseline_text = (REPO_ROOT / "docs" / "VALIDATION_BASELINE.md").read_text(encoding="utf-8")

        self.assertTrue((REPO_ROOT / "CONSTITUTION.md").exists())
        self.assertIn("CONSTITUTION.md", agents_text)
        self.assertIn("CONSTITUTION.md", manual_text)
        self.assertIn("docs/VALIDATION_BASELINE.md", agents_text)
        self.assertIn("docs/VALIDATION_BASELINE.md", manual_text)
        self.assertIn("tests.test_docs_sync", agents_text)
        self.assertIn("tests.test_command_surface", agents_text)
        self.assertIn(".github/workflows/ci.yml", baseline_text)

    def test_workflow_doc_mentions_query_identity_and_monitor_pointer_rules(self):
        workflow_text = (REPO_ROOT / "docs" / "workflows.md").read_text(encoding="utf-8")

        self.assertIn("content_key = type:id", workflow_text)
        self.assertIn("unsupported 新条目", workflow_text)
        self.assertIn("configured path / active path", workflow_text)

    def test_docs_use_validation_baseline_instead_of_stage_matrix(self):
        for rel_path in (
            "docs/workflows.md",
            "docs/WINDOWS_RUNBOOK.md",
            "docs/VALIDATION_BASELINE.md",
        ):
            text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
            self.assertNotIn("STAGE5_VALIDATION_MATRIX", text)


if __name__ == "__main__":
    unittest.main()
