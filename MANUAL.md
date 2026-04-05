# MANUAL.md

本文件是本仓库的内部说明书，面向维护者、未来协作者和后续重构任务。  
它不替代 `README.md`，而是负责记录架构、边界、约定、限制和维护方式。

## 1. 项目定位

### 1.1 目标

本项目是一个**本地优先**的知乎抓取与归档工具，目标是：

- 输入知乎链接或本地任务清单
- 默认走协议优先抓取，必要时回退浏览器
- 抓取正文和必要元数据
- 转换为 Markdown
- 下载图片并保存为本地文件
- 同步写入 SQLite 以支持检索和增量任务

当前推荐交付形态：

- CLI 命令面
- Textual TUI 交互工作台
- 本地 `data/` 内容目录
- 本地 `zhihu.db`

### 1.2 非目标

以下内容不属于当前主交付目标：

- 在线托管爬虫平台
- SaaS 服务
- 统一 GUI 产品
- 面向企业的批量数据服务
- 全站级主题采集
- MySQL / Elasticsearch / 云端存储为默认路径

## 2. README 与 MANUAL 的分工

- `README.md`
  对外入口。负责项目介绍、快速安装、最小运行方式、功能概览、基本目录说明。
- `README_EN.md`
  英文对外入口，内容与中文 README 保持能力边界一致。
- `MANUAL.md`
  内部说明书。记录架构、边界、配置、合同、维护约定、已知限制与迁移信息。
- `AGENTS.md`
  代码代理执行规范。任何代理任务开始前优先阅读。
- `cli/manual_content.py`
  内置终端说明书，服务 `zhihu manual` 命令，属于操作层文档，不替代 `MANUAL.md`。

## 3. 仓库结构

### 3.1 主项目目录

```text
.
├─ AGENTS.md
├─ CHANGELOG.md
├─ DEVLOG.md
├─ MANUAL.md
├─ README.md
├─ README_EN.md
├─ .github/
├─ pyproject.toml
├─ config.yaml
├─ install.sh
├─ cli/
├─ core/
├─ docs/
├─ references/
├─ tests/
├─ data/
└─ .local/
```

### 3.2 `cli/`

`cli/` 负责命令入口、用户交互与保存编排。

- `cli/app.py`
  Typer 命令注册与总入口。
- `cli/archive_execution.py`
  CLI / TUI / legacy 共用的执行桥，避免其他入口反向依赖 `cli.app` 私有 helper。
- `cli/workflow_service.py`
  应用服务层，统一 `fetch / batch / creator / monitor` 的任务编排。
- `cli/workflow_contracts.py`
  CLI/TUI 工作流层的 typed result contracts。
- `cli/launcher_flow.py`
  首页菜单与 onboarding 流程。
- `cli/manual_content.py`
  内置 manual 文本生成。
- `cli/config_view.py`
  `zhihu config --show` 的展示层。
- `cli/save_pipeline.py`
  Markdown / 图片 / SQLite / creator 元信息的保存编排。
- `cli/save_contracts.py`
  保存链路稳定 result contract。
- `cli/interactive.py`
  Textual TUI 启动入口。
- `cli/interactive_legacy.py`
  旧 Rich / questionary 路径，仅作兼容与排障。
- `cli/healthcheck.py`
  `zhihu check` 的环境检查逻辑。
- `cli/optional_deps.py`
  可选依赖缺失提示和降级行为。

### 3.3 `core/`

`core/` 负责抓取、配置、转换、数据库与运行时能力。

- `core/scraper.py`
  抓取主逻辑，仍是当前主要复杂点之一。
- `core/scraper_payloads.py`
  页面载荷归一化构建逻辑。
- `core/scraper_contracts.py`
  抓取结果 typed contracts。
- `core/api_client.py`
  API 模式请求与协议访问。
- `core/browser_fallback.py`
  浏览器回退路径。
- `core/converter.py`
  HTML 到 Markdown 的转换。
- `core/db.py`
  SQLite 落地与查询。
- `core/monitor.py`
  收藏夹增量监控逻辑。
- `core/cookie_manager.py`
  Cookie 文件和 Cookie 池管理。
- `core/config.py`
  配置 facade。
- `core/config_runtime.py`
  配置加载与单例缓存。
- `core/config_schema.py`
  配置 schema 与默认值。
- `core/logging_setup.py`
  结构化日志与脱敏。
- `core/project_paths.py`
  项目路径解析。
