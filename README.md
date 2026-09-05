<div align="center">

# Zhihu-Scraper

**把一个知乎链接变成可读、可迁移的本地归档**

[![CI](https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper)

**简体中文** · [English](README_EN.md)

</div>

Zhihu-Scraper 是一个本地优先的知乎归档工具。输入文章、回答、问题、专栏或独立视频链接，程序会先尝试轻量 HTTP/API 抓取，再按设置回退到浏览器，并把统一的内容模型保存为 Markdown 和本地媒体；离线 HTML 可按需开启。

项目面向两类使用者：希望研究工程化爬虫的开发者，以及希望让 Codex 等 Agent 代为执行命令的普通用户。它没有 TUI、云端账号或前端构建系统，公开入口保持为一个 CLI 和一个 Python 函数。

> [!CAUTION]
> 仅将本项目用于学习、研究和个人合法归档。请遵守知乎服务条款、robots 规则、内容著作权、隐私要求和所在地法律；不要绕过付费、私密或无权访问的内容，也不要高频请求或把含个人信息的归档再次公开。

## 当前可用范围

| 输入链接 | 归档行为 |
| --- | --- |
| `https://zhuanlan.zhihu.com/p/<文章 ID>` | 单篇文章及其所属专栏信息 |
| `https://www.zhihu.com/question/<问题 ID>/answer/<回答 ID>` | 指定的单个回答 |
| `https://www.zhihu.com/answer/<回答 ID>` | 指定的单个回答 |
| `https://www.zhihu.com/question/<问题 ID>` | 分页抓取问题下的多个回答，并合并为一个文档 |
| `https://www.zhihu.com/column/<专栏 token>` | 专栏目录和专栏内文章 |
| `https://www.zhihu.com/zvideo/<视频 ID>` | 独立知乎视频 |

正文解析覆盖段落、标题、列表、引用、表格、代码、链接、图片、动图和 TeX 数学公式。独立视频自动选择已知尺寸最大的清晰度；下载中断时保留 `.part` 文件，下次对同一目标归档时，有可靠验证信息才使用 HTTP Range 续传，否则安全地重新下载，并在服务端提供长度时校验最终字节数。单张正文图片、动图或封面失效不会毁掉整篇归档：程序会继续保存正文和其他媒体，并在报告中列出失败项；未下载的远程媒体只显示为普通链接，不会在打开 HTML 时自动请求。独立视频主文件失败则明确报错。

文章和回答中的知乎视频卡片可解析并下载已公开的 MP4 等直连文件；解析失败会保留原视频页面链接并显示警告。关闭媒体下载时不请求内嵌视频接口。暂不支持专栏合集、作者主页、搜索结果、想法、收藏夹和盐选内容。

HTTP/API、分页和评论共用请求节奏，默认相邻请求启动间隔为 0.5 秒，加随机 0–0.5 秒。设置 `network.request_interval` 和 `network.request_jitter` 可调整，两项均为 0 时关闭；首个请求不等待。

单次 HTTP 请求的累计重试等待最多 60 秒；服务器要求超长等待或返回无效等待值时，会明确停止并提示稍后重试，不提前重试或转而打开浏览器。

问题和专栏分页允许一页完全重叠；连续两个未结束分页没有新增内容时，会停止并明确报错。正常归档不限制总页数。

## 默认一次抓取会保存什么

不添加额外参数时，一次正常抓取会保存：

- 标题、作者、原始链接、发布时间和可获得的赞同数。
- 段落、标题、列表、引用、表格、代码、超链接和 TeX 数学公式。
- 正文图片、动图、封面；独立 `zvideo` 还会保存描述、原始链接和已知尺寸最大的清晰度。
- 文章的所属专栏信息，回答对应的问题信息，问题详情及全部可访问回答，或者专栏简介、目录及全部可访问文章。
- 可阅读的 `.md` 和成功下载的 `media/` 文件。

默认**不生成 HTML，也不抓评论**。传入 `--html` 才生成可直接双击打开的离线 `.html` 和本地样式；传入 `--comments` 才抓取最多 10 条一级评论及每条最多 10 条二级回复。两个选项也可以在设置文件中长期开启。项目不创建 SQLite 数据库、原始 JSON、搜索索引或知识图谱；传入 `--pdf` 可额外生成 PDF。

## 安装

需要 Python 3.12 或更高版本。建议保留项目自己的 `.venv`，避免污染系统 Python。

### macOS / Linux 安装脚本

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
./scripts/install.sh
source .venv/bin/activate
```

脚本会一次安装项目依赖和项目管理的 Chromium 浏览器；在 Linux 上也会安装浏览器所需的系统库，系统可能要求输入 `sudo` 密码。

### Windows PowerShell 安装脚本

```powershell
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
.\scripts\install.ps1
.\.venv\Scripts\Activate.ps1
```

PowerShell 脚本同样会安装项目管理的 Chromium。

### 使用 uv

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
uv sync --locked
uv run playwright install chromium
uv run zhihu --help
```

全新的 Linux 环境请把浏览器命令改为 `uv run playwright install --with-deps chromium`，以同时安装系统库。

### 手动使用 pip

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m playwright install chromium
```

Playwright 属于核心运行依赖，因为浏览器回退是可靠抓取链路的一部分；Chromium 二进制仍需要执行一次安装命令。项目使用独立虚拟环境是为了隔离依赖和命令入口，并不意味着爬虫本身必须运行在容器中。

全新的 Linux 环境应使用 `python -m playwright install --with-deps chromium`。

## 命令怎么选

所有功能都从 `zhihu` 这一个命令进入。最常用的选择放在一起：

| 目的 | 命令 | 结果 |
| --- | --- | --- |
| 查看当前版本 | `zhihu --version` | 确认正在使用项目当前版本 |
| 普通归档 | `zhihu fetch URL` | Markdown + 下载媒体 |
| 同时生成网页 | `zhihu fetch --html URL` | Markdown + 离线 HTML + 下载媒体 |
| 生成 PDF | `zhihu fetch --pdf URL` | Markdown + 媒体 + PDF |
| 同时抓取评论 | `zhihu fetch --comments URL` | Markdown + 媒体 + 10×10 评论 |
| 网页和评论都要 | `zhihu fetch --html --comments URL` | 同时开启两个可选能力 |
| 不下载媒体 | `zhihu fetch --no-media URL` | Markdown 中保留远程媒体链接 |
| 指定输出目录 | `zhihu fetch -o "/path/to/archive" URL` | 覆盖本次保存位置 |
| 强制浏览器抓取 | `zhihu fetch --browser always URL` | 跳过 HTTP 内容路径 |

第一次需要 Cookie 或希望长期保存选项时，再生成设置文件：

```bash
zhihu init
```

`init` 默认创建 `./settings.toml`，已有文件不会被覆盖。其他命令**不会自动读取**这个文件，因此使用时要明确传入 `-s settings.toml`：

```bash
zhihu check -s settings.toml
zhihu fetch -s settings.toml "https://zhuanlan.zhihu.com/p/357892158"
```

也可以完全不用设置文件，直接采用内置默认值：

```bash
zhihu fetch "https://www.zhihu.com/zvideo/1666569497233207296"
```

设置文件中的选项仍可被本次命令覆盖：

```bash
zhihu fetch -s settings.toml --html URL
zhihu fetch -s settings.toml --comments URL
zhihu fetch -s settings.toml --no-html URL
zhihu fetch -s settings.toml --no-media URL
zhihu fetch -s settings.toml --browser always URL
zhihu fetch -s settings.toml --cdp http://127.0.0.1:9222 URL
zhihu fetch -s settings.toml -o "/path/to/archive" URL
```

查看完整命令：

```bash
zhihu --version
zhihu --help
zhihu fetch --help
zhihu login --help
zhihu check --help
zhihu init --help
```

PDF 默认关闭，可用 `--pdf` 或 `archive.pdf = true` 开启。只要安装了 Chrome 或执行过 `playwright install chromium`，即可由隔离的无登录浏览器打印本地内容；PDF 导出不请求远程资源，支持中文、公式、表格和已下载图片。视频保留原链接，不嵌入可播放视频。专栏为目录和每篇文章分别生成 PDF，整体移动目录后相对导航仍有效（取决于阅读器是否允许打开本地链接）。仅需 PDF 时，在设置中使用 `markdown = false`、`html = false`、`pdf = true`；不留下中间 HTML 或样式文件。

## 安全配置 Cookie

推荐运行 `zhihu login`，在打开的浏览器中完成登录。命令最多等待 180 秒，通过知乎身份接口验证后才原子保存 Cookie；默认位置为 `.local/cookies.json`。取消、超时或保存失败都会保留旧文件。按命令输出把 `network.cookie_file` 写入设置，再显式使用 `-s settings.toml`。使用 `zhihu login -s settings.toml` 可更新已配置的文件；普通抓取不会自动覆盖 Cookie。

已有开启本机 CDP 的登录浏览器时，可运行 `zhihu login --cdp http://127.0.0.1:9222`；只读取知乎 Cookie，不操作已有页面。文件保存时会限制为当前用户访问，文件内容不加密。也可以继续手工导入：

公开内容不一定需要登录，但部分接口会要求有效会话。项目读取浏览器导出的 JSON Cookie 文件，支持常见的对象格式和 `name` / `value` 列表格式。为避免误传其他网站凭证，列表格式只接收明确标记为 `zhihu.com` 或其子域的记录；对象格式应只放知乎 Cookie。

1. 只从你本人已登录的知乎浏览器会话导出 Cookie，并使用你信任的浏览器工具。
2. 把文件放在不会同步或提交的位置；仓库内推荐 `.local/cookies.json`，`.local/` 已被 Git 忽略。
3. `settings.toml` 只保存文件路径，绝不写入 Cookie 值。

最小对象格式如下；尖括号内容应替换为你自己的值，但不要把真实值发到 Issue、聊天或日志中：

```json
{
  "z_c0": "<your z_c0 value>",
  "d_c0": "<your d_c0 value>"
}
```

在 `settings.toml` 中只配置路径：

```toml
[network]
cookie_file = ".local/cookies.json"
```

然后检查字段和真实登录状态：

```bash
zhihu check -s settings.toml
```

也可以临时检查另一个文件：

```bash
zhihu check --cookie-file /private/path/cookies.json
```

macOS / Linux 可额外执行 `chmod 600 .local/cookies.json`。Cookie 等同于登录凭证；一旦怀疑泄露，应立即在知乎退出相关会话并重新登录。`check` 只报告字段是否齐全和会话是否有效，不打印 Cookie 值。

## `settings.toml`

`zhihu init` 生成的默认设置如下：

```toml
[archive]
output_dir = "知乎归档"
markdown = true
html = false
pdf = false
comments = false
comment_roots = 10
comment_replies = 10
media_download = true

[network]
# cookie_file = ".local/cookies.json"
# proxy = "http://127.0.0.1:7890"
timeout = 30.0
retries = 3
page_size = 20
request_interval = 0.5
request_jitter = 0.5

[browser]
fallback = "auto"
headless = false
# cdp_url = "http://127.0.0.1:9222"
```

默认生成 Markdown 并下载媒体；HTML、PDF、评论和代理关闭。`--html` 只开启本次离线 HTML，也可以将 `html = true` 写入设置长期开启。评论开启后，每个内容按知乎接口返回顺序保存最多 10 条一级评论，每条一级评论最多 10 条二级回复，不足时保存全部。可以在设置中调整 10/10 上限，也可以用 `--comments` 只开启一次。关闭评论表示本轮不请求评论，重复归档时文档只反映本轮结果；关闭媒体下载时不会下载新文件，正文中的远程媒体保留为普通链接。

`browser.fallback` 有三种模式：

- `auto`：先走 HTTP/API，受阻或载荷无效时尝试浏览器。
- `never`：只使用 HTTP/API。
- `always`：单个目标页面直接使用浏览器载荷。

未配置 CDP 时，程序优先启动系统 Chrome，并在不可用时使用项目管理的 Chromium；两者共用项目自己的持久化浏览器目录。配置 `cdp_url` 后，可连接已经登录的本机 Chrome。出于凭证安全，CDP 只接受 `localhost`、`127.0.0.1` 或 `[::1]` 的 HTTP/WebSocket 地址。

`network.proxy` 会统一应用于 HTTP/API 请求、项目管理的浏览器和媒体下载；连接外部 CDP 时则沿用该浏览器自身的代理设置。请求和媒体下载共用 `timeout` 与有界重试策略，日志会隐藏 Cookie 和代理凭证。

## 本地输出

只有“整个专栏”创建 `内容/`。默认结构是：

```text
知乎归档/
└── 机器学习/
    ├── 机器学习.md
    ├── 内容/
    │   ├── 一文归纳AI数据增强之法.md
    │   └── RNN_LSTM_BPTT详细推导.md
    └── media/
```

专栏同名文件是按年份分组的完整目录，使用“本栏目共 N 篇”；各文章页包含收录专栏、本次归档来源、返回目录和上一篇/下一篇导航。

单篇文章、单个回答、整个问题和独立视频默认使用精简结构：

```text
知乎归档/
└── 标题/
    ├── 标题.md
    └── media/
```

使用 `--html` 或 `html = true` 后，同级增加同名 `.html`，并创建保存本地阅读样式的 `assets/`；专栏 `内容/` 中的每篇文章也会增加对应 HTML。问题下的回答作为多个章节合并进同一个问题文档，不创建 `内容/`。`media/` 只在确有可下载媒体时创建。HTML 由归一化内容重新生成，不复制知乎的 HTML、CSS 或 JavaScript。

公式会保留原始 TeX：Markdown 使用 `$…$` / `$$…$$`，HTML 则在生成归档时转换为浏览器原生可渲染的本地 MathML，并在 `data-tex` 中保留安全的可追溯表达式；无须联网加载 KaTeX 或 MathJax。生成的 MathML 会移除链接、事件和样式等危险属性，无法转换的表达式安全回退为可读 TeX。

中断下载会留下 `.part` 和临时 `.part.resume`，后者仅保存资源指纹、验证信息和总长度，成功后自动清理。续传使用 `If-Range` 确认资源版本；缺少可靠验证信息时从头下载。有已知媒体长度时会检查现有文件，损坏缓存会重新下载；未知长度的已有文件不额外请求远端验证。

媒体文件名区分实际资源地址：封面或媒体换源会下载新文件；仅已知签名参数 `pkey` / `expiration` 刷新时复用同一资源。升级前的旧媒体文件会保留，首次重跑可能重新下载。

专栏先完成正文与样式写入，再发布目录；正文或样式写入失败时不会发布新目录。每个文件单独原子替换，已完成的正文不会回滚。

重复归档按知乎内容 ID 复用现有目录和文件路径。标题变化时，正文标题和导航会更新，文件名可能保留旧标题；专栏中已不可访问的文章文件会保留，但本轮目录只列出当前获取的文章。遇到无法确认归属的同名文件或目录时会使用避让名称。

项目刻意不维护数据库、搜索索引或知识图谱。Markdown、媒体和按需生成的 HTML 就是完整归档，便于用户直接阅读、移动、备份或删除，不产生额外的隐藏状态。

## Python 调用

```python
from pathlib import Path

from zhihu_scraper import ArchiveSettings, archive_url

report = archive_url(
    "https://zhuanlan.zhihu.com/p/357892158",
    ArchiveSettings(output_dir=Path("知乎归档"), html=True),
)

print(report.target.title)
print(report.receipt.entry_directory)
```

`archive_url(URL, settings) -> ArchiveReport` 是 CLI、Agent 和未来界面共用的同步入口。网络来源、浏览器和保存器边界都可以通过 `build_workflow` 注入，便于测试和二次开发。 自定义保存器必须返回结构化的 `ArchiveReceipt`，统一提供输出路径与媒体失败信息；无效回执会明确报错。

## 三平台与开发验证

核心抓取、归一化、渲染和媒体逻辑在 Windows、macOS、Linux 共用；平台 Adapter 只处理浏览器位置、应用数据目录和安全文件名等真实差异。CI 在三个系统上使用锁定依赖覆盖 Python 3.12、3.13 和 3.14，并在 Ubuntu 单独验证允许范围内的新依赖与浏览器启动。知乎接口和反爬策略可能随时变化，自动测试通过不等于任意链接永远可抓。

开发环境：

```bash
uv sync --locked --extra dev
uv run playwright install chromium
```

完整本地质量门禁：

```bash
PYTHONWARNINGS=error::ResourceWarning uv run pytest
uv run ruff check zhihu_scraper tests
uv run ruff format --check zhihu_scraper tests
uv run mypy zhihu_scraper
uv run python -m compileall -q zhihu_scraper
uv lock --check
uv run zhihu --help
```

真实知乎烟雾测试是单独的显式测试套件，因此普通确定性测试不会再显示被跳过的联网测试：

```bash
ZHIHU_LIVE=1 ZHIHU_COOKIE_FILE=/private/path/cookies.json \
  uv run pytest tests/live/live_archive.py
```

架构边界见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，后续功能路线见 [docs/FEATURE_TODO.md](docs/FEATURE_TODO.md)。当前不提供数据库或原始 JSON 归档。

## 参考与许可

重建设计过程中对照研究了 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)、[CrawlerTutorial](https://github.com/NanmiCoder/CrawlerTutorial)、[Ther-nullptr/zhihu-scraper](https://github.com/Ther-nullptr/zhihu-scraper) 和 [chenluda/zhihu-download](https://github.com/chenluda/zhihu-download)。本仓库实现和测试独立维护，不把外部仓库源码复制进项目。 参考版本和用途记录在 [架构文档的参考清单](docs/ARCHITECTURE.md#8-外部参考版本)，便于换机器后复现研究基线。

本项目使用 [MIT License](LICENSE)。
