# DEVLOG

---

## 2026-04-06 / 交互体验与国际化细节收口

### 相关 commits
- `5e653fb` / `7c104b6` (fix: TUI 模式下彻底禁用控制台日志，解决布局撑破/UI 腐化)
- `404d75c` (feat: LocalizedFooter — 现在底部快捷键栏已完全国际化)
- `9c9d2d0` (feat: 重构 config 命令并新增 `set` 选项，允许随时通过 CLI 切语言)
- `a9cd66b` (chore: config.yaml 状态落盘持久化)

### 本次修改
- **底栏国际化 (Footer i18n)**：通过自定义 `LocalizedFooter` 小部件覆盖了 Textual 的 BINDINGS 渲染逻辑。
  - 现在 BINDINGS 的描述字段允许使用 i18n key（如 `binding.run`）。
  - 在运行时配合 `recompose()` 可以同步更新底部的“输入、执行、重试、退出”等多语言文案。
- **日志隔离方案 (Silent Console)**：彻底解决了后台 API 请求报错（如 403 频控）导致 ASCII 码在终端界面乱跳挤压 TUI 的难题。
  - 在 `core/logging_setup.py` 中引入 `set_silent_console()` 原子开关。
  - 在 TUI 启动时强行切断标准输出链路，保证所有详尽报错信息只静默流向日志文件。
- **配置命令行 (CLI Config set)**：
  - 增强了 `zhihu config` 工具。
  - 现在可以通过命令行直接切换 UI 语言，而不再仅依赖于首次启动的向导或手动改 YAML。

### 解决的问题
- 解决了知乎新版超长 ID `answer_id` 触发反爬 403 导致 TUI 被大量日志输出撑破、界面无法阅读的重大视觉交互 Bug。
- 解决了底部操作栏 BINDINGS 无法根据已切换语言动态刷新显示的问题。
- 提供了更便捷的语言控制入口：`zhihu config set language <lang>`。

### 影响范围
- `cli/tui/app.py`
- `cli/tui/widgets.py`
- `cli/app.py`
- `core/logging_setup.py`
- `core/locales/*.json`

### 下一步
- 准备将成熟的 `i18n-crawler` 分支功能合并并推广。

---

## 2026-04-05 / 多语言启动向导、极简主页重构与 SkillsMP 挂载

### 相关 commits
- `767cc9f` / `5ee4cfb` / `76150fa` / `9a716c8` / `fa599d2` (文档体系优化与极简重构)
- `0b064cb` / `9c0f866` / `8e3bc8d` / `0b80c74` / `98fe42f` / `846c8fe` / `797d1b4` / `6b74ea9` / `c528271` (TUI First-Run 多语言向导与交互升级)

### 本次修改
- **首运行多语言向导**：
  - 新增 `language_configured` 的配置文件持久化开关。
  - 在 TUI (Textual) 入口加入首运行强弹的 `LanguageSelectionScreen`（Apple-style 设置体验）。
  - 新增 `zh_hant` 繁体中文语言包，并完全解耦与补齐了原有 `InputCard` 的国际化字典项。
- **命令行入口收口**：
  - 更改了裸 `zhihu` 触发的底层逻辑，如今执行 `zhihu` 会直达 Textual TUI 进行首运行检测并打开全屏工作台。
- **配置系统升级**：
  - 重构了 `zhihu config` 命令，支持 `show`、`path` 和 `set` 子命令。
  - 允许通过 `zhihu config set language <lang>` 随时手动切换 UI 语言，并自动同步至配置文件。
- **README 重构与 SkillsMP 引入**：
  - 大幅抽离原双语 `README` 中的大量边角命令行传参、兼容路径与旧系统兼容文案，全量迁入内部说明书 `MANUAL.md`。
  - 按照 Github 明星开源库的标准，为 `README.md`、`README_EN.md` 打造了极简的信息密度抓眼展示（Elevator pitch）。
  - 在 `references/skills/` 下正式引入了 `mermaid-diagram`、`mermaid-tools` 和 `readme-generator` 指导方案。

### 解决的问题
- 解决了新手启动工具后仍需要记命令的痛点：现在 `zhihu` 命令直接打通体验。
- 解决了长篇 README 造成的维护与阅读疲劳：繁杂技术细节分流至 MANUAL，降低项目首屏劝退率。
- 确立了代码代理协同准则底线，通过 `skills` 给后续自动化引入立下了标准边界。

