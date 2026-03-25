# Examples / 示例

此目录用于展示仓库内保留的**示例抓取结果**，方便新用户直接查看 Markdown 导出的实际效果。

This directory contains **showcase exports** kept in the repository so readers can inspect real Markdown outputs without running the scraper first.

## 当前保留的展示样例

### 1. 超链接保留示例

- 路径：
  [examples/outputs/[2026-03-24] 【深度学习数学基础】序章 + 目录（已完结，共30章） (article-25643286963)/index.md](outputs/[2026-03-24]%20【深度学习数学基础】序章%20+%20目录（已完结，共30章）%20(article-25643286963)/index.md)
- 用途：
  展示专栏目录页、外部链接和多层超链接在 Markdown 中的保留效果。
- 重点观察：
  - 文章内的章节链接
  - 外部参考链接
  - 导出后的长文目录结构

### 2. 图片与数学公式示例

- 路径：
  [examples/outputs/[2026-03-24] 线性代数(Linear Algebra)学习笔记 (article-641433373)/index.md](outputs/[2026-03-24]%20线性代数(Linear%20Algebra)学习笔记%20(article-641433373)/index.md)
- 用途：
  展示大篇幅图片资源、本地图片引用、块公式和行内公式的导出效果。
- 重点观察：
  - `images/` 子目录中的本地图片资源
  - `$$ ... $$` 形式的块公式
  - 长文中图片与公式混排的效果

## Boundary Rules / 边界规则

- `examples/outputs/` 只保留少量人工挑选的展示样例
- 不要放真实 Cookie、数据库、监控状态或临时调试产物
- 本地临时导出结果放回 `data/`
- 仓库级目录约定见 [docs/REPOSITORY_BOUNDARY.md](../docs/REPOSITORY_BOUNDARY.md)
