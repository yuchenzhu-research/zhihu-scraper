

<div align="center">

# Zhihu-Scraper

**把一个知乎链接变成可读、可迁移的本地归档**

[![CI](https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper)

**简体中文** · [English](README_EN.md)

</div>

Zhihu-Scraper 是一个本地优先的知乎归档工具。输入文章、回答、问题、专栏或独立视频链接，程序会先尝试轻量 HTTP/API 抓取，再按设置回退到浏览器，并把统一的内容模型保存为 Markdown、静态 HTML、SQLite 和本地媒体。

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

正文解析覆盖段落、标题、列表、引用、表格、代码、链接、图片、动图和 TeX 数学公式。独立视频自动选择已知尺寸最大的清晰度；下载中断时保留 `.part` 文件，下次对同一目标再次归档会使用 HTTP Range 续传，并在服务端提供长度时校验最终字节数。单张正文图片、动图或封面失效不会毁掉整篇归档：程序会继续保存正文和其他媒体，并在报告中列出失败项；未下载的远程媒体只显示为普通链接，不会在打开 HTML 时自动请求。独立视频主文件失败则明确报错。

暂不支持专栏合集、内嵌于文章/回答的视频、作者主页、搜索结果、想法、收藏夹和盐选内容。

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
uv sync
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

## 第一次归档

先生成设置文件：

```bash
zhihu init
```

`init` 默认创建 `./settings.toml`，已有文件不会被覆盖。其他命令**不会自动读取**这个文件，因此使用时要明确传入 `-s settings.toml`：

```bash
zhihu check -s settings.toml
zhihu fetch -s settings.toml "https://zhuanlan.zhihu.com/p/357892158"
```

也可以不用设置文件，直接采用内置默认值：

```bash
zhihu fetch "https://www.zhihu.com/zvideo/1666569497233207296"
```

常用的单次覆盖：

```bash
zhihu fetch -s settings.toml --comments URL
zhihu fetch -s settings.toml --no-media URL
zhihu fetch -s settings.toml --browser always URL
zhihu fetch -s settings.toml --cdp http://127.0.0.1:9222 URL
zhihu fetch -s settings.toml -o "/path/to/archive" URL
```

查看完整命令：

```bash
zhihu --help
zhihu fetch --help
zhihu check --help
zhihu init --help
```

## 安全配置 Cookie

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
html = true
sqlite = true
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

[browser]
fallback = "auto"
headless = false
# cdp_url = "http://127.0.0.1:9222"
```

默认生成 Markdown、HTML 和 SQLite，下载媒体；PDF、评论和代理关闭。评论开启后，每个内容按知乎接口返回顺序保存最多 10 条一级评论，每条一级评论最多 10 条二级回复，不足时保存全部。可以在设置中调整 10/10 上限，也可以用 `--comments` 只开启一次。关闭评论表示“本轮不请求”，重复归档会保留 SQLite 与文档中已经抓到的评论；关闭媒体下载时也会继续引用仍存在的本地文件。

`browser.fallback` 有三种模式：

- `auto`：先走 HTTP/API，受阻或载荷无效时尝试浏览器。
- `never`：只使用 HTTP/API。
- `always`：单个目标页面直接使用浏览器载荷。

未配置 CDP 时，程序优先启动系统 Chrome，并在不可用时使用项目管理的 Chromium；两者共用项目自己的持久化浏览器目录。配置 `cdp_url` 后，可连接已经登录的本机 Chrome。出于凭证安全，CDP 只接受 `localhost`、`127.0.0.1` 或 `[::1]` 的 HTTP/WebSocket 地址。

`network.proxy` 会统一应用于 HTTP/API 请求、项目管理的浏览器和媒体下载；连接外部 CDP 时则沿用该浏览器自身的代理设置。请求和媒体下载共用 `timeout` 与有界重试策略，日志会隐藏 Cookie 和代理凭证。

## 本地输出

所有内容共用归档根目录下的 `zhihu.db`。只有“整个专栏”创建 `内容/`：

```text
知乎归档/
├── zhihu.db
└── 机器学习/
    ├── 机器学习.md
    ├── 机器学习.html
    ├── 内容/
    │   ├── 一文归纳AI数据增强之法.md
    │   ├── 一文归纳AI数据增强之法.html
    │   └── RNN_LSTM_BPTT详细推导.md
    ├── media/
    └── assets/
```

专栏同名文件是按年份分组的完整目录，使用“本栏目共 N 篇”；各文章页包含收录专栏、本次归档来源、返回目录和上一篇/下一篇导航。

单篇文章、单个回答、整个问题和独立视频使用精简结构：

```text
知乎归档/
├── zhihu.db
└── 标题/
    ├── 标题.md
    ├── 标题.html
    ├── media/
    └── assets/
```

问题下的回答作为多个章节合并进同一个问题文档，不创建 `内容/`。`media/` 只在确有可下载媒体时创建；`assets/` 在生成 HTML 时保存项目自己的本地阅读样式。HTML 由归一化内容重新生成，不复制知乎的 HTML、CSS 或 JavaScript。

公式会保留原始 TeX：Markdown 使用 `$…$` / `$$…$$`，HTML 则在生成归档时转换为浏览器原生可渲染的本地 MathML，并在 `data-tex` 中保留安全的可追溯表达式；无须联网加载 KaTeX 或 MathJax。生成的 MathML 会移除链接、事件和样式等危险属性，无法转换的表达式安全回退为可读 TeX。

SQLite 当前保存内容、作者、专栏、评论、媒体和可由原始数据确定的关系。它是归档数据层，不代表已经提供搜索或知识图谱功能。

## Python 调用

```python
from pathlib import Path

from zhihu_scraper import ArchiveSettings, archive_url

report = archive_url(
    "https://zhuanlan.zhihu.com/p/357892158",
    ArchiveSettings(output_dir=Path("知乎归档")),
)

print(report.target.title)
print(report.receipt.entry_directory)
```

`archive_url(URL, settings) -> ArchiveReport` 是 CLI、Agent 和未来界面共用的同步入口。网络来源、浏览器和保存器边界都可以通过 `build_workflow` 注入，便于测试和二次开发。

## 三平台与开发验证

核心抓取、归一化、渲染和 SQLite 逻辑在 Windows、macOS、Linux 共用；平台 Adapter 只处理浏览器位置、应用数据目录和安全文件名等真实差异。CI 在三个系统上覆盖 Python 3.12、3.13 和 3.14。知乎接口和反爬策略可能随时变化，自动测试通过不等于任意链接永远可抓。

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

真实知乎烟雾测试默认跳过，只有显式提供本机 Cookie 文件时才运行：

```bash
ZHIHU_LIVE=1 ZHIHU_COOKIE_FILE=/private/path/cookies.json \
  uv run pytest tests/live/test_live_archive.py
```

架构边界见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，已确认但延期的 PDF、关键词搜索、语义搜索和知识图谱见 [docs/FEATURE_TODO.md](docs/FEATURE_TODO.md)。当前不提供原始 JSON 归档。

## 参考与许可

重建设计过程中对照研究了 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)、[CrawlerTutorial](https://github.com/NanmiCoder/CrawlerTutorial)、[Ther-nullptr/zhihu-scraper](https://github.com/Ther-nullptr/zhihu-scraper) 和 [chenluda/zhihu-download](https://github.com/chenluda/zhihu-download)。本仓库实现和测试独立维护，不把外部仓库源码复制进项目。

本项目使用 [MIT License](LICENSE)。
