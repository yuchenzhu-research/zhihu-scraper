# Zhihu Scraper v3.0 - System Architecture & Handover Document

这份文档专为后续接手的 AI Agent（如 Claude Code）编写，旨在系统性、无废话地剖析当前项目的核心架构、颗粒度设计以及未来的演进路线。

## 1. 项目定位与核心演进 (Mission & Evolution)
本项目最初依赖于笨重的 Playwright（无头浏览器）进行 DOM 渲染和抓取，导致 CPU/内存占用极高且速度受限。
在 **v3.0** 架构中，项目完成了**“纯 API 协议层”**的彻底重构。我们直接与知乎的后端 JSON API 交火，通过模拟浏览器底层网络指纹并本地动态计算加密签名，实现了毫无渲染开销的毫秒级数据获取。

## 2. 核心技术栈 (Tech Stack)
*   **网络欺骗与通行**: `curl_cffi` (完美模拟 Chrome 的 TLS/HTTP2 握手指纹，突破知乎基础 WAF 拦截)。
*   **逆向签名桥接**: `PyExecJS` + `z_core.js` (在本地 Python 环境中执行 V8 引擎，毫秒级动态生成知乎 `x-zse-96` 接口防刷签名)。
*   **持久化数据仓**: SQLite3 (`core/db.py`) + Markdown 文件双轨存储。既有文本阅览性，又具备 SQL 的强检索和防重排异能力。
*   **终端交互 (CLI/UI)**: `typer` (路由构建) + `rich` (表格与进度条) + `questionary` (终端选项板)。
*   **高并发管控**: `asyncio` + `httpx` (图片资源的高并发下载池)。

---

## 3. 代码库粒度拆解 (Granularity & Directory Structure)
当前的颗粒度非常清晰，严格遵循领域驱动设计 (DDD) 的分层思想，杜绝了面条代码：

*   **`cli/` (入口与视图层)**
    *   `app.py`: 核心 Typer CLI 路由。定义了 `fetch`, `batch`, `monitor`, `query` 等核心命令，负责解析用户传参并下发给 core 层，最后整合 UI 输出。
    *   `interactive.py`: 绚丽的 "Americana Fusion" 交互式仪表盘终端（通过 `zhihu interactive` 触发），是对传统命令行输入的图形化增强。
*   **`core/` (核心业务逻辑层 - 极其重要)**
    *   **`api_client.py`**: 万物之源。这里封装了向知乎发起 API 请求的底层通道。负责合并 Cookie、生成时间戳、调用 `z_core.js` 算签名、附带 TLS 指纹，最后返回纯净的 Dict 数据。
    *   **`scraper.py`**: 页面级业务编排。负责判断 URL 类型（问题/回答/专栏），向 `api_client` 要数据，提取出标题、正文 HTML、作者信息等上下文，并统筹图片下载工作。
    *   **`converter.py`**: Markdown 转换器。接收 HTML，将其中的图片替换为本地相对路径，处理数学公式、加粗等标签，输出标准 Markdown 字符串。
    *   **`db.py`**: 结构化数据库访问层 (DAL)。负责维护 `data/zhihu.db`，包含 `articles` 建表、全文索引、基于 `answer_id` 的 UPSERT (冲突更新/防重识别) 以及 keyword 模糊查询。
    *   **`monitor.py`**: 增量抓取引擎。通过拉取收藏夹的页面并比对 `.monitor_state.json` 中的 Last ID，计算出“增量 Delta”，避免重复请求扫描整个几十万条收藏夹。
*   **`z_core.js` (资产库)**: 绝密的逆向环境。包含了知乎 `x-zse-96` 的加密混淆算法。
*   **`data/` (输出库)**: 无需进入 Git 追踪的内容产生地，包含 `zhihu.db`、各种子文件夹(`.md` + `images/`)。

---

## 4. 核心工作流解析 (Core Workflows)

