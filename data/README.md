# Scraping Results / 抓取结果

此目录只用于本地运行产物，不属于正式仓库内容。

This directory is reserved for local runtime artifacts and is not part of the maintained repository surface.

## Suggested Layout / 建议结构

- `data/entries/`
  普通 `fetch` / `batch` / `monitor` 输出。
- `data/creators/<url_token>/`
  `creator` 模式作者归档。
- `data/zhihu.db`
  本地 SQLite 数据库。
- `data/.monitor_state.json`
  收藏夹监控游标。

## Boundary Rules / 边界规则

- 不要把抓取结果、图片、数据库、监控状态提交到版本库
- 展示样例放到 `examples/outputs/`，不要回灌到 `data/`
- 仓库级目录约定见 [docs/REPOSITORY_BOUNDARY.md](../docs/REPOSITORY_BOUNDARY.md)
