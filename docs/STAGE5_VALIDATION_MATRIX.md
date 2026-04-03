# Stage 5 Validation Matrix

阶段五的目标不是继续堆功能，而是把“哪些能力必须每次都能被验证”固定下来，减少后续重构时的文档漂移和命令面回归。

## Current Validation Layers

1. Static syntax
- `python -m compileall cli core`
- `python -m py_compile` for newly split modules

2. Unit / regression tests
- CLI compatibility: `tests.test_cli_compat`
- docs/manual drift: `tests.test_docs_sync`
- command surface: `tests.test_command_surface`
- TUI regression: `tests.test_tui_rebuild`
- save pipeline: `tests.test_save_pipeline`
- config display: `tests.test_config_view`
- scraper payload normalization: `tests.test_scraper_payloads`
- scraper result contracts: `tests.test_scraper_contracts`
- config schema parsing: `tests.test_config_schema`

3. CLI smoke
- `python cli/app.py --help`
- `python cli/app.py manual --help`
- `python cli/app.py onboard --help`
- `python cli/app.py fetch --help`
- `python cli/app.py batch --help`
- `python cli/app.py creator --help`
- `python cli/app.py monitor --help`
- `python cli/app.py query --help`
- `python cli/app.py interactive --help`
- `python cli/app.py config --help`
- `python cli/app.py check --help`

## Guardrails

- `README.md`, `README_EN.md`, built-in `manual`, and command registration should evolve together.
- New CLI-facing modules should get at least one focused regression test before large follow-up refactors.
- CI should validate both import/compile safety and command-surface availability on every PR.

## Next Hardening Targets

- Add installer / editable-install smoke coverage for dependency drift.
- Add a Linux-oriented path behavior check for shell-sensitive output names.
- Add a Windows runbook once the install path is stable enough to automate.
