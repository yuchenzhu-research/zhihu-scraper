# Stage 6 Release Review

阶段六的目标是把阶段一到五形成的治理、重构和验证成果收束成一份可合并、可评审、可回退的总审查材料。

## Branch Baseline

- current branch: `test`
- current HEAD: `5aab82e`
- comparison target: `main` / `origin/main`
- `test` is ahead of `main` by the staged governance + refactor commits since `4b645ca`

## What Changed Since `main`

### CLI layer

- `cli/app.py` shrank from a mixed command + save + manual + config surface into a thinner command router
- new modules:
  - `cli/launcher_flow.py`
  - `cli/manual_content.py`
  - `cli/save_pipeline.py`
  - `cli/config_view.py`
  - `cli/healthcheck.py`
  - `cli/optional_deps.py`

### Core layer

- `core/structlog_compat.py` adds fallback behavior when `structlog` is unavailable
- `core/scraper_payloads.py` isolates payload normalization away from the fetch loop
- `core/browser_fallback.py`, `core/config.py`, `core/errors.py`, `core/utils.py`, and `core/scraper.py` contain targeted compatibility / boundary updates, not a full rewrite

### Docs / governance

- stage docs:
  - `docs/STAGE1_SKILL_FOUNDATION.md`
  - `docs/STAGE2_QUALITY_AUDIT.md`
  - `docs/STAGE5_VALIDATION_MATRIX.md`
  - `docs/STAGE6_RELEASE_REVIEW.md`
  - `docs/STAGE6_ISSUE_REPLY_TEMPLATES.md`
  - `docs/STAGE6_MERGE_PLAYBOOK.md`
- platform / install docs:
  - `docs/PLATFORM_SUPPORT.md`
  - `docs/WINDOWS_RUNBOOK.md`
- bilingual README alignment continued

### Tests / CI

- added focused regression tests:
  - `tests.test_cli_compat`
  - `tests.test_docs_sync`
  - `tests.test_command_surface`
  - `tests.test_tui_rebuild`
  - `tests.test_save_pipeline`
  - `tests.test_config_view`
  - `tests.test_scraper_payloads`
  - `tests.test_install_contract`
- CI now runs unit tests plus a broader CLI help smoke matrix on `ubuntu-latest` and `macos-latest`

## Phase Completion Summary

### Stage 1

- skill foundation and repository boundary cleanup
- consolidated references / governance structure

### Stage 2

- produced the formal quality audit
- identified platform, command-surface, docs, and large-file risks

### Stage 3

- reduced noisy environment checks
- added optional dependency handling
- started CLI splitting (`manual_content`, `launcher_flow`)
- clarified platform support boundaries

### Stage 4

- extracted save orchestration into `cli/save_pipeline.py`
- extracted config presentation into `cli/config_view.py`
- extracted scraper payload normalization into `core/scraper_payloads.py`
- reduced file size pressure in `cli/app.py` and `core/scraper.py`

### Stage 5

- added validation matrix
- added command-surface / install-contract tests
- broadened CI smoke coverage
- added explicit Windows runbook

## Validation Status

At the end of stage 6 review, the following checks pass locally:

- `python -m unittest -q tests.test_cli_compat tests.test_docs_sync tests.test_command_surface tests.test_tui_rebuild tests.test_save_pipeline tests.test_config_view tests.test_scraper_payloads tests.test_install_contract`
- CLI smoke:
  - `app.py --help`
  - `interactive --help`
  - `config --help`
  - `check`

## Remaining Risks

These items are still open and should be treated as post-merge follow-up rather than blockers for the current governance tranche:

1. `core/config.py` is still large and mixes schema, compatibility, logging setup, and singleton loading.
2. `core/scraper.py` is smaller than before, but still holds pagination, transport flow, throttling, and image download in one file.
3. Windows remains a documented manual path, not a fully automated CI-tested platform.
4. Browser fallback automation is still not fully covered in tests.

## Merge Recommendation

Recommendation: **mergeable**, with these conditions:

- prefer a normal merge commit over squash to preserve the staged checkpoints
- treat this branch as a governance / architecture tranche, not a final “finished product” state
- continue the next tranche from the merged branch head rather than reopening large single-file edits on `main`

## Suggested Post-Merge Next Step

If merged, the next engineering tranche should focus on:

1. shrinking `core/config.py`
2. defining more stable result / error contracts around scraper and persistence
3. tightening installer / platform behavior beyond documentation-only guardrails
