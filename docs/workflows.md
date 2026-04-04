# workflows.md

本文档记录主项目的常见运行流程和维护流程，重点是“命令如何进入代码”和“产物落到哪里”。

## 1. 安装工作流

官方安装入口：

```bash
./install.sh
./install.sh --recreate
```

安装脚本当前会完成：

1. 检查 Python 版本
2. 创建或重建 `.venv`
3. 安装 `.[full]`
4. 安装 Playwright Chromium
5. 初始化 `.local/`
6. 运行一次 `zhihu check`
7. 安装全局命令 `zhihu`

补充说明：

- `./install.sh` 代表本地完整安装路径，内部使用 `pip install -e ".[full]"`
- CI 当前使用 `pip install -e .` 做基础命令面与单测验证
- 因此 CI 通过并不代表 Playwright / browser fallback 已被完整验证

## 2. 首页 / launcher 工作流

入口命令：

```bash
zhihu
```

流程：

```text
cli/app.py main()
-> 无参数分支
-> cli/launcher_flow.py
-> 首页菜单 / onboarding / 常用命令导航
```

说明：

- `zhihu` 默认进入首页 launcher
- `zhihu interactive` 才是直达 Textual TUI 的命令
- `zhihu interactive --legacy` 是兼容回退路径

## 3. 单条抓取工作流

入口命令：

```bash
zhihu fetch "https://www.zhihu.com/question/.../answer/..."
```

流程：

```text
Typer command
-> cli/app.py
-> cli/workflow_service.py
-> core/scraper.py
-> protocol-first fetch, with browser fallback when needed
-> cli/save_pipeline.py (converter + Markdown/images/SQLite persistence)
-> cli/save_contracts.py
-> data/entries/... + zhihu.db
```

## 4. creator 工作流

入口命令：

```bash
zhihu creator "https://www.zhihu.com/people/..."
```

流程：

```text
cli/app.py
-> cli/workflow_service.py
-> core/scraper.py (creator path)
-> cli/save_pipeline.py
-> cli/creator_metadata.py
-> data/creators/<url_token>/
```

## 5. batch 工作流

入口命令：

```bash
zhihu batch urls.txt
```

流程：

```text
cli/app.py
-> cli/workflow_service.py
-> 并发/顺序调度单 URL workflow
-> cli/save_pipeline.py
-> data/entries/... + zhihu.db
```

约束：

- 批量流程的汇总结果由 `cli/workflow_contracts.py` 提供
- 单条失败不会污染其它成功结果的保存记录

## 6. monitor 工作流

入口命令：

```bash
zhihu monitor 78170682
```

流程：

```text
cli/app.py
-> cli/workflow_service.py
-> core/monitor.py
-> core/scraper.py
-> cli/save_pipeline.py
-> pointer 更新
```

约束：

- 当本轮存在失败项时，不推进 pointer
- 当只有 unsupported 新条目时，pointer 仍可安全推进
- 避免增量任务静默跳过失败内容

## 7. query 工作流

入口命令：

```bash
zhihu query "Transformer" -l 20
```

流程：

```text
cli/app.py
-> core/db.py
-> local data/zhihu.db
-> Rich table output
```

约束：

- query 当前展示 `Content Key`
- 稳定身份为 `content_key = type:id`
- `answer_id` 仅保留为历史兼容字段

## 8. interactive 工作流

入口命令：

```bash
zhihu
zhihu interactive
zhihu interactive --legacy
```

说明：

- `zhihu` 打开首页 launcher，而不是直接进入 TUI
- `interactive` 当前默认是 Textual TUI
- `interactive --legacy` 为兼容与排障路径

主流程：

```text
zhihu interactive
-> cli/interactive.py
-> Textual TUI
```

通过首页进入时：

```text
zhihu
-> cli/launcher_flow.py
-> 选择 interactive
-> cli/interactive.py
-> Textual TUI
```

TUI 内部主流程：

```text
输入 URL / 文本
-> 生成 draft
-> 执行当前 draft
-> cli/archive_execution.py
-> cli/workflow_service.py / cli/save_pipeline.py
-> 展示最近执行结果 / 失败重试
```

## 9. config / check / manual 工作流

### `zhihu config --show`

- 负责输出配置摘要
- 展示层在 `cli/config_view.py`
- 展示 configured path / active path
- 显式提示是否仍命中旧 Cookie 路径兼容

### `zhihu check`

- 检查配置文件
- 检查 Cookie 状态
- 检查 configured path / active path 是否仍在命中旧路径兼容
- 检查 Playwright 可用性
- 目标是诊断，不是打印原始崩溃日志
- 当前诊断逻辑在 `cli/healthcheck.py`

### `zhihu manual`

- 打开内置 terminal manual
- 内容来源于 `cli/manual_content.py`

## 10. 文档维护工作流

当以下内容发生变化时，默认需要同步：

- 命令面
- 安装方式
- 配置字段
- 平台支持边界
- TUI 行为

文档同步顺序建议：

1. `MANUAL.md`
2. `README.md`
3. `README_EN.md`
4. `cli/manual_content.py`
5. `docs/` 下相关专题文档

## 11. 测试与回归工作流

最小回归集合：

```bash
./.venv/bin/python -m unittest -q tests.test_docs_sync tests.test_command_surface tests.test_install_contract
```

完整当前矩阵见：

- `docs/STAGE5_VALIDATION_MATRIX.md`

## 12. 当前维护建议

- 命令入口优先走 `cli/workflow_service.py`，不要再把 fetch/batch/monitor 编排堆回 `cli/app.py`
- 新工作优先在稳定 contract 边界上推进
- query / db 相关新工作优先沿 `content_key` 边界推进，不要重新把裸 `answer_id` 当成唯一身份
- 避免再把业务逻辑堆回 `cli/app.py`
- 避免在 README 中重复 MANUAL 和 docs 的内部细节
