# 架构说明

> 状态：2026-09-06 文件优先架构。本文描述已经落地的模块职责和稳定 seam；延期能力见 `FEATURE_TODO.md`。

## 1. 外部 interface

对 CLI、Agent 或未来其他调用者，只暴露一个归档行为：

```text
archive_url(URL, settings, progress=callback) → ArchiveReport
```

调用者只需要提供知乎 URL 和少量用户设置。URL 类型识别、登录态、浏览器回退、媒体下载、目录创建和保存顺序都隐藏在归档模块内部。

## 2. 主流程

```text
知乎 URL
  → URL 路由
  → HTTP 抓取 / 浏览器回退
  → 归一化内容模型
  ├→ 媒体下载
  ├→ Markdown 渲染
  ├→ HTML 渲染（显式开启）
  └→ PDF 打印（显式开启、隔离离线浏览器）
```

模块 seam：

- URL 路由：把输入识别为文章、回答、问题、专栏或独立视频目标。
- 知乎来源 Adapter：获取原始数据，不负责输出格式。
- 归一化模块：把不同知乎载荷转换为同一种内容模型。
- 内嵌视频解析：通过固定 lens 接口把视频卡片转换为媒体模型；不可用时保留原链接与结构化警告。
- 媒体模块：下载、验证资源版本后续传和校验图片、动图与视频；已知长度的缓存文件先检查完整性。
- Markdown 渲染器：只根据内容模型生成 Markdown。
- HTML 渲染器：只根据内容模型生成静态 HTML 和本地资源引用；数学公式转换为原生 MathML，同时保留原始 TeX。
- PDF 导出：复用 HTML/MathML，在不含登录态的浏览器中离线打印；PDF 内保留出处与相对导航，不保存中间 HTML。
- 文件归档模块：负责可读目录、原子写入、专栏导航和本地媒体引用；通过原文稳定标识复用归档路径。
- 运行平台 Adapter：封装 Windows、macOS、Linux 的真实差异。

批量保存通过 `ArchiveSink.begin_batch` 返回一个拥有生命周期的 session，提供 `write_item`、`finish`、`interrupt`。工作流逐项归一化、补评论和解析视频后写入；分页重试用已交付 ID 去重，视频解析缓存也在本次工作流内共享。session 在每项保存成功后更新可读进度并复用媒体回执，最终只再渲染一次完整文档，不在每个检查点重渲染全部旧正文。

CLI 只编排归档行为，不包含抓取、转换或文件命名规则。项目不维护数据库、搜索索引或知识图谱，也不保留对应的兼容 interface。

## 3. 归一化内容模型

内容模型表达知乎内容的含义，而不是某个接口的 JSON 形状：

- 稳定知乎标识、原始 URL、标题和内容类型
- 作者、发布时间、更新时间和可获得的统计信息
- 段落、标题、列表、引用、表格、代码、链接和数学公式
- 图片、动图、封面、独立视频和带稳定 lens ID 的内嵌视频卡片
- 问题与回答、文章与所属专栏
- 可选的一级评论与二级回复

渲染器只能依赖内容模型，不能读取 HTTP 响应、Cookie 或浏览器对象。

## 4. 文件归档结构

只有整个专栏使用 `内容/`。默认只生成 Markdown 和媒体：

```text
知乎归档/
└── 机器学习/
    ├── 机器学习.md
    ├── 内容/
    │   ├── 一文归纳AI数据增强之法.md
    │   └── ...
    └── media/
```

单篇文章、单个回答、问题下多个回答和独立视频使用精简结构：

```text
知乎归档/
└── 标题/
    ├── 标题.md
    └── media/
```

开启 HTML 后，同级增加同名 `.html` 和本地样式 `assets/`，专栏 `内容/` 中的文章也增加对应 HTML。问题下多个回答合并为同一个问题文档，不创建 `内容/`。`media/` 和 `assets/` 只在有对应产物时创建。文件名优先可读，并统一处理同名、系统保留名称、字符长度和 UTF-8 字节长度。

开启 PDF 后生成同名 `.pdf`，专栏目录与文章各一份；只开 PDF 时不留下 HTML 或样式文件。PDF 的标准 Creator 字段与可见出处共同用于重跑身份识别。

归档通过文档出处的内容类型与稳定 ID 识别原有目录，标题变化不制造新的副本；媒体源变化时生成新媒体路径，旧文件保留供用户自行清理。专栏先保存文章，再发布完整目录。

问题/专栏另有可读的 `归档进度.md`，保留出处、完成状态及已保存文件链接。问题中途的回答放在 `回答片段/`，PDF-only 专栏中途正文放在 `归档片段/`；本轮完整产物成功后清理对应片段。重跑重新枚举 API 列表、复用稳定路径和有效媒体，不保存服务端游标，也不声称跳过所有网络请求。

Markdown、媒体和按需生成的 HTML/PDF 就是完整归档；目录可以整体阅读、移动、备份或删除，不依赖隐藏状态。

## 5. 设置与可选行为

普通用户可见设置保持少而稳定：

- 保存目录
- Markdown、HTML 和 PDF 输出开关
- 媒体下载开关
- 评论开关及 10/10 数量
- 浏览器回退、CDP、代理、超时与重试
- 请求基础间隔与随机抖动（分别默认 0.5 秒，设为 0 可关闭）

默认生成 Markdown 并下载媒体；HTML、PDF、评论和代理默认关闭。HTML 只有在 `html = true` 或传入 `--html` 时生成；评论只有在 `comments = true` 或传入 `--comments` 时抓取。关闭评论表示本轮不请求，重复归档时文档只反映本轮获取的数据，不从数据库或其他隐藏状态恢复旧评论。