- `core/runtime_paths.py`
  `.local/` 运行时路径默认值。

### 3.4 `docs/`

`docs/` 放正式专题文档。当前重点包括：

- 平台边界：`docs/PLATFORM_SUPPORT.md`
- Windows 运行：`docs/WINDOWS_RUNBOOK.md`
- 依赖映射：`docs/dependency-map.md`
- 配置说明：`docs/config.md`
- 工作流说明：`docs/workflows.md`
- 历史阶段审计和 merge 文档

### 3.5 `references/`

`references/` 只放参考资料，不放主项目实现。

- `references/skills/`
  已筛选并归一后的 skill 参考资料
- `references/external/`
  外部参考仓库的本地挂载点；正式进入版本库的只有目录说明，挂载的外部仓库内容不属于主项目源码

说明：

- `references/external/` 不属于主项目代码边界
- 这里的内容可以参考，但不应被主项目代码直接 import

### 3.6 `tests/`

当前测试以标准库 `unittest` 为主，主要覆盖：

- 文档同步
- 命令面
- 配置 schema / runtime
- workflow service / 执行桥边界
- 保存链路
- SQLite contract / schema 迁移
- scraper contracts / payloads
- TUI 基础流程
- 安装契约

## 4. 依赖说明与依赖分类原则

### 4.1 唯一事实来源

主项目依赖以 `pyproject.toml` 为唯一事实来源。

处理原则：

- 不为主项目新增根目录 `requirements*.txt`
- 文档、安装脚本、CI 应以 `pyproject.toml` 为准
- 子目录中出现的 `requirements*.txt` 需要先判断是否属于独立子项目

### 4.2 当前依赖分类

#### 核心抓取与协议访问

- `curl_cffi`
- `httpx`
- `PyExecJS`

#### 内容解析与转换

- `beautifulsoup4`
- `markdownify`

#### CLI / TUI / 用户交互

- `typer`
- `rich`
- `textual`
- `questionary`

说明：

- `questionary` 仍在 onboarding 和 legacy 流程中使用
- `textual` 是当前默认交互入口所依赖的正式依赖

#### 配置与日志

- `pyyaml`
- `structlog`

#### 可选浏览器能力

- `playwright`

当前通过 `.[full]` 安装，不作为最小运行路径的硬依赖。

### 4.3 子目录依赖文件处理原则

仓库中当前仍存在：

- `references/external/MediaCrawler/requirements.txt`
- `references/external/MediaCrawler/uv.lock`

它们**不属于本项目根目录依赖来源**，视为子项目或外部参考材料，暂不静默删除。

### 4.4 依赖新增原则

新增依赖前必须满足：

- 代码中有实际使用
- 文档中能解释用途
- 安装链路能覆盖
- 测试或 smoke 能验证

## 5. 配置系统说明

### 5.1 入口文件

- 用户配置文件：`config.yaml`
- schema：`core/config_schema.py`
- runtime loader：`core/config_runtime.py`
- facade：`core/config.py`

### 5.2 配置分层

配置结构目前分为四块：

- `zhihu`
  Cookie、浏览器、反检测、签名相关
- `crawler`
  重试、滚动、人类行为模拟、图片下载
- `output`
  输出目录、图片子目录、文件夹模板
- `logging`
  日志等级、格式、文件路径、异常记录

### 5.3 运行时路径

当前默认运行目录已经收口到 `.local/`：

- `.local/cookies.json`
- `.local/cookie_pool/`
- `.local/logs/`

同时仍兼容历史路径：

- `cookies.json`
- `cookie_pool/`

当前 `zhihu config --show` 与 `zhihu check` 会同时展示：

- configured path
- active path
- 是否仍命中仓库根目录旧路径兼容

### 5.4 配置兼容原则

- 优先兼容旧字段和旧路径
- 配置加载失败时允许回退默认配置，但应记录警告
- 新旧字段差异应写入 `docs/config.md`

## 6. 核心数据流 / 运行流程

### 6.1 入口拓扑

```text
zhihu
-> cli/app.py main()
-> 无参数时进入 cli/launcher_flow.py 首页 launcher

zhihu interactive
-> cli/interactive.py
-> 直接启动 Textual TUI

zhihu interactive --legacy
-> cli/interactive_legacy.py
-> 旧 Rich / questionary 回退路径

zhihu fetch / creator / batch / monitor / query / config / check / manual
-> cli/app.py Typer 命令入口
```

