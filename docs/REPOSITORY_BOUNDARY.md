# Repository Boundary / 仓库边界

这份文档定义两个问题：

1. 哪些目录属于正式项目结构，应该长期维护
2. 哪些目录只属于本地运行、调试，不应作为仓库能力的一部分

This document defines two things:

1. which directories are part of the maintained project layout
2. which directories are local-only runtime or debug areas and should stay outside the product boundary

## Official Layout / 正式目录

以下目录属于正式仓库结构：

- `cli/`
  CLI 入口、命令编排、交互式终端入口。
- `core/`
  抓取、转换、配置、数据库、监控等核心实现。
- `static/`
  协议抓取和浏览器回退依赖的静态资源。
- `examples/`
  少量人工挑选的展示样例，不放本地临时导出结果。
- `docs/`
  仓库结构、命名规范、工程约定等正式文档。
- `references/`
  参考资料区；其中 `skills/` 是正式参考入口，`external/README.md` 是外部仓库落点说明；`skillsmp/` 视为本地临时来源，不纳入正式结构。
- `data/README.md`
  只保留目录说明；真正的数据产物不进入版本库。
- `.github/`
  CI 和仓库自动化配置。

根目录正式文件保持精简：

- `AGENTS.md`
- `MANUAL.md`
- `DEVLOG.md`
- `CHANGELOG.md`
- `README.md`
- `README_EN.md`
- `pyproject.toml`
- `config.yaml`
- `install.sh`
- `zhihu`
- `cookies.example.json`

## Local-Only Layout / 本地专用目录

以下路径属于本地运行、凭据、缓存、调试或外部参考，不应被视为产品结构：

- `.local/`
- `.venv/`
- `.claude/`
- `data/entries/`
- `data/creators/`
- `data/zhihu.db`
- `data/.monitor_state.json`
- `references/external/*`
- `references/skillsmp/`

历史兼容路径仍可存在，但不再推荐作为默认布局：

- `cookies.json`
- `cookie_pool/`
- `browser_data/`
- `logs/`

这些目录可以存在于工作区，但不应：

- 被 README 当作正式功能的一部分介绍
- 被代码当作仓库内必备依赖
- 被纳入 CI 或发布边界

## Naming Rules / 命名规范

### Code / 代码

- Python 模块文件统一用 `snake_case.py`
- 目录名优先使用短名词，不混用风格
- 避免 `misc`、`temp`、`new`、`final` 这类无语义命名

### CLI / 命令

- 命令名保持短动词或稳定名词：`fetch`、`batch`、`creator`、`monitor`、`query`
- 帮助文本使用 “动作 + 对象” 的描述方式，避免营销式命名

### Runtime Outputs / 运行产物

- 输出根目录统一使用 `data/`
- 普通抓取结果放 `entries/`
- 作者归档放 `creators/`
- 图片目录统一用 `images/`
- 数据库统一用 `zhihu.db`
- 本地凭据、日志、缓存统一收口到 `.local/`

### Docs / 文档

- 仓库级约定写在 `docs/`
- 展示样例写在 `examples/`
- 运行目录说明留在对应目录的 `README.md`

## Cleanup Decisions / 本轮清理决策

- `data/README.md` 与 `examples/README.md` 保留目录职责说明，不再重复仓库边界长说明
- Cookie、日志等敏感/本地状态默认迁移到 `.local/`
- 历史上的 `cookies.json` / `cookie_pool/` 暂时保留兼容，但不再作为文档主路径

## References / 参考资料

- `references/` 现在统一作为参考资料区
- `references/skills/docs-writing/` 保存 README / 文档写作相关 skill
- `references/skills/engineering/` 保存质量检测与工程推进相关 skill
- `references/external/README.md` 是外部参考仓库的正式入口说明
- `references/external/*` 下挂载的 `MediaCrawler/`、`openclaw/` 等内容视为本地参考材料，不纳入主项目正式边界
- `references/skillsmp/` 视为本地原始来源或临时挂载点，不纳入主项目正式边界；如需保留内容，应筛选后迁入 `references/skills/`

后续如果要重构 Cookie 存储、运行时目录或配置层，应以这份边界文档为准，而不是继续把本地实验目录混进正式仓库。