1.  **单体拉取 (`zhihu fetch <url>`)**:
    Input URL -> `scraper.py` 检测类型 -> `api_client` 获取加密数据 -> 提取图片 URL -> `httpx` 并发落盘图片 -> `converter.py` 将混杂 HTML 转 MD -> `db.py` 写入 SQLite -> 并且保存为 `data/标题/index.md`。
2.  **增量监控 (`zhihu monitor <collection_id>`)**:
    调度 `monitor.py` -> 读 `.monitor_state.json` 的顶端指针 -> 调用 `api_client.get_collection_page` 翻页 -> 遇到已知指针则立即阻断 -> 将新增的 10\~50 篇文章丢给并发池 (`_batch_concurrent`) 批量跑上面的流程 1 -> 抓取成功后更新状态文件的指针。
3.  **秒级检索 (`zhihu query <keyword>`)**:
    `cli/app.py` 调起 -> `db.search_articles(keyword)` 执行 SQL Like 扫描 -> `rich` 渲染表格返回终端。

---

## 5. 当前唯一的遗留局限 (Current Limitations)
**专栏文章 (Zhuanlan Article) 的极强风控**:
知乎对其 `zhuanlan.zhihu.com` 的防护策略远高于正常的问答 (`zhihu.com/question/...`)。即使我们采用了 `curl_cffi` 进行 TLS 指纹欺骗，在请求专栏 API (`/v4/articles/` 或直接请求页面 HTML) 时，依然有极高概率遭遇 `403` 或触发安全验证。目前 v3.0 的核心突破点全在问答体系上。

---

## 6. 未来的史诗级升级方向 (Future Upgrade Paths for Claude Code)

未来的开发迭代应当围绕**“防封”、“生态输出”和“AI 内化”**三个维度展开，建议优先考虑以下路径：

### ⬆️ Direction 1: 专栏智能降级/回退机制 (Smart Playwright Fallback)
由于专栏 API 极难攻破，可以在 `scraper.py` 的 `_extract_article` 中加入 Fallback 逻辑。
**思路**：默认走 `curl_cffi` API，如果触发了 403 异常，迅速静默唤起一层封装好的 `Playwright` 实例，携带本地 `cookies.json`，模拟正常滚动到底部拿到 HTML 后就销毁。用少量的计算代价换区专栏文章的 100% 获取率。

### ⬆️ Direction 2: 私域知识库的 RAG 与向量检索 (Vectorize for RAG)
随着 SQLite 中积攒成千上万篇深度好文，传统的 `LIKE "%检索%"` 已经不够用。
**思路**：扩展 `core/db.py`，引入轻量级的向量存取方案 (如 `chromadb` 或是 `sqlite-vss` / `lancedb`)。在 `_fetch_and_save` 完毕后，调用 OpenAI / BGE embedding 模型，对文本进行向量化并存库。最后在前端 CLI 新增一个命令：`zhihu ask "大模型的底层原理是什么？"`，实现真正的私域知识问答大脑。

### ⬆️ Direction 3: 知识图谱与双链笔记导出管线 (Obsidian/Notion Pipeline)
把抓回来的死文本变成活的知识图谱。
**思路**：增加 `zhihu export --format obsidian` 指令。根据 SQLite 中记录的 Author, Collection_ID, Tags，在导出 Markdown 时自动往文首硬编码 YAML Frontmatter，并将专有名词替换为 `[[双链接]]` 格式，瞬间构建个人的 Obsidian 知乎宇宙网。

### ⬆️ Direction 4: 异构多节点与强化 Cookie 池 (Cookie Pooling & Proxy Rotator)
目前项目是单机单号。如果用户手握几十万内容的终极收藏夹想要“全量清洗”，极易触发封禁。
**思路**：重构 `core/api_client.py` 与 `cookies.json`，让系统支持从多行文本甚至 Redis 中读取 Cookie 列表并随机轮询；同时对接市面上的隧道动态代理（每次 API 请求自动更换 IP）。将这台战车从“单兵作战”提升至“集群作业”级别。
