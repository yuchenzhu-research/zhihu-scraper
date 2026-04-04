import unittest
from pathlib import Path

import tomllib


REPO_ROOT = Path(__file__).resolve().parent.parent


class InstallContractTests(unittest.TestCase):
    def test_pyproject_exposes_expected_console_entrypoint(self):
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        scripts = pyproject["project"]["scripts"]
        self.assertEqual(scripts["zhihu"], "cli.app:main")

    def test_install_script_keeps_editable_full_install_and_runtime_init(self):
        install_script = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('pip install -e ".[full]"', install_script)
        self.assertIn('cli/app.py check', install_script)
        self.assertIn('install_global_launcher', install_script)
        self.assertIn('.local/cookies.json', install_script)
        self.assertIn('sys.version_info >= (3, 14)', install_script)
        self.assertNotIn('cli/app.py check || true', install_script)

    def test_platform_docs_reference_windows_runbook(self):
        platform_doc = (REPO_ROOT / "docs/PLATFORM_SUPPORT.md").read_text(encoding="utf-8")
        windows_runbook = (REPO_ROOT / "docs/WINDOWS_RUNBOOK.md").read_text(encoding="utf-8")
        dependency_map = (REPO_ROOT / "docs/dependency-map.md").read_text(encoding="utf-8")

        self.assertIn("docs/WINDOWS_RUNBOOK.md", platform_doc)
        self.assertIn("pip install -e .", platform_doc)
        self.assertIn('pip install -e ".[full]"', platform_doc)
        self.assertIn("Windows", windows_runbook)
        self.assertIn("python -m pip install -e .", windows_runbook)
        self.assertIn("python -m pip install -e \"[full]\"", windows_runbook.replace(".[full]", "[full]"))
        self.assertIn("python -m playwright install chromium", windows_runbook)
        self.assertIn("pip install -e .", dependency_map)
        self.assertIn('pip install -e ".[full]"', dependency_map)


if __name__ == "__main__":
    unittest.main()