### 影响范围
- `cli/app.py`
- `cli/tui/app.py`, `widgets.py`, `dialogs.py`
- `core/config_schema.py`
- `core/locales/`
- 所有根目录及内层参考目录的 README 文档体系与 `MANUAL.md`

### 风险 / 未完成事项
- TUI 直接作为 `zhihu` 的默认入口对于终端不兼容真彩或特定 Curses 的极其老旧环境来说有一定失败风险。

### 下一步
- 为重构后的主页补上高帧率的 TUI 展示视频/图片。

---

## 2026-04-05 / 核心抓取链路加固与 TUI 故障修复

### 相关 commits
- `302ccd5` feat: enhance scraper with proxy/retry and fix TUI layout issues

### 本次修改
- 清理了 `docs/` 目录下的阶段性历史过渡文件（如 STAGE 1~6 系列的梳理文档及 TUI 合并清单），减轻维护认知负担。
- **硬核提升**：
  - 在 `api_client.py` 引入全局隧道代理（Proxy）配置，并加上了智能延时+指数退避的防封抗拦截重试机制。
  - 针对 `browser_fallback.py` 的 Playwright 环境抛出 `user_data_dir` 支持，依靠本地持久化降低降级强制唤醒时的二次风控率。
- **UI & TUI 优化**：针对在 `zhihu interactive` 界面下，由于粘贴超长知乎链接时 Textual `TextArea` 未换行且无限侵占高度，引发“图三空框挤压坍塌”的渲染漏洞进行了 CSS 排版重构与 `soft_wrap` 软换行支持。

### 解决的问题
- 解决了在短时间大批量抓取触发知乎 403 / 429 后，原架构易直接崩溃抛错，无法缓冲延缓重试的问题。
- 彻底封锁了 TUI `HomeStage` 中长 URL 输入撑破固定高度网格（StatusPill）导致界面悬停黑框的恶性视觉 Bug。
- 移除了项目历史迭代中不再具有时效性的临时总结及计划 Markdown，收紧了 `/docs` 下的核心长效文档。

### 影响范围
- `docs/` 相关废弃文档
- `core/api_client.py`
- `core/browser_fallback.py`
- `core/config_schema.py`
- `cli/tui/theme.tcss`
- `cli/tui/widgets.py`

### 风险 / 未完成事项
- `browser.channel` 启动失败回退等机制还需要在生产环境中跑跑看重试开销。

### 下一步
- 进一步观察现有代理配置在集群或重度使用中稳定情况。

---

## 2026-04-04 / `structure-alignment` 十二阶段结构收口与主分支日志对齐

### 相关 commits
- `3e26f6a` Align archive structure and runtime contracts
- `9e033c4` Clarify launcher as the recommended TUI path
- `73fb9fe` Clarify install and platform support contracts
- `2418b21` Stabilize config runtime fallback behavior
- `a0c5d84` Trim dead helpers from CLI entry layer
- `75f420b` Unify workflow defaults and monitor pointer handling
- `783e0d3` Add typed save pipeline failure context
- `3faadb3` Align query surface with typed content keys
- `1b76514` Normalize creator metadata and monitor delta handling

### 本次修改
- 以十二阶段方式对 `structure-alignment` 做了一轮完整收口。
- 阶段 1：冻结基线、跑通现状校验、建立 `structure-alignment` 工作分支。
- 阶段 2：对齐 README / README_EN / MANUAL / built-in manual / workflows 中的产品定位、入口关系和协议优先表达。
- 阶段 3：把 launcher、`interactive`、`interactive --legacy` 的主次关系压清楚。
- 阶段 4：整理安装脚本、Python 基线、平台支持文档和安装契约。
- 阶段 5：稳定配置运行时回退路径，并让配置缺失/损坏场景的行为一致。
- 阶段 6：继续压薄 `cli/app.py`，清掉失去职责的 helper。
- 阶段 7：统一 question-page scrape config 的默认语义，让不同入口复用同一套规则。
- 阶段 8：收 monitor pointer 规则，明确 unsupported-only 新活动与失败项时的推进策略。
- 阶段 9：把保存链路失败升级为 typed context，保留部分已保存结果与失败条目上下文。
- 阶段 10：把 SQLite / query 的稳定身份统一到 `content_key = type:id`。
- 阶段 11：清洗 creator 元信息里的 HTML 残留，并补上 monitor / creator 的直接回归测试。
- 阶段 12：完成完整验证矩阵、命令面 smoke 和最终 branch 收口。
- 同时把 `main` 上更新过的 `CHANGELOG.md` / `DEVLOG.md` 基线同步回 `structure-alignment`，避免两个分支的日志体系继续分叉。

