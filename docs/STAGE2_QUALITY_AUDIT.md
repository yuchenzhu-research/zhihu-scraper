# Stage 2 Quality Audit

Branch: `test`  
Date: `2026-04-03`  
Scope: platform readiness, command surface, documentation drift, feature execution depth, and structural maintainability.

## Executive Summary

Stage 2 confirms that the repository is no longer in a "single-user demo only" state, but it is still not ready to claim smooth cross-platform operation.

The strongest areas are:

- The top-level CLI command surface is coherent and all public `--help` entrypoints are alive.
- `README.md` and `README_EN.md` now match the current direction: Textual TUI default, legacy fallback retained, and platform status stated honestly.
- The new TUI path already has basic regression coverage.

The weakest areas are:

- Cross-platform readiness is not yet backed by real validation. CI still only runs on Ubuntu and does not execute the unit test suite.
- The installation path is still Unix-first. `install.sh` is not a realistic Windows installation story.
- Runtime diagnostics are too raw. `zhihu check` currently dumps large Playwright failure output instead of a controlled summary.
- The CLI and core service layer are still concentrated in several oversized files, especially `cli/app.py`.

## Audit Evidence

The following evidence was collected during Stage 2:

- Public command surface from `cli/app.py`
- Runtime installer from `install.sh`
- dependency declaration from `pyproject.toml`
- CI definition from `.github/workflows/ci.yml`
- current docs in `README.md` and `README_EN.md`
- smoke runs:
  - `./zhihu --help`
  - `./zhihu fetch --help`
  - `./zhihu creator --help`
  - `./zhihu interactive --help`
  - `./zhihu manual --help`
  - `./zhihu config --show`
  - `./zhihu check`
- test runs:
  - `./.venv/bin/python -m unittest -q tests.test_cli_compat tests.test_tui_rebuild`

## Horizontal Audit

### 1. Platform Readiness

#### macOS

Status: usable, but still noisy.

What is working:

- primary developer flow runs here
- `zhihu` launcher works
- TUI and CLI help surface both work

What is still weak:

- `zhihu check` emits a long Playwright launch crash log instead of a summarized diagnosis
- browser fallback still depends on environment-specific Chromium launch behavior

Why it matters:

- macOS is currently the main maintained platform, so raw failure logs here will shape user confidence and issue volume

#### Linux

Status: partially hardened, not fully validated.

What is working:

- shell-friendly output directory naming has already improved Linux usability
- the main CLI surface is Unix-friendly

What is still weak:

- no Linux-specific installation or regression matrix in CI
- the project depends on Unix shell assumptions in several places
- the installer and launcher guidance remain more Bash/Zsh-oriented than distro-agnostic

Why it matters:

- Linux is the most likely secondary platform for CLI-heavy users, and it is the easiest place for path, shell, and dependency issues to accumulate silently

#### Windows

Status: documentation-level acknowledgment only.

Current blockers:

- `install.sh` is the official installer, but it is Bash-only
- launcher guidance assumes `~/.local/bin`
- several docs and commands still reference `.venv/bin/python`

Why it matters:

- the repository currently states Windows still needs fuller validation, and that statement is accurate
- without a Windows setup path, "three-platform support" is not an engineering reality yet

### 2. Command Surface Audit

Current public commands:

- `manual`
- `onboard`
- `fetch`
- `batch`
- `creator`
- `monitor`
- `query`
- `interactive`
- `config`
- `check`

Observed status:

- all public `--help` entrypoints tested in Stage 2 are alive
- `interactive` correctly describes the Textual TUI as the default path
- `config --show` renders successfully
- `check` completes, but error presentation quality is weak

Assessment:

- command discoverability is now reasonably good
- command stability is better than before
- operational clarity is still dragged down by raw low-level diagnostics

### 3. Documentation Drift Audit

Current status:

- `README.md` and `README_EN.md` are materially aligned with the current product direction
- both READMEs mention:
  - Textual TUI as default interactive path
  - `interactive --legacy` as fallback
  - platform status by `macOS / Linux / Windows`
  - dependency resync guidance after branch switching

Remaining gaps:

- the docs are honest about Windows not being fully validated, but there is still no dedicated Windows runbook
- README is ahead of CI reality: cross-platform intent is documented, but validation is not yet automated
- the built-in manual has not yet been audited line-by-line against the latest install/config guidance

