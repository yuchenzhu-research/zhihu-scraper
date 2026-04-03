# AGENTS.md

本文件是本仓库的项目级执行规则。  
后续任何代码代理或自动化协作者进入仓库后，都应优先阅读本文件，再执行具体任务。

## 1. 默认执行流程

所有代理在开始本仓库任务前，必须先阅读并遵守 `AGENTS.md`。除非任务明确说明，否则不得跳过。

默认执行顺序如下：

1. 先阅读 `AGENTS.md`
2. 再检查与本次任务相关的：
   - `README.md`
   - `MANUAL.md`
   - `docs/`
   - `pyproject.toml`
   - 相关代码与测试
3. 再实施修改
4. 如果本次任务形成了新的相关 Git commits，则在汇报中明确说明 commit 情况
5. 是否更新 `DEVLOG.md`，由维护者手动决定；代理不得默认每次都自动更新
6. 如果本次任务对应对外发布版本、里程碑发布或明确的对外可见更新，则再判断是否需要同步更新 `CHANGELOG.md`

说明：

- 后续在本仓库执行任务时，默认先读本文件，不再依赖用户重复提醒
- 如果任务范围只涉及文档、测试或配置，也不跳过这个流程

## 2. 项目目标

本项目的目标是维护一个**本地优先**的知乎抓取与归档工具，核心交付包括：

- 稳定的 CLI 与 TUI 入口
- Markdown + 图片 + SQLite 的本地输出
- 可维护的配置系统
- 明确的模块边界与 typed contracts
- 可复现的测试、安装和文档入口

默认优先级：

1. 保持现有功能可用
2. 减少结构混乱与文档漂移
3. 在不破坏兼容性的前提下推进重构

## 3. 修改原则

- 先检查现状，再修改，不先假设
- 优先最小闭环修改，不做顺手大重构
- 能抽边界时抽边界，但不要制造空壳模块
- 新增模块必须有明确职责，避免“helper.py / misc.py / temp.py”这类无语义文件
- 已经形成的模块边界优先保留：
  - `cli/` 负责入口与编排
  - `core/` 负责抓取、配置、转换、数据库与运行时能力
  - `docs/` 负责正式工程文档

## 4. 依赖管理规则

- `pyproject.toml` 是主项目依赖的唯一事实来源
- 不要为主项目再新增根目录 `requirements*.txt`
- 如果仓库内存在其他目录下的 `requirements*.txt`，先判断是否属于独立子项目或外部参考材料，不要静默删除
- 新依赖必须满足：
  - 有明确用途
  - 代码里确实使用
  - 文档中有落点
  - 测试或安装链路能覆盖

## 5. 文档与日志同步规则

文档职责固定如下：

- `README.md`
  对外介绍、快速安装、最小运行方式、功能概览、基本目录说明
- `MANUAL.md`
  面向维护者与未来协作者的内部说明书
- `AGENTS.md`
  面向代码代理的执行规范
- `docs/`
  放专题文档，例如依赖、配置、工作流、平台支持、阶段审计

修改代码时，优先检查以下内容是否需要同步：

- `README.md`
- `README_EN.md`
- `MANUAL.md`
- `cli/manual_content.py`
- `docs/` 下相关专题文档

### 5.1 DEVLOG 维护规则

`DEVLOG.md` 用于记录按“日期 / 任务”归档的人工维护日志，不要求一条记录严格对应一个 commit。

是否更新 `DEVLOG.md`，由维护者手动决定。  
代理默认**不因“本次任务产生了 commit”就自动更新 `DEVLOG.md`**。

原则：

- 一次任务一条记录，或一次阶段性整理一条记录
- 一条记录下可附多个相关 commit hashes
- 不要求每个 commit 单独写一条 `DEVLOG`
- `DEVLOG` 优先保证可读性与任务层面的清晰总结，不机械复制 Git 日志

每条记录建议至少包含：

- 日期
- 任务标题
- 相关 commits
- 本次修改
- 解决的问题
- 影响范围
- 风险 / 未完成事项
- 下一步计划（可选）

### 5.2 commit 与 DEVLOG 的关系

Git commit 负责记录细粒度代码变更；`DEVLOG.md` 负责记录“这次任务整体做了什么”。

因此：

- 不要求每个 commit 单独写一条 `DEVLOG`
- 允许多个相关 commits 合并为一条 `DEVLOG`
- 代理应在结果汇报中说明当前是否形成了新 commits，供维护者决定是否更新 `DEVLOG.md`
- 如果任务结束时改动尚未提交，则在结果汇报中明确说明：
  - 当前改动尚未提交
  - 暂无最终 commit hash
  - 必要时可以先以“未提交”作为临时占位，待提交后补全

### 5.3 CHANGELOG 维护规则

`CHANGELOG.md` 用于记录对外发布版本的可读变更。

仅当任务对应以下情形时，才需要同步更新：

- 对外发布版本
- 里程碑发布
- 明确的对外可见更新

日常内部重构、测试补强、文档整理，不默认要求更新 `CHANGELOG.md`。

## 6. 测试与校验要求

默认最小校验集：

- `./.venv/bin/python -m unittest -q ...` 运行当前验证矩阵
- 命令面 smoke：
  - `python cli/app.py --help`
  - `python cli/app.py fetch --help`
  - `python cli/app.py interactive --help`
  - `python cli/app.py config --help`
  - `python cli/app.py check --help`

如果改动涉及以下范围，还应补对应验证：

- 文档/命令面：`tests.test_docs_sync`、`tests.test_command_surface`
- 配置层：`tests.test_config_schema`、`tests.test_config_runtime`
- 保存链路：`tests.test_save_pipeline`、`tests.test_save_contracts`
- scraper contract：`tests.test_scraper_payloads`、`tests.test_scraper_contracts`
- 安装/平台边界：`tests.test_install_contract`

## 7. 任务完成后的汇报要求

完成任务后，汇报应尽量包含：

1. 仓库原状
2. 新建文件
3. 修改文件
4. 每个文件修改目的
5. 已验证内容
6. 未验证内容
7. 风险、歧义与后续建议

如果任务与 Git 提交相关，还应明确说明：

1. 是否形成了新的相关 commits
2. `DEVLOG.md` 是否需要更新，或是否由维护者手动决定
3. 若已更新，记录了哪些相关 commit hashes
4. 若未更新，原因是什么
5. 是否需要同步更新 `CHANGELOG.md`

如果存在未解决问题，不要装作已经完成。

## 8. 禁止事项

- 不要先假设文件不存在
- 不要静默删除可能仍有价值的旧文档或旧文件
- 不要在未确认职责的情况下新增重复文档
- 不要把 README 再次写成“内部说明书全集”
- 不要新增与任务无关的依赖
- 不要把测试失败当成“只是 CI 问题”略过
- 不要在未经说明的情况下修改 `references/external/` 下的独立/参考目录

## 9. 遇到歧义时的处理原则

如果出现以下情况：

- 文件职责重叠
- 文档命名不统一
- 旧内容仍有价值但明显过时
- 代码边界暂时无法彻底理顺

默认策略是：

1. 优先最小改动
2. 优先保留有价值内容
3. 优先通过新增标准入口解决混乱
4. 无法彻底解决时，把歧义写进 `MANUAL.md` 或相应 `docs/` 文档

## 10. 长期维护约定

- 后续任务开始时，先读本文件
- 再读 `MANUAL.md`
- 再看本次任务相关模块与专题文档

如果仓库结构发生重大变化，应同步更新：

- `AGENTS.md`
- `MANUAL.md`
- `README.md`