### 解决的问题
- 解决了 `structure-alignment` 上日志文件仍停留在模板占位、无法反映真实阶段工作的情况。
- 解决了入口、安装、配置、workflow、monitor、保存链路、数据库身份和 creator 元信息之间多处“表面清楚、底层不一致”的问题。
- 解决了 query 仍展示裸 `answer_id`、monitor 可能反复扫描 unsupported 头部条目、creator README 落原始 HTML 等具体维护痛点。
- 解决了 `cli/app.py` 继续承担过多历史 helper 的问题，进一步把职责下沉到更稳定的边界。
- 解决了 `structure-alignment` 与 `main` 在 changelog/devlog 记录体系上的漂移。

### 影响范围
- `README.md`
- `README_EN.md`
- `MANUAL.md`
- `cli/app.py`
- `cli/archive_execution.py`
- `cli/config_view.py`
- `cli/creator_metadata.py`
- `cli/healthcheck.py`
- `cli/interactive_legacy.py`
- `cli/launcher_flow.py`
- `cli/manual_content.py`
- `cli/save_contracts.py`
- `cli/save_pipeline.py`
- `cli/workflow_contracts.py`
- `cli/workflow_service.py`
- `core/config_runtime.py`
- `core/cookie_manager.py`
- `core/db.py`
- `core/monitor.py`
- `docs/`
- `.github/workflows/ci.yml`
- `tests/`
- `CHANGELOG.md`
- `DEVLOG.md`

### 风险 / 未完成事项
- `core/scraper.py` 仍然是主复杂度热点，这轮没有深拆。
- 旧 Cookie 路径兼容仍然存在，`check` 已能诊断，但实际迁移还需要后续人工收口。
- legacy / compatibility 路径已经明显降权，但还未完全移除。
- 本轮以结构清晰度和契约收口为主，没有做全平台真机抓取验证。

### 下一步
- 后续新工作建议直接在 `Unreleased` 和新的 DEVLOG 条目里继续累积，不再回到模板占位文件。
- 如继续演进，优先沿 `workflow service`、`save pipeline`、`content_key`、`monitor delta`、`config runtime/schema` 这些已收口边界推进。
- 若准备下一轮大功能或发布，先做一次实网抓取回归和平台验证，再决定是否继续拆 `core/scraper.py`。

---

## 2026-04-02 / 历史基线：项目启动到 TUI 重构落地前的整体沉淀

### 相关 commits
- `53a547d` initial commit: powerful zhihu crawler with stealth and direct markdown conversion
- `9a1f4dc` improve LaTeX rendering, add zhihu signature injection and enhance scraper stealth
- `043e941` clean separation of concerns across three scripts
- `6f41395` restructure project layout (`core/` + `static/`)
- `0239a34` 添加配置管理、日志系统和现代化依赖管理
- `27cb8e9` 重构爬虫引擎为纯协议 API 模式，引入 `curl_cffi` 和动态签名生成
- `a6ad865` 完成增量监控系统 (`CollectionMonitor`) 及 `monitor` CLI
- `090c3d9` 集成 SQLite 数据库存储 (`ZhihuDatabase`) 及 `query` CLI
- `4b7c9d0` 实现 Cookie Pooling 和 Smart Playwright Fallback
- `ad11703` 新增一键安装脚本并优化依赖配置
- `36a7c7f` 接通配置项并统一 Cookie 与输出逻辑
- `e84053e` 新增 `creator` 作者主页抓取模式
- `ace8984` 实现问题页分页抓取与保守节流
- `46d3031` 默认入口切换为 `zhihu` 命令
- `abd888a` 修复知乎公式识别与图片回写
- `a136efa` 重构交互式归档工作台界面
- `42e1265` ~ `1785f17` 完成 Textual TUI 六阶段重构
- `880a08b` 补执行详情面板与合并清单文档
- `8e21e8d` 修复 TUI 多行粘贴与状态卡渲染