说明：

- `zhihu` 是首页 launcher，不是 Textual TUI 的别名
- `zhihu interactive` 是当前默认交互工作台的直达入口
- `zhihu interactive --legacy` 仅用于兼容与排障

### 6.2 单条抓取

```text
用户输入 URL
-> cli/app.py fetch 命令入口
-> cli/workflow_service.py 统一抓取工作流
-> core/scraper.py 识别页面类型并抓取
-> article 路径优先走协议抓取，必要时回退浏览器
-> cli/save_pipeline.py 内部调用 converter / db 完成保存
-> cli/save_contracts.py 返回保存结果 contract
```

说明：

- 若 SQLite 写入在 Markdown 已落盘后失败，保存链路会抛出 `SavePipelineError`
- 该异常会保留 partial save result、失败条目与失败 Markdown 路径，供 workflow 层继续汇总

### 6.3 creator 流程

```text
creator URL / token
-> cli/workflow_service.py
-> core/scraper.py 抓作者回答和专栏
-> cli/save_pipeline.py 保存内容
-> cli/creator_metadata.py 写 creator 索引文件
-> cli/workflow_contracts.py / cli/save_contracts.py 返回聚合结果
```

### 6.4 interactive 流程

```text
zhihu interactive
-> cli/interactive.py 启动 Textual TUI
-> 应用内构建 draft
-> cli/archive_execution.py 执行共享抓取入口
-> cli/workflow_service.py / cli/save_pipeline.py
-> 展示最近结果与重试草案
```

说明：

- `zhihu` 无参数时先进入首页 launcher，再由用户决定是否进入 TUI
- `zhihu interactive --legacy` 不属于推荐主路径

### 6.5 monitor 流程

```text
收藏夹 ID
-> cli/workflow_service.py
-> core/monitor.py 计算增量范围
-> core/scraper.py 抓新内容
-> cli/save_pipeline.py 保存
-> unsupported-only 新动态可安全推进 pointer
-> 若存在可归档条目且本轮有失败，则不推进 pointer
```

## 7. 关键数据结构 / contracts

### 7.1 抓取 contracts

定义位置：`core/scraper_contracts.py`

核心结构：

- `ScrapedItem`
  表示一条标准化抓取结果。
- `PaginationStats`
  表示分页请求过程的统计信息。
- `CreatorProfileSummary`
  表示作者资料摘要。
- `PageFetchResult`
  表示单 URL 抓取结果，可能包含多条 item。
- `CreatorFetchResult`
  表示作者抓取结果，包含 creator 摘要与 answers/articles 分页统计。

### 7.2 保存 contracts

定义位置：`cli/save_contracts.py`

核心结构：

- `SavedContentRecord`
  表示一条已保存内容及其落盘位置。
- `SaveRunResult`
  表示一次保存任务的结果集合。
- `SavePipelineError`
  表示保存链路中途失败时的类型化异常，附带部分已保存结果与失败条目上下文。
- `CreatorSaveResult`
  表示作者抓取+保存的聚合结果。

数据库读取层当前以 `content_key = type:id` 作为稳定身份；
`answer_id` 仅作为历史兼容字段保留，新的 query / search 展示也应优先使用 `content_key`。

### 7.3 设计意图

这些 contracts 的目的不是“为了类型而类型”，而是：

- 减少 CLI 与 scraper 之间依赖松散 dict
- 让保存链路和 TUI 可以吃稳定结构
- 为后续继续拆 `core/scraper.py` 留接口空间

### 7.4 工作流 contracts

定义位置：`cli/workflow_contracts.py`

核心结构：

- `UrlTaskResult`
  表示一条 URL 任务的执行结果。
- `BatchWorkflowResult`
  表示一组 URL 任务的聚合结果。
- `CreatorWorkflowResult`
  表示作者抓取流程的聚合结果。
- `MonitorWorkflowResult`
  表示收藏夹增量同步的聚合结果和 pointer 推进状态。

当前 monitor contract 还会显式暴露：

- `unsupported_count`
- `next_pointer`
- `has_new_activity`

这层的作用是：

- 让 `cli/app.py` 只做命令入口，不再自己拼业务流程
- 让 TUI、后续自动化任务、未来 API 层可以共用同一套 orchestration
- 为失败分类、审计日志、重试策略继续扩展预留稳定接口

## 8. 详细操作指引 (从 README 迁移)

