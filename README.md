# 🕷️ Zhihu-Scraper

<div align="center">

[![Python Version](https://img.shields.io/pypi/pyversions/zhihu-scraper?logo=python&style=flat-square)](https://pypi.org/project/zhihu-scraper/)
[![Playwright](https://img.shields.io/badge/Playwright-1.49-blue?style=flat-square&logo=playwright)](https://playwright.dev/)
[![License](https://img.shields.io/pypi/l/zhihu-scraper?color=green&style=flat-square)](https://github.com/yuchenzhu-research/zhihu-scraper/blob/main/LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/yuchenzhu-research/zhihu-scraper?style=flat-square)](https://github.com/yuchenzhu-research/zhihu-scraper/stargazers)

**高质量知乎内容离线备份工具 | 高保真 Markdown 转换 | LaTeX 公式完美渲染**

</div>

---

## 📖 介绍

**Zhihu-Scraper** 是一款专为知识深度爱好者打造的内容归档工具。它不仅仅是一个爬虫，更是一个**高保真排版还原引擎**。

基于 Playwright 自动化驱动，它能将知乎专栏、回答完美转换为本地 Markdown，尤其解决了数学公式渲染、图片排版、视频卡片噪音等历史难题。

### ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🎓 **LaTeX 公式** | 工业级公式还原，支持 `*{N}{X}` 复杂矩阵 |
| 🖼️ **图片本地化** | 自动下载高清原图，断网也能阅读 |
| 🧹 **智能去噪** | 自动剔除广告、视频、点赞提醒 |
| 🤖 **双重界面** | 交互式 CLI + 命令行 (Typer) |
| 🛡️ **反爬对抗** | Stealth JS + 人类行为模拟 |

---

## 🚀 快速上手

### 1. 安装

```bash
# 克隆代码
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或: .\venv\Scripts\activate  # Windows

# 安装依赖 (CLI 模式)
pip install -e ".[cli]"

# 安装 Playwright 浏览器
playwright install chromium
```

### 2. 配置 Cookie (推荐)

在 `cookies.json` 中填入你的知乎 Cookie：

```json
[
  {"name": "z_c0", "value": "你的z_c0值"},
  {"name": "d_c0", "value": "你的d_c0值"}
]
```

> **获取方法**：登录知乎后，按 F12 打开开发者工具 → Network → 刷新页面 → 点击任意请求 → 复制 Cookie 头部

### 3. 运行

#### 方式 A: 交互式界面
```bash
python main.py
```

#### 方式 B: 命令行模式 (推荐)
```bash
# 抓取单个问题 (前 10 个回答)
zhihu fetch "https://www.zhihu.com/question/123456" -n 10

# 批量抓取
zhihu batch ./urls.txt -c 4 -o ./data

# 查看配置
zhihu config --show

# 环境检查
zhihu check
```

---

## 📖 使用指南

### CLI 命令

| 命令 | 说明 |
|------|------|
| `zhihu fetch <url>` | 抓取单个链接 |
| `zhihu batch <file>` | 批量抓取 |
| `zhihu config` | 配置管理 |
| `zhihu check` | 环境检查 |

### 抓取选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `-n, --limit` | 限制回答数量 | 全部 |
| `-o, --output` | 输出目录 | ./data |
| `-c, --concurrency` | 图片并发数 | 4 |
| `-i, --no-images` | 不下载图片 | False |
| `-b, --headless` | 无头模式运行 | True |

### 配置说明

所有配置均在 `config.yaml` 中管理：

```yaml
# 人类行为模拟 (防反爬)
humanize:
  min_delay: 1.0      # 最小请求间隔 (秒)
  max_delay: 3.0      # 最大请求间隔 (秒)

# 浏览器设置
browser:
  headless: true      # 无头模式
  timeout: 30000      # 超时 (ms)

# 图片下载
images:
  concurrency: 4      # 并发数
  timeout: 30.0       # 超时 (秒)
```

---

## 📂 项目结构

```
.
├── main.py              # 🚀 启动入口 (交互式 CLI)
├── cli/
│   ├── __init__.py
│   └── app.py           # ✨ Typer CLI 命令行
├── core/
│   ├── __init__.py
│   ├── scraper.py       # 爬虫引擎 + 反爬对抗
│   ├── converter.py     # HTML → Markdown
│   ├── config.py        # 配置 + 日志
│   └── errors.py        # 异常体系
├── static/
│   ├── stealth.min.js   # 反检测脚本
│   └── z_core.js        # 知乎签名算法
├── config.yaml          # ⚙️ 配置文件
├── pyproject.toml       # 📦 依赖管理
├── cookies.json         # 🔑 用户凭证
└── data/                # 📂 输出目录
    └── [日期] 问题标题/
        ├── index.md     # Markdown 文件
        └── images/      # 本地图片
```

---

## 🛠️ 技术栈

<div align="center">

| 层级 | 技术 |
|------|------|
| **浏览器** | Playwright |
| **HTTP** | httpx (异步) |
| **HTML 解析** | BeautifulSoup4 |
| **格式转换** | markdownify |
| **CLI** | Rich + Typer |
| **日志** | structlog |
| **配置** | PyYAML |

</div>

---

## ⚠️ 免责声明

> **使用本项目即代表您已阅读并同意以下条款：**

1. 本项目仅用于计算机技术研究，严禁用于商业非法盈利行为
2. 使用者应自行遵守目标网站的 `robots.txt` 和用户协议
3. 开发者不对因不当使用产生的后果承担责任
4. 请尊重原创，仅用于个人学习收藏

---

## 📈 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=yuchenzhu-research/zhihu-scraper&type=Date)](https://star-history.com/#yuchenzhu-research/zhihu-scraper&Date)

---

<div align="center">

如果这个工具对你有帮助，请给个 ⭐ **Star** 吧！

</div>