### 本次修改
- 项目从最早的知乎页面抓取脚本，逐步演化为本地优先的知乎归档工具。
- 建立了协议优先的抓取链路，并在必要时引入浏览器回退能力。
- 逐步形成了 Markdown + 图片 + SQLite 的本地归档模式。
- 建立了 `fetch / batch / creator / monitor / query` 这一组主命令。
- 引入配置系统、日志系统、Cookie 管理、输出命名与本地运行目录约束。
- 把项目目录从早期脚本集合整理为 `cli/`、`core/`、`static/`、`docs/`、`tests/` 这种可维护结构。
- 完成了 `zhihu` 启动命令切换，减少直接记忆 `python cli/app.py` 的负担。
- 修复了知乎公式识别、图片本地化、Markdown 输出细节、creator 元信息、问题页分页抓取等关键功能。
- 完成了 Textual TUI 六阶段重构，从静态打印式界面切到真正可持续演化的全屏终端工作台。

### 解决的问题
- 解决了早期抓取逻辑分散、协议抓取不稳定、输出结构不统一的问题。
- 解决了 CLI 路径单一且难用的问题，形成了更完整的命令面。
- 解决了 SQLite、monitor、creator 等能力缺失导致项目只能做单次抓取的问题。
- 解决了旧 UI 依赖 `print` 和临时布局导致的缩放错位、粘贴失效、状态卡渲染异常等问题。
- 解决了部分公式、图片回写和本地引用不稳定的问题。
- 解决了安装、Cookie 路径、输出目录、项目结构、README 表达等多处基础可用性问题。

### 影响范围
- `cli/`
- `core/`
- `static/`
- `install.sh`
- `README.md`
- `README_EN.md`
- `data/`
- `tests/`

### 风险 / 未完成事项
- 到这个阶段为止，项目虽然已经不再是单脚本，但仍然存在较明显的大文件压力，特别是 `cli/app.py`、`core/scraper.py`、`core/config.py`。
- TUI 虽然已经成为默认交互入口，但文档、主流程、兼容路径之间当时还没有彻底治理完。
- 配置 schema、runtime loader、typed contracts 在这时还没有完成真正意义上的边界收紧。
- 平台支持仍以 macOS / Linux 为主，Windows 仍缺少稳定工程化路径。

### 下一步
- 做一次正式的系统审计，而不是继续直接堆功能。
- 对 CLI、配置、保存链路、文档体系、平台支持和验证矩阵进行阶段化治理。

---

## 2026-04-03 / `test` 分支六阶段治理、后续 contract tranche 与主线合并

### 相关 commits
- `60e9a98` 导入 SkillsMP 工程治理技能集
- `df86a8c` 收口阶段一技能参考目录结构
- `a490a77` 同步 README 当前能力边界与工程重点
- `8cb0c9b` 补充阶段二质量审计报告
- `048c86c` 收敛环境检查与阶段三基线
- `9ffbc20` 抽离内置说明书内容
- `c7b6983` 拆分首页流程并补文档同步测试
- `a4a18a6` 抽离保存链路并补阶段四回归测试
- `89a875e` 抽离配置展示层并补回归测试
- `297040c` 抽离抓取归一化逻辑并收紧边界
- `c556914` 补阶段五验证矩阵与命令面守卫
- `65a2c67` 补安装契约与 Windows 运行说明
- `5aab82e` 补阶段六发布审查文档
- `4134397` 补阶段六收口与合并操作清单
- `8785797` 抽离配置 schema 并引入抓取结果契约
- `7f1a1bc` 拆分配置运行时并类型化保存结果
- `4195313` 抽离 creator 元数据渲染模块
- `c236e90` 为问题页抓取结果补分页统计契约
- `08fb44b` Merge branch `test` into `main`
- `ad5bbe2` 升级 Python 基线并重构 README
- `3aa7689` 调整 AGENTS 中的 DEVLOG 更新规则
- `5df6520` 引入归档工作流服务层
- `b558d49` 整理文档入口与仓库边界

