# CHANGELOG

> 记录项目对外发布版本的可读变更。  
> 不机械罗列所有 commits，只总结对用户、协作者、维护者真正重要的变化。

---

## [Unreleased]

### 新增
- 从 2026-04-04 起，后续新版本和新工作请从这一节继续累积。

### 变更
- 无

### 修复
- 无

### 移除
- 无

### 兼容性影响
- 无

### 迁移提示
- 当前历史已经压缩进下方三个基线节点；新的版本记录建议从本节开始。

---

## [2026-04-04：`structure-alignment` 十二阶段结构收口] - 2026-04-04

### 新增
- 新增 `cli/archive_execution.py` 作为 CLI、TUI、legacy 共享执行桥，减少入口层对私有 helper 的依赖。
- 新增 SQLite `content_key = type:id` 读取/展示闭环，使 query 面与数据库真实主键一致。
- 新增保存失败 typed context、monitor 增量状态和 creator 元数据清洗相关回归测试。

### 变更
- 以十二阶段方式完成一轮结构收口：文档真相层、入口拓扑、安装契约、配置运行时、CLI 瘦身、workflow 默认语义、保存闭环、数据库身份模型、creator/monitor 边角和最终验证矩阵全部串联整理。
- `zhihu` / `interactive` / `interactive --legacy` 的主次路径表述与帮助文本进一步统一。
- `config --show`、`check`、monitor pointer 规则、query 输出、creator README/JSON 元信息都对齐到当前主结构。

### 修复
- 修复了保存链路中 SQLite 写入失败会被静默吞掉的问题，现在失败会带上部分已保存结果和失败条目上下文。
- 修复了 monitor 在收藏夹顶部只有不支持归档的新条目时可能反复扫描同一批头部噪音的问题。
- 修复了 creator 元信息中遗留 HTML 片段直接落到 README/JSON 的问题。
- 修复了 query 展示仍以裸 `answer_id` 作为公开身份、容易混淆 answer/article 同号内容的问题。

### 移除
- 进一步移除了 `cli/app.py` 中失去职责的死 helper 和重复编排压力。

### 兼容性影响
- 旧 Cookie 路径、旧 launcher/legacy 入口仍保留兼容，但状态已经被更明确地暴露和降权。
- `answer_id` 仍保留为历史兼容字段，但数据库和 query 的稳定身份已收口到 `content_key`。

### 迁移提示
- 维护者后续应优先沿 `workflow service`、`save pipeline`、`content_key`、`monitor delta` 这些已收口边界继续演进，而不是把逻辑重新堆回命令层。
- 建议继续把实际运行时凭据逐步迁移到 `.local/`，避免长期依赖仓库根目录 Cookie 兼容路径。

---

## [历史基线：项目启动至 2026-04-02] - 2026-04-02

### 新增
- 建立了知乎本地归档项目的核心能力：回答抓取、专栏抓取、问题页分页抓取、作者主页抓取、批量抓取、收藏夹增量监控、SQLite 查询。
- 建立了本地输出闭环：Markdown、图片本地化、`zhihu.db`、creator 元信息。
- 建立了基础命令面：`fetch`、`batch`、`creator`、`monitor`、`query`、`manual`、`interactive`。
- 建立了协议优先抓取路径，并在必要时引入 Playwright 浏览器回退能力。
- 引入配置系统、日志系统、Cookie 管理、安装脚本和更清晰的目录布局。
- 完成 Textual TUI 六阶段重构，使 `interactive` 成为真正的全屏交互工作台。

### 变更
- 项目从早期脚本集合逐步演化为本地优先的知乎归档工具。
- 抓取链路从浏览器主导逐步转向协议优先，再辅以回退路径。
- 默认启动方式收敛为 `zhihu` 命令，而不是手动记忆 Python 启动入口。
- 输出目录、配置路径、Cookie 路径、运行时目录逐步收口到更清晰的结构。

### 修复
- 修复了多轮抓取中的公式识别、图片本地回写、Markdown 转换、重复下载、输出路径不稳定等问题。
- 修复了旧交互界面中的粘贴、状态卡、缩放布局、渲染残影等问题。
- 修复了启动器、安装链路、Cookie 模板和 README 指引中的多处可用性问题。

### 移除
- 逐步降低了旧脚本式入口和历史杂糅结构的权重。
- 旧的打印式交互路径不再作为默认主路径。

### 兼容性影响
- 历史 Cookie 路径、旧交互方式和部分旧布局仍保留兼容，但默认路径已经明显变化。
- 默认交互入口已变为 Textual TUI，旧交互模式仅作为兼容与排障路径保留。

### 迁移提示
- 建议使用 `./install.sh` 和 `zhihu` 作为标准安装与启动方式。
- 建议将运行时文件迁移到 `.local/`，不要继续把 Cookie、日志、状态文件散落在仓库根目录。
- 如仍依赖旧交互方式，请使用 `zhihu interactive --legacy`。

---

## [2026-04-03：`test` 六阶段治理、contract tranche 与主线合并] - 2026-04-03

### 新增
- 新增阶段化治理体系：仓库边界、质量审计、验证矩阵、安装契约、发布审查、merge playbook。
- 新增命令面守卫、文档同步测试、安装契约测试、配置/保存/抓取 contract 测试。
- 新增 `workflow service` 层，为 `fetch / batch / creator / monitor` 提供统一任务编排。
- 新增 `config schema / runtime / facade` 分层，以及更稳定的 scraper/save typed contracts。
- 新增 `MANUAL` / `AGENTS` / `docs/config` / `docs/dependency-map` / `docs/workflows` 等正式工程文档入口。

### 变更
- `test` 分支完成六阶段治理后正式合回 `main`。
- `cli/app.py` 被持续压薄，manual、launcher、save pipeline、config view、creator metadata、workflow orchestration 等职责进一步下沉。
- 文档体系从单一 README 承担全部内容，演进为 `README + MANUAL + AGENTS + docs/*` 分层。
- 平台支持边界和 Windows 状态被明确写入文档，而不再靠口头说明。
- 项目维护基线提升，测试和 CI 从“有一些检查”提升为“有明确验证矩阵”。

### 修复
- 修复了环境检查输出噪音、依赖缺失提示、配置展示、Linux 路径友好性、安装契约漂移等问题。
- 修复了文档、命令面、help、manual、平台说明之间不同步的问题。
- 修复了部分工作流对松散 dict 和跨层逻辑的过度依赖，开始向稳定 contract 收口。

### 移除
- 旧式混杂职责继续从主入口剥离，不再让 `cli/app.py` 同时承担所有流程。
- legacy / compatibility 逻辑不再假装是主路径，而是被明确标记为兼容或排障路径。

### 兼容性影响
- Python 维护基线、安装路径、文档入口和主交互入口的表达都比之前更严格。
- 旧路径仍有兼容层，但维护重点已转向新结构、新 workflow、新 contract。

### 迁移提示
- 后续维护请优先从新的工作流边界和 typed contracts 上继续推进，而不是回到大文件内联逻辑。
- 文档与结构请以 `README / MANUAL / docs/*` 的正式入口为准。
- 从 2026-04-04 开始，建议把后续工作作为新的版本线继续记录在 `Unreleased` 中。
