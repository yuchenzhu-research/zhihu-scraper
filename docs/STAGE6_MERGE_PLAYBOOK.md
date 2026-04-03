# Stage 6 Merge Playbook

这份文档定义阶段六结束后的推荐合并方式，目标是：保留阶段 checkpoint、降低回退成本，并避免把这一轮治理工作压成一团不可追踪的大提交。

## Recommendation

- source branch: `test`
- target branch: `main`
- merge style: **normal merge commit**
- do **not** squash
- keep `test` after merge

## Why

`test` currently contains staged checkpoints for:

- stage 1 skill / repository boundary setup
- stage 2 quality audit
- stage 3 environment and CLI compatibility hardening
- stage 4 CLI / scraper boundary refactors
- stage 5 validation matrix and install contract hardening
- stage 6 release review and external-response handoff

Squashing would discard that checkpoint structure.

## Suggested Commands

```bash
git checkout main
git pull origin main
git merge --no-ff test
git push origin main
git checkout test
```

## Post-Merge Verification

After merge, run at least:

```bash
./.venv/bin/python -m unittest -q tests.test_cli_compat tests.test_docs_sync tests.test_command_surface tests.test_tui_rebuild tests.test_save_pipeline tests.test_config_view tests.test_scraper_payloads tests.test_install_contract
./.venv/bin/python cli/app.py --help
./.venv/bin/python cli/app.py interactive --help
./.venv/bin/python cli/app.py check
```

## If You Need to Keep Working on `test`

That is still fine. After merging:

- keep using `test` for the next tranche, or
- branch again from the merged `main`

The key point is to avoid reopening large, mixed edits directly on `main`.