### 8.1 安装与环境诊断

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
./install.sh

# 如需重建环境
./install.sh --recreate

zhihu check
zhihu config --show
zhihu config --path
```

### 8.2 Cookie 准备

应用运行时默认使用 `.local/` 目录：
```bash
mkdir -p .local
cp cookies.example.json .local/cookies.json
```
需要在文件内填入你的 `z_c0` 与 `d_c0`。
若仍使用旧的根目录路径（如 `cookies.json` 或 `cookie_pool/`），系统仍会兼容。使用 `zhihu check` 可以查看当前生效路径。

### 8.3 交互入口拓扑

- `zhihu`
  无参数时进入全屏 Textual TUI 交互式工作台（带有首次语言选择）。
- `zhihu interactive --legacy`
  旧版 Rich / questionary 回退路径，仅作兼容与排障。
- `zhihu onboard`
  首次环境体检和引导向导。

### 8.4 详细抓取命令

```bash
# 抓取单条：
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"

# 抓取作者主页：
zhihu creator "https://www.zhihu.com/people/iterator"

# 批量抓取链接列表文件 (urls.txt 每行一个链接)：
zhihu batch urls.txt -c 8

# 增量监控收藏夹：
zhihu monitor 78170682

# 本地 SQLite 数据检索：
zhihu query "Transformer" -l 20
```

### 8.5 默认输出结构

抓取得到的文件默认存放于 `data/` 目录中：

```text
data/
├─ entries/
│  └─ 2026-04-03_title--answer-123456/
│     ├─ index.md  (包含正文，如有启翻译则伴随有 [EN] 版文件)
│     └─ images/   (原图备份)
├─ creators/
│  └─ <url_token>/
│     ├─ creator.json
│     └─ README.md
└─ zhihu.db        (SQLite 索引库)
```

## 9. 已知问题与限制

- 当前默认平台仍然是 macOS 与 Linux CLI 路径，Windows 仍在补 runbook 与验证。
- `interactive` 暂不接受 creator profile URL，作者抓取请使用 `zhihu creator`。
- Playwright 回退仍然是补充路径，不是所有内容都完全依赖浏览器。
- `core/scraper.py` 仍是高复杂度文件，虽然已经拆出 payloads 和 contracts，但还未彻底收口。
- `core/config.py` 虽然已经转成 facade，但配置系统仍有继续模块化空间。

## 10. 维护约定

### 10.1 修改前顺序

默认顺序：

1. 读 `AGENTS.md`
2. 读 `MANUAL.md`
3. 看相关 `docs/`
4. 再进入具体模块

### 10.2 文档同步

以下内容改动时，默认检查文档是否需要同步：

- CLI 命令面
- 配置字段
- 安装方式
- 平台支持边界
- TUI 行为

需要同步的入口通常包括：

- `README.md`
- `README_EN.md`
- `MANUAL.md`
- `cli/manual_content.py`
- `docs/PLATFORM_SUPPORT.md`
- `docs/config.md`
- `docs/workflows.md`

### 10.3 测试与 smoke

默认最小校验集：

- `python -m unittest -q ...`
- `zhihu --help`
- `zhihu fetch --help`
- `zhihu interactive --help`
- `zhihu config --help`
- `zhihu check --help`

## 11. 迁移记录 / 后续待办

### 11.1 已完成的阶段

阶段一到阶段六已经完成，主要完成了：

- skill 与治理底座整理
- 系统审计
- P0 可用性修复
- CLI / 保存链路 / 配置展示层拆分
- 验证矩阵和安装契约固化
- 发布与合并收口文档

阶段六之后又继续推进了：

- `core/config.py` 向 facade 化收敛
- scraper / save result contract 类型化

### 11.2 当前后续重点

- 继续压薄 `cli/app.py`，让命令层只保留参数解析和输出
- 继续拆 `core/scraper.py`
- 继续收紧配置系统边界
- 继续稳定 workflow / save / scraper 的 typed contract
- 补更真实的三平台验证
- 继续压缩 legacy 交互路径的权重

## 12. 相关文档入口

- [README.md](README.md)
- [AGENTS.md](AGENTS.md)
- [docs/dependency-map.md](docs/dependency-map.md)
- [docs/config.md](docs/config.md)
- [docs/workflows.md](docs/workflows.md)
- [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md)
- [docs/WINDOWS_RUNBOOK.md](docs/WINDOWS_RUNBOOK.md)