独立视频和已解析内嵌视频固定选择已知尺寸最大的清晰度。图片、动图、公式、断点续传、原始链接和日志脱敏属于固定可靠行为，不制造多余开关。

`network.proxy` 贯穿 HTTP/API、项目管理浏览器和媒体下载。外部 CDP 浏览器的代理由该浏览器自己管理。单篇、分页和评论共用一次浏览器恢复策略；耗尽 429 或 Retry-After 等待预算时直接停止。HTTP 重试解析 Retry-After 的秒数和日期，累计等待超过 60 秒或非法等待值会明确停止；连续分页无新增 ID 时停止，即使游标不断变化。认证 HTTP 请求不跨域自动重定向；媒体初始地址、DNS 和每一跳重定向分别校验。HTTP 客户端、浏览器上下文和工作流都具有明确的关闭 seam。

`login_session`/`zhihu login` 允许用户手动登录，经身份接口验证后原子保存独立 Cookie 文件；默认 180 秒截止，取消或失败保留旧文件。CDP 登录只读取当前知乎 Cookie，不操作用户已有页面。文件权限通过平台 Adapter 限制为当前用户，但不提供加密存储。普通抓取的会话回流只更新本次 HTTP 客户端，不自动覆盖磁盘 Cookie。

`ArchiveReport` 和 `ArchiveReceipt` 是明确的结构化结果，包含输出路径、浏览器使用情况、媒体失败与内嵌视频警告；归档 sink 必须返回正确类型，CLI 不猜测对象字段。

## 6. 三平台 Adapter

程序启动时检测一次运行平台。平台 Adapter 只处理真正变化的行为：

- 浏览器发现、安装和进程管理
- 用户数据与缓存目录
- 平台特有的文件占用与路径行为
- Cookie 文件的 POSIX 权限与 Windows ACL
- Windows 保留名称和跨平台安全文件名；按 UTF-16 核算总路径、媒体及临时后缀的余量，缩短新名称并保留已有路径身份

URL、内容模型、渲染、媒体和知乎字段解析保持共用，业务模块中不得散落操作系统判断。

## 7. 迁移与验证

每项能力按照一个纵向闭环迁移：

1. 用公共 interface 写行为测试。
2. 实现通过测试的最小路径。
3. 加入真实但可控的集成样例。
4. 删除已经被替代的实现。
5. 提交并推送。

单元/集成测试使用固定数据；默认测试只收集确定性测试。`tests/live/live_archive.py` 是必须显式指定文件并传入 Cookie 的受控在线烟雾套件，不在普通测试中制造 skip。完整门禁覆盖 pytest、Ruff、mypy、`compileall`、锁文件、CLI smoke 和三系统 CI。

## 8. 外部参考版本

以下清单锁定本地研究资料的版本。参考源码不纳入主项目、不参与运行或测试，也不自动更新；重新克隆主项目后，需要按来源地址单独获取并检出对应提交。本文中的 commit 是研究基线，并不宣称始终为上游最新版。

| 本地目录 | 来源 | 固定 commit | 参考用途 |
| --- | --- | --- | --- |
| `MediaCrawler` | [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | `17f66121e0fcc40fc23958b995bec873d422667d` | HTTP/浏览器会话、错误分类与请求重试 |
| `CrawlerTutorial` | [NanmiCoder/CrawlerTutorial](https://github.com/NanmiCoder/CrawlerTutorial) | `43cc58cf48b6d070d48cc8525a481588e7b94fd7` | 爬虫基础和工程化学习资料 |
| `zhihu-scraper` | [Ther-nullptr/zhihu-scraper](https://github.com/Ther-nullptr/zhihu-scraper) | `6c7730a6362096d12c8fb97b421a1b6768fed813` | 知乎正文与内容结构 |
| `zhihu-download` | [chenluda/zhihu-download](https://github.com/chenluda/zhihu-download) | `0c4fa675ccdaadb6cf322620adb7a409282fbb1c` | 知乎本地导出与可读输出 |
| `scrapy` | [scrapy/scrapy](https://github.com/scrapy/scrapy) | `185d6b9a20b7d0e77f4c60435d17e5072bd4d704` | 分页、请求调度和抓取生命周期 |
| `yt-dlp` | [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) | `d23e6f5a387d5933bc24e1eb5437da8fd563c1f0` | 媒体格式与下载恢复 |
| `you-get` | [soimort/you-get](https://github.com/soimort/you-get) | `049548f3f3f35e67ba8d3181c71fdc71d11cf260` | 媒体下载处理 |
| `lux` | [iawia002/lux](https://github.com/iawia002/lux) | `dd00f6d258d80b6684a0b9402d7124e5c18ef42f` | 媒体提取与格式选择 |
| `WechatSogou` | [chyroc/WechatSogou](https://github.com/chyroc/WechatSogou) | `6a7e08caa82dd7cf47331d7c303f578a4b325360` | 其他平台抓取设计对照 |
| `weiboSpider` | [dataabc/weiboSpider](https://github.com/dataabc/weiboSpider) | `720d52a58aeff3bdafdc552b90443842ebb94ba7` | 其他平台归档与评论处理 |

核对日期：2026-09-05。MediaCrawler、Scrapy、yt-dlp 的本地研究基线分别落后本次核对的上游 15、254、104 个提交；其他七个有效参考一致。MediaCrawler 这批差异没有修改 `media_platform/zhihu/`。

`references/external/openclaw` 只有 Git 目录，无有效 HEAD，不属于可用的研究基线；项目不依赖它。