### 本次修改
- 以 `test` 分支为主线，完成了一轮完整的六阶段工程治理。
- 阶段一整理参考资料、skills 入口、README 方向和仓库治理基线。
- 阶段二完成系统审计，明确命令面、平台支持、文档同步、目录职责、可维护性风险和优先级。
- 阶段三优先解决 P0 可用性问题，包括 `check` 诊断噪音、缺依赖提示、manual 抽离、launcher/onboard 拆分和文档同步测试。
- 阶段四继续做结构重构，把保存链路、配置展示层、抓取载荷归一化逻辑从大文件中拆出。
- 阶段五建立验证矩阵、命令面守卫、安装契约和 Windows runbook，把“靠记忆维护”改成“靠测试和文档约束维护”。
- 阶段六补齐发布审查、issue 回复模板、merge playbook，并明确了如何把 `test` 合回 `main`。
- 六阶段之后继续推进新的工程 tranche，把 `config` 进一步拆成 facade/schema/runtime 等边界，并给 scraper/save 引入更稳定的 typed contracts。
- 抽离 `creator` 元数据渲染与问题页分页统计 contract，进一步为后续 monitor、TUI、batch、未来扩展留出更稳的接口。
- 当天后半段又把 Python 基线升级、README 重构、DEVLOG/CHANGELOG/AGENTS/MANUAL 体系和仓库边界整理推进到 `main`。
- 引入 `workflow service` 层，把 `fetch / batch / creator / monitor` 的编排从 CLI 主入口进一步抽离，为未来 TUI、自动化和 API 化预留扩展窗口。

### 解决的问题
- 解决了“项目已经能用，但没有系统治理框架”的问题。
- 解决了 `cli/app.py` 承担过多职责的问题，开始把 manual、launcher、save pipeline、config view、workflow orchestration 分层。
- 解决了 `README / manual / docs / tests / help` 漂移的问题，建立了同步和守卫。
- 解决了 `zhihu check` 输出过于原始、对维护者不友好的问题。
- 解决了安装契约、平台边界、Windows 状态、命令面事实与文档不一致的问题。
- 解决了配置、保存链路、scraper 结果大量依赖松散 dict 的问题，开始建立 typed contracts。
- 解决了 `test` 分支治理成果无法顺利合回 `main` 时的合并和发布认知问题。
- 解决了根目录文档职责混乱的问题，重新建立了 `README / MANUAL / AGENTS / docs/*` 的分工。

### 影响范围
- `cli/app.py`
- `cli/launcher_flow.py`
- `cli/manual_content.py`
- `cli/healthcheck.py`
- `cli/optional_deps.py`
- `cli/save_pipeline.py`
- `cli/config_view.py`
- `cli/creator_metadata.py`
- `cli/workflow_service.py`
- `cli/workflow_contracts.py`
- `cli/save_contracts.py`
- `core/config.py`
- `core/config_schema.py`
- `core/config_runtime.py`
- `core/scraper.py`
- `core/scraper_payloads.py`
- `core/scraper_contracts.py`
- `tests/`
- `.github/workflows/ci.yml`
- `README.md`
- `README_EN.md`
- `docs/`

### 风险 / 未完成事项
- 虽然边界已经明显清晰，但 `core/scraper.py` 仍然是复杂度热点，后续还需要继续拆。
- `cli/app.py` 已大幅变薄，但命令入口层仍有继续压缩空间。
- Windows 运行说明已经有文档，但工程体验仍未达到第一等支持。
- legacy / compatibility 路径已经被标识清楚，但还不能完全移除。
- typed contracts 已经起步，但还未覆盖所有历史路径和所有错误语义。
- `test` 分支完成治理后合回 `main`，但主线后续仍需要继续做新的版本节奏整理。

### 下一步
- 以 2026-04-04 作为新一轮版本线的起点。
- 继续沿 `workflow service`、`config facade/runtime/schema`、`scraper contracts` 这三个方向推进。
- 继续把 CLI / TUI / core 的边界压清楚。
- 在不打断现有抓取能力的前提下，继续把项目从“阶段化治理后的可维护工具”推进到“更稳定的工业化本地归档系统”。
