from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class NewInstallContractTests(unittest.TestCase):
    def test_ci_covers_supported_operating_systems_and_python_versions(self) -> None:
        workflow = self._read(".github/workflows/ci.yml")

        for runner in ("ubuntu-latest", "windows-latest", "macos-latest"):
            with self.subTest(runner=runner):
                self.assertIn(runner, workflow)
        for version in ('"3.12"', '"3.13"', '"3.14"'):
            with self.subTest(version=version):
                self.assertIn(version, workflow)

        self.assertIn('python -m pip install -e ".[dev]"', workflow)
        self.assertIn("uv sync --locked --extra dev", workflow)
        self.assertIn("uv run --no-sync python -m pytest", workflow)
        self.assertIn("python -m pytest", workflow)
        self.assertIn("python -m ruff check", workflow)
        self.assertIn("python -m ruff format --check", workflow)
        self.assertIn("python -m mypy zhihu_scraper", workflow)
        self.assertIn("uv lock --check", workflow)
        self.assertIn("zhihu --help", workflow)
        self.assertIn("zhihu --version", workflow)
        self.assertIn("zhihu fetch --help", workflow)
        self.assertIn("zhihu check --help", workflow)
        self.assertIn("zhihu init --help", workflow)
        self.assertIn("playwright install --with-deps chromium", workflow)
        self.assertIn("fail-fast: false", workflow)
        self.assertRegex(
            workflow,
            r"uses: actions/checkout@[0-9a-f]{40}",
        )
        self.assertRegex(
            workflow,
            r"uses: actions/setup-python@[0-9a-f]{40}",
        )

    def test_ci_does_not_keep_obsolete_package_or_unittest_commands(self) -> None:
        workflow = self._read(".github/workflows/ci.yml")

        self.assertNotRegex(workflow, r"compileall\s+.*\b(?:cli|core)\b")
        self.assertNotIn("python -m unittest", workflow)
        self.assertNotIn("cli/app.py", workflow)

    def test_posix_installer_is_relocatable_and_fails_fast(self) -> None:
        script = self._read("scripts/install.sh")

        self.assertTrue(script.startswith("#!/usr/bin/env sh\n"))
        self.assertIn("set -eu", script)
        self.assertIn('dirname -- "$0"', script)
        self.assertIn('"$python_command" -m venv "$venv_dir"', script)
        self.assertIn('"$venv_python" -m pip install --upgrade pip', script)
        self.assertIn('"$venv_python" -m pip install -e .', script)
        self.assertIn('"$venv_python" -m playwright install chromium', script)
        self.assertIn('"$venv_python" -m playwright install --with-deps chromium', script)
        self.assertIn('case "$(uname -s)"', script)
        self.assertIn("zhihu --version", script)
        self.assertNotIn("[full]", script)

    def test_powershell_installer_is_relocatable_and_fails_fast(self) -> None:
        script = self._read("scripts/install.ps1")

        self.assertIn('$ErrorActionPreference = "Stop"', script)
        self.assertIn("Set-StrictMode -Version Latest", script)
        self.assertIn("$PSScriptRoot", script)
        self.assertIn("-m venv $VenvDir", script)
        self.assertIn("-m pip install --upgrade pip", script)
        self.assertRegex(script, re.compile(r"-m pip install -e \.\s*$", re.MULTILINE))
        self.assertRegex(
            script,
            re.compile(r"& \$VenvPython -m playwright install chromium\s*$", re.MULTILINE),
        )
        self.assertIn("zhihu --version", script)
        self.assertNotIn("[full]", script)

    def test_default_dependencies_include_the_browser_fallback_runtime(self) -> None:
        project = self._read("pyproject.toml")
        browser = self._read("zhihu_scraper/browser.py")
        runtime = project.split("[project.optional-dependencies]", 1)[0]

        self.assertRegex(runtime, r'"playwright>=.*"')
        self.assertNotRegex(project, r"(?m)^full\s*=")
        self.assertNotIn("zhihu-scraper[full]", browser)

    def test_project_has_one_current_version_and_command_entry_point(self) -> None:
        project = tomllib.loads(self._read("pyproject.toml"))["project"]

        self.assertEqual("4.0.0", project["version"])
        self.assertEqual(
            {"zhihu": "zhihu_scraper.cli:main"},
            project["scripts"],
        )
        self.assertFalse((REPO_ROOT / "cli").exists())

    def _read(self, relative_path: str) -> str:
        return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
