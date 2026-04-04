# DEVLOG

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
