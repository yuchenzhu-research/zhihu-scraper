<div align="center">

# 🕷️ Zhihu Scraper (v3.0)

**高保真知乎内容离线备份工具 · 纯后端原生 API 握手 · SQLite 实体库架构**

[![Python Version](https://img.shields.io/pypi/pyversions/zhihu-scraper.svg?style=for-the-badge&logo=python)](https://pypi.org/project/zhihu-scraper/)
[![License](https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Stars](https://img.shields.io/github/stars/yuchenzhu-research/zhihu-scraper.svg?style=for-the-badge&logo=github)](https://github.com/yuchenzhu-research/zhihu-scraper/stargazers)
[![Issues](https://img.shields.io/github/issues/yuchenzhu-research/zhihu-scraper.svg?style=for-the-badge)](https://github.com/yuchenzhu-research/zhihu-scraper/issues)

**[极速抓取]** · **[防封号 Cookie 池]** · **[Markdown 与数据库双引擎存储]**

</div>

---

## ⚡ 核心演进 (v3.0 Architecture)

在全新的 v3.0 架构中，项目彻底抛弃了以往沉重低效的无头浏览器页面解析思路（除非遇到终极 WAF 才会作为降级使用），**重构为直接与知乎后台 JSON API 交互的纯粹网络协议引擎。**

| 核心组件引擎 | 技术解析与功能特性 |
| :--- | :--- |
| 🚀 **原生 API 提速引擎** | 依赖 `curl_cffi` 完美模拟 Chrome 底层 TLS/HTTP2 网络握手指纹，无视绝大数网关拦截。同时本地内置 `z_core.js` V8 逆向签名验证，实现 **毫秒级、0渲染开销** 的数据捕获。 |
| 💿 **SQLite 主动存储池** | 获取到的每一个问题/专栏/回答，提取出核心字段，使用 UPSERT（冲突平滑更新）持久化写入 `data/zhihu.db` 构建真正的**本地化智能知识库**。 |
| 🔄 **自动化增量监听 (Monitor)** | 全新指令 `zhihu monitor`！利用状态指针 (Last ID) 实现对上万条知乎“收藏夹”记录的**无缝增量扫描**，只抓取昨晚刚加入的数据。极其适合挂载 Cron 定时任务！ |
| 🛡️ **专栏墙降级与 Cookie 池** | 内置智能重试机制：当面对防抓取极严谨的**知乎专栏**时，自动无感拉起 Playwright 并注入动态 **Cookie 轮换池**中的备用小号，突破终极 `zse_ck` 防线！ |
| 🎓 **排版引擎增强** | 完善并清洗图片防盗链链接，在最终导出的纯净 `Markdown` 内完美离线转换复杂的 LaTeX ($...$) 矩阵公式与重点加粗内容。 |

---

## 📦 极简安装部署

本项目深度依赖诸如 `PyExecJS` 与 `curl_cffi` 等底层 C 库。要求 **Python 3.10+**。

### 标准安装
```bash
# 1. 直接通过官方 pip 源安装推荐包 (自动挂载命令行)
pip install zhihu-scraper

# 2. 如果你需要开启智能专栏降级防护墙，需要额外补充浏览器引擎：
playwright install chromium
```

### 开发者源码安装
```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
pip install -e ".[cli]"
playwright install chromium
```

---

## 🕹️ 五大核心控制台指令 (CLI Features)

v3.0 版本搭载了一整套完备的 CLI 矩阵体系（同时兼容纯炫酷终端 UI 和 Shell 管道组合），输入 `zhihu` 或 `zhihu --help` 皆可快速调用。

### 1. 交互式仪表盘终端 (✨强烈推荐)
这是传统脚本到赛博纪元的飞跃！启动炫酷且全图形引导的 **Americana Fusion UI 终端引擎**：
```bash
zhihu interactive

# => 回车进入终端，用上下左右按键和空格直接图形化选定你想执行的任务(Fetch/批量/检索等)。
```

### 2. 精准定点抓取 (Fetch)
不管它是知乎的一个极其刁钻的独立回答，还是一个总和问题，还是超长专栏，一行拿走：
```bash
zhihu fetch "https://www.zhihu.com/question/12345/answer/98765"

# 参数可选:
# -i, --no-images : 光速只下载文本，忽略大图图片并发
```

### 3. 多线程文件队列抓取 (Batch)
如果你的 `urls.txt` 里面塞了 500 条各种杂乱的知乎链接：
```bash
# -c 代表启动多少条底层高并发信道
zhihu batch ./urls.txt -c 8
```

### 4. 收藏夹状态指针监控同步 (Monitor)
专为常年维护某个几十万条目私人知乎大收藏夹的用户开发。每次运行它都会从你收藏夹第 1 页开始爬，一旦遇到你在本地已经存进 SQLite 过的数据，立马**自动中断程序退出**（防止无脑重复刷封号）！抓取效率极高。
```bash
# 输入公开收藏夹的纯数字 ID 即可
zhihu monitor 78170682
```

### 5. 本地 SQLite 知识库疾速闪查 (Query)
数据存下来如果不利用就等于死了。现在你可以一秒跨越全量抓取离线库匹配关键字！
```bash
# 根据标题、内容或作者，一键列出表格，支持管道再分发
zhihu query "人工智能的底层逻辑"
```

---

## 🛠️ 高级反制：配置与身份凭证池

如果你需要爬取的私域内容要求极高的等级，你也可以在工程根目录填装弹药。

### `cookies.json` 与 `cookie_pool/` 轮询矩阵 (重磅防封)
1. 默认身份：将你主号抓包拦截到的基础 Cookie（JSON数组格式）全量覆盖至工具目录下的 `cookies.json`。
2. **集群防封**：在同级目录下新建文件夹 `cookie_pool/`。把你所有小号的 `any_name.json` 扔进去！在遇到高危 WAF 时（比如触发了 HTTP 403 惩罚），底层的 `CookieManager` 将自动替你踢掉被封的号，立刻换一个未冷却的小号接着跑！

### `config.yaml` 核心节律指引
默认情况无需修改。它能定义最低重试间隔与并发宽容度。
```yaml
zhihu:
  cookies: ./cookies.json

crawler:
  humanize: # 拟人化时间轴补偿
    enabled: true
    min_delay: 1.0   
    max_delay: 3.5   

output:
  directory: data
  format: markdown
```

---

## 🧱 技术栈基石与架构 (Tech Stack)

<div align="center">

**[curl_cffi](https://github.com/lexiforest/curl_cffi)** (TLS 伪装) · **[Playwright](https://playwright.dev/)** (防线重构) · **[SQLite](https://sqlite.org/)** (数据全系固化)

**[Typer](https://typer.tiangolo.com/)** (CLI 驱动) · **[Rich](https://github.com/Textualize/rich)** (赛博 TUI 组件) · **[PyExecJS](https://pypi.org/project/PyExecJS/)** (本地 V8 动态执行环境)

</div>

### 目录分层逻辑 (Design Pattern)
- `cli/`：视图解析逻辑（Typer 路由映射及炫酷的 Interactive Shell 展示墙）。
- `core/`：核心商业领域模型。绝不涉及显示渲染，专心搞 WAF 欺骗网络通道 (`api_client`)，多账号池分配 (`cookie_manager`) 和 SQL 全增量存取 (`db.py`)。
- `static/`：最宝贵的资产库：`z_core.js` 原版底层验证破解，由我们全系接管。

---

## ⚠️ 免责声明 (Disclaimer)

1. 本项目仅供学术研究和学习交流使用，旨在探讨大规模非结构化文档的数据保存技术。
2. 代码内含有对特定平台底层 HTTP 认证指纹特征的解析，严禁用此工具从事任何黑产打压、DDOS 恶意爬取及商业化倒卖活动。
3. 任何由使用者擅自配置高并发参数导致被知乎封锁账户，产生的连带责任由部署者自行全权承担。使用者应遵守对应平台的法律法规与相关的 Robot 协议。