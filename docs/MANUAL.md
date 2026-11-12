# Zhihu-Scraper 使用手册

**简体中文** · [繁體中文](MANUAL_ZH_HANT.md) · [English](MANUAL_EN.md) · [项目首页](../README.md)

[安装与更新](#install) · [常用命令](#commands) · [登录与 Cookie](#login) · [配置](#settings) · [输出文件](#outputs) · [中断与续抓](#resume) · [排查问题](#troubleshooting)

<a name="install"></a>

## 安装与更新

准备 Git 和 Python 3.12 或更新版本。先克隆项目，进入仓库目录后任选一种安装方式。

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
```

### 使用 uv

在 Windows、macOS 和 Linux 上都可以用 [uv](https://docs.astral.sh/uv/getting-started/installation/) 按仓库锁定的版本安装依赖。

```bash
uv sync --locked
uv run zhihu --version
```

浏览器用于登录、抓取回退和 PDF 导出。程序会优先尝试系统 Chrome，找不到可用的 Chrome 时可安装项目使用的 Chromium。在刚安装的 Linux 上，用第二条命令一起安装浏览器所需的系统库，系统可能提示输入 `sudo` 密码。

```bash
uv run playwright install chromium
# Linux 上需要一并安装系统库时
uv run playwright install --with-deps chromium
```

更新已有副本时，在仓库目录运行 `git pull --ff-only` 和 `uv sync --locked`。Chromium 由 Playwright 管理时，更新后可再次运行浏览器安装命令。

### 使用安装脚本

脚本会在仓库中创建 `.venv`，安装项目和 Chromium，并在 Linux 上安装浏览器所需的系统库。

**macOS / Linux**

```bash
./scripts/install.sh
source .venv/bin/activate
zhihu --version
```

**Windows PowerShell**

```powershell
.\scripts\install.ps1
.\.venv\Scripts\Activate.ps1
zhihu --version
```

### 手动用 pip 安装

在仓库目录运行 `python -m venv .venv`，然后用上面对应平台的命令激活环境。macOS 或 Linux 上可使用指向 Python 3.12 或以上版本的 `python3`。

```bash
python -m pip install -e .
python -m playwright install chromium
```

Linux 上需要一并安装系统库时，使用 `python -m playwright install --with-deps chromium`。已经激活 `.venv` 的用户，执行下文命令时可去掉 `uv run`。

<a name="commands"></a>

## 常用命令

把下面的 `"URL"` 替换为带 `https://` 的完整知乎链接。可归档的链接类型见[项目首页](../README.md)。

| 想做什么 | 命令 |
| --- | --- |
| 保存 Markdown 和本地媒体 | `uv run zhihu fetch "URL"` |
| 同时保存离线 HTML | `uv run zhihu fetch --html "URL"` |
| 同时生成 PDF | `uv run zhihu fetch --pdf "URL"` |
| 同时保存评论 | `uv run zhihu fetch --comments "URL"` |
| 只保留媒体原链接 | `uv run zhihu fetch --no-media "URL"` |
| 指定保存目录 | `uv run zhihu fetch -o "./archive" "URL"` |
| 使用指定设置文件 | `uv run zhihu fetch -s settings.toml "URL"` |

开关可以组合使用，例如 `uv run zhihu fetch --html --comments "URL"`。开启评论后，每个内容默认保存最多 10 条一级评论，每条再保存最多 10 条回复，可在[配置](#settings)中调整。

用 `uv run zhihu --help` 查看入口命令，用 `uv run zhihu fetch --help` 查看全部抓取参数。`init`、`login` 和 `check` 也各自支持 `--help`。

<a name="login"></a>

## 登录与 Cookie

遇到知乎要求登录的内容，可先生成配置，再让工具打开浏览器。

```bash
uv run zhihu init
uv run zhihu login -s settings.toml
```

在打开的浏览器中完成登录。程序最多等待 180 秒，验证登录状态后才保存 Cookie，默认存到 `.local/cookies.json`。取消、超时或保存失败时会保留原文件。按命令提示修改 `settings.toml` 中已有的 `[network]` 分区，填入命令显示的文件路径。使用默认位置时可填下面这一行。

```toml
cookie_file = ".local/cookies.json"
```

```bash
uv run zhihu check -s settings.toml
uv run zhihu fetch -s settings.toml "https://zhuanlan.zhihu.com/p/357892158"
```

已有启用本机远程调试（CDP）的 Chrome 时，可运行 `uv run zhihu login --cdp http://127.0.0.1:9222` 读取该浏览器的知乎 Cookie。

也可以导入 JSON 文件，支持知乎 Cookie 键值对象及[示例中的列表格式](../cookies.example.json)。列表条目必须标明 `zhihu.com` 或其子域。要单独检查某个文件，可用 `uv run zhihu check --cookie-file "./.local/cookies.json"`。

Cookie 文件以明文保存登录凭证，请放在本地私有位置。`.local/` 已由仓库的 Git 规则忽略，`settings.toml` 里只填文件路径。报告问题时请删去凭证和其他隐私信息。

<a name="settings"></a>

## 配置文件

`uv run zhihu init` 生成含默认值的 `settings.toml`，已有文件会保留。每次使用配置都要显式传入 `-s settings.toml`，相对路径以运行命令时所在的目录为基准。

| 分区 | 可设置的内容 |
| --- | --- |
| `[archive]` | 输出目录 `output_dir`，格式 `markdown`、`html`、`pdf`，评论 `comments`、`comment_roots`、`comment_replies`，以及媒体下载 `media_download` |
| `[network]` | Cookie 文件 `cookie_file`、代理 `proxy`、超时 `timeout`、重试次数 `retries`、分页大小 `page_size`、请求间隔 `request_interval` 和随机等待 `request_jitter` |
| `[browser]` | 浏览器策略 `fallback`、是否隐藏窗口 `headless`、本机调试地址 `cdp_url` |

命令行开关可覆盖本次设置。`--no-html`、`--no-pdf`、`--no-comments` 和 `--no-media` 分别关闭对应选项。`--browser auto`（默认）先用 HTTP/API，必要时尝试浏览器，`never` 仅使用 HTTP/API，`always` 直接从浏览器获取目标页面的数据。问题和专栏的后续分页仍可使用 API。

`--cdp` 或 `browser.cdp_url` 可连接启用了远程调试的本机浏览器，地址限于 `localhost`、`127.0.0.1` 或 `[::1]` 的 HTTP 或 WebSocket 端点。配置 `network.proxy` 会影响 HTTP 请求、媒体下载和工具启动的浏览器，已连接的浏览器沿用自己的代理。

<a name="outputs"></a>

## 输出文件和格式

默认输出到当前目录的 `知乎归档/`。每个目标都有自己的目录，其中包含主文档和成功下载的 `media/` 文件。完整问题把回答合并到同一份文档。专栏生成索引，并把文章放在 `内容/` 中。移动归档时请带上整个目录，以保留相对链接。

- **Markdown** 保留正文结构和原始 TeX。
- **媒体** 关闭下载或可选媒体无法下载时，文档保留来源链接。独立视频主文件下载失败时会报错。
- **离线 HTML** 可直接在浏览器打开，使用本地样式 `assets/`。成功转换的公式用浏览器原生 MathML 显示。
- **PDF** 由 Chrome 或 Chromium 渲染本地内容，视频保留来源链接。专栏索引和各篇文章各有一份 PDF。仅需 PDF 时，在 `[archive]` 中设置 `markdown = false`、`html = false`、`pdf = true`。至少需要开启一种输出格式。

<a name="resume"></a>

## 中断与续抓

问题和专栏会逐项保存。终端会显示进度文件路径，常规归档通常为 `归档进度.md`。中断后可重跑原命令，工具从头读取列表、复用已有目录和有效媒体。成功后才发布新的完整专栏索引或合并后的问题文档。

如果已知问题回答列表的 **API 分页 offset**，可从该位置续抓。下面的 `9980` 是示例分页位置，实际值以接口分页位置为准。终端已保存条数可能受去重影响。

```bash
uv run zhihu fetch "https://www.zhihu.com/question/1976120753834443272" -s settings.toml --offset 9980 --no-html --no-pdf
```

- 使用原来的归档目录。此前指定过 `-o` 时请再次传入同一个目录。此前使用内置默认值时可去掉 `-s settings.toml`。
- 正数 `--offset` 仅支持问题链接和 Markdown，需保留 `archive.markdown = true`。
- 工具按 ID 跳过已保存的回答片段，把新片段写入 `回答片段/`，索引通常为 `续抓进度.md`。已有完整文档会保留。
- 抓到最后一页时，本轮片段续抓结束。需要重新生成完整问题文档时，去掉 `--offset` 再运行。

同一目标的媒体中途断开时，重跑可在服务端提供可靠验证信息的情况下续传 `.part` 文件。

<a name="troubleshooting"></a>

## 排查问题

| 现象 | 怎么处理 |
| --- | --- |
| 登录失效或内容要求登录 | 用 `uv run zhihu check -s settings.toml` 检查会话，再用 `uv run zhihu login -s settings.toml` 刷新。抓取时传入同一个设置文件。 |
| 浏览器找不到或 PDF 导出失败 | 确认 Chrome 可启动，或按[安装](#install)一节安装 Playwright 的 Chromium。 |
| Windows 输出路径太长 | 用 `-o` 选择较短的绝对路径，例如 `-o "C:/archive"`，也可修改 `archive.output_dir`。如需续抓旧归档，先把整份归档移到新位置。 |
| 遇到 HTTP 429 或要求等待 | 等待一段时间后再试。每次 HTTP 请求和每个媒体下载的累计重试等待分别最多 60 秒。批量归档可增加 `network.request_interval` 来放慢请求。 |
| 问题或专栏在中途停止 | 查看终端的 `中断原因` 和进度文件。报告时可附上命令、版本、系统和脱敏后的错误输出。 |

还有问题可到 [GitHub Issues](https://github.com/yuchenzhu-research/zhihu-scraper/issues) 查看或反馈。