Assessment:

- README drift has improved significantly
- documentation governance is better, but not yet closed-loop

## Vertical Audit

### 1. Feature Execution Depth

Validated in Stage 2:

- CLI command help surface
- configuration display
- environment check path
- TUI regression tests
- compatibility tests

Not yet fully validated in Stage 2:

- full fetch flow across answer, article, question, creator, batch, and monitor on all target platforms
- browser fallback behavior across OSes
- onboarding end-to-end behavior after a fresh install on each supported platform

Assessment:

- the project now has a stronger surface than before, but execution depth is still thinner than the README ambition

### 2. Configuration and Runtime Compatibility

Observed behavior:

- `config --show` still reports a split between configured local paths and currently active historical cookie paths
- this is intentional compatibility behavior, but it also shows migration work is not complete

Assessment:

- compatibility logic is becoming more robust
- the runtime path model is still transitional and should be made more explicit in later phases

### 3. Test and CI Coverage

Observed behavior:

- local test suite `tests.test_cli_compat` and `tests.test_tui_rebuild` passes
- test output is polluted by a user-facing optional dependency warning about `questionary`
- CI does not run the unit tests
- CI only runs on `ubuntu-latest`

Assessment:

- local regression coverage now exists
- automated enforcement is still weak

### 4. Structural Maintainability

Current hotspot sizes:

- `cli/app.py`: 1672 lines
- `core/scraper.py`: 698 lines
- `core/config.py`: 642 lines
- `core/converter.py`: 478 lines
- `core/errors.py`: 354 lines

Assessment:

- `cli/app.py` remains the largest structural risk
- `cli/tui/` is a positive move because it prevented more interactive logic from being piled into `cli/app.py`
- the repository has not crossed into unmanageable sprawl yet, but it will if CLI, config, and persistence orchestration continue growing in-place

## Problem Matrix

| Severity | Area | Problem | Why it matters | Evidence | Phase 3+ direction |
| --- | --- | --- | --- | --- | --- |
| P0 | CI / platform | CI only validates Ubuntu and does not run unit tests | cross-platform claims are not enforced | `.github/workflows/ci.yml` | add a matrix for macOS/Linux and execute unit tests |
| P0 | Installer | official install path is Bash-only | Windows path is not operational | `install.sh` | define a Windows setup path or explicitly scope support |
| P0 | Diagnostics | `zhihu check` dumps raw Playwright crash output | user-facing troubleshooting quality is poor | runtime `./zhihu check` | replace raw dump with summarized diagnostic blocks |
| P1 | Tests | user-facing optional dependency warning leaks into test output | test isolation is weak and output is noisy | `tests.test_cli_compat`, `tests.test_tui_rebuild` run | suppress or mock optional dependency messaging in automated tests |
| P1 | Docs / ops | built-in manual is not yet re-audited against latest README and install guidance | drift can reappear even if README is current | `cli/app.py`, READMEs | audit manual/help/install together in Stage 3 |
| P1 | Config migration | active runtime cookie paths can still differ from configured local paths | compatibility is preserved, but operator understanding is weaker | `./zhihu config --show` | formalize migration messaging and deprecation windows |
| P1 | Structure | `cli/app.py` remains oversized | future features will continue to accumulate in a single file | file size audit | split launcher/manual/onboarding/save orchestration |
| P2 | Windows | Windows status is documented but not operationalized | platform story remains incomplete | README + installer evidence | add Windows runbook after CI and packaging groundwork |
| P2 | Linux | Linux shell behavior is improved but not systematically tested | regressions may slip in | current docs and fixes | add Linux smoke scenarios beyond help output |

## Phase 2 Conclusion

Stage 2 should be considered successful.

Reason:

- the project now has a coherent public surface
- the documentation is much closer to the current implementation
- the new TUI path is real and tested
- the remaining problems are now concentrated and legible, not vague

But Stage 2 also makes one thing clear:

- the next priority is not adding more features
- the next priority is operational hardening and structural cleanup

## Stage 3 Entry Criteria

Stage 3 should begin with these items in order:

1. reduce noisy and raw diagnostics in `check` and test output
2. add a real CI validation step for the existing unit tests
3. define platform support boundaries more concretely, especially Windows
4. start splitting `cli/app.py` by responsibility rather than adding more command logic in place

