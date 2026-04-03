# TUI Rebuild Merge Checklist / TUI 重构合并清单

这份清单用于把 `tui-rebuild` 合并回 `main` 前做最后确认。

## Scope / 变更范围

当前分支相对 `main` 的主要改动只在这些区域：

- `cli/`
- `cli/tui/`
- `README.md`
- `README_EN.md`
- `pyproject.toml`
- `tests/test_tui_rebuild.py`

当前分支**没有修改 `core/`**，也就是说抓取、转换、数据库、监控等核心实现没有被这轮 TUI 重构直接侵入。

## Functional Checks / 功能检查

- `./zhihu --help`
- `./zhihu fetch --help`
- `./zhihu interactive --help`
- `./.venv/bin/python -m unittest -q tests.test_tui_rebuild`

确认 `interactive` 的主路径已经是新工作台：

- `Enter` 生成当前草案
- `Ctrl+R` 执行当前草案
- `Ctrl+Y` 从最近失败项生成重试草案
- `--legacy` 仅作为回归排查回退入口

## Compatibility Notes / 兼容性说明

和 `main` 相比，真正会影响旧 CLI 行为的点只有两个：

1. `interactive` 命令默认切到了 Textual 工作台
2. `cli/app.py` 里的 `_fetch_and_save()` 现在会返回保存结果列表

第二点是向后兼容的：

- 原先调用方只关心副作用，不依赖返回值
- 现在新增返回值，只是为了让 TUI 汇总结果摘要

## Merge Recommendation / 合并建议

建议直接 merge，不建议 squash，原因：

- 这条分支已经有清晰阶段节点，便于以后回退
- 远端 tag 已经完整保留：
  - `tui-p1-shell`
  - `tui-p2-layout`
  - `tui-p3-input`
  - `tui-p4-single-run`
  - `tui-p5-usable`
  - `tui-p6-cutover`

如果需要进一步开发，也可以在 `tui-rebuild` 上继续推进，等下一轮增强收敛后再合并。

## Post-Merge Follow-up / 合并后建议

- 再跑一次真实 `zhihu interactive`
- 再跑一次 `zhihu interactive --legacy`
- 再验证一次 `fetch / creator / batch / monitor / query` 的帮助文本
- 决定是否在下一轮删除 `interactive_legacy.py`
