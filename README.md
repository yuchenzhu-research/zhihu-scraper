# 🕷️ Zhihu-Scraper

<div align="center">

[![Python Version](https://img.shields.io/pypi/pyversions/zhihu-scraper.svg?style=flat-square&logo=python)](https://pypi.org/project/zhihu-scraper/)
[![License](https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Stars](https://img.shields.io/github/stars/yuchenzhu-research/zhihu-scraper.svg?style=flat-square&logo=github)](https://github.com/yuchenzhu-research/zhihu-scraper/stargazers)
[![Issues](https://img.shields.io/github/issues/yuchenzhu-research/zhihu-scraper.svg?style=flat-square)](https://github.com/yuchenzhu-research/zhihu-scraper/issues)

**高保真知乎内容离线备份工具** · **LaTeX 公式完美渲染** · **Markdown 导出**

</div>

---

## 📦 安装

```bash
# 方式一：pip 安装（推荐）
pip install zhihu-scraper

# 方式二：源码安装
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
pip install -e ".[cli]"

# 安装浏览器
playwright install chromium
```

> **依赖说明**：需要 Python 3.10+，推荐使用 [uv](https://github.com/astral-sh/uv) 或 [conda](https://conda.io/) 管理环境。

---

## ⚡ 快速开始

```bash
# 交互式界面（推荐新手）
python main.py

# 命令行抓取单个链接
zhihu fetch "https://www.zhihu.com/question/123456" -n 10

# 批量抓取
zhihu batch ./urls.txt -c 4 -o ./data

# 查看配置
zhihu config --show
```

---

## ✨ 核心特性

| 特性 | 描述 |
|:---|:---|
| 🎓 **LaTeX 渲染** | 支持复杂矩阵公式，自动修复 KaTeX 兼容问题 |
| 🖼️ **图片本地化** | 自动下载高清原图，支持并发加速 |
| 🧹 **智能去噪** | 广告、弹窗自动过滤，保留纯净内容 |
| ⚡ **双重界面** | 交互式 TUI + Typer CLI，随心切换 |
| 🛡️ **反爬对抗** | Stealth JS + 随机延迟，模拟真人行为 |
| 📊 **并发控制** | 可控并发数，避免触发频率限制 |

---

## 📖 使用指南

### CLI 命令

| 命令 | 说明 |
|:---|:---|
| `zhihu fetch <url>` | 抓取单个链接 |
| `zhihu batch <file>` | 批量抓取 |
| `zhihu config` | 配置管理 |
| `zhihu check` | 环境检查 |

### 抓取选项

| 选项 | 说明 | 默认 |
|:---|:---|:---|
| `-n, --limit` | 限制回答数量 | 全部 |
| `-o, --output` | 输出目录 | ./data |
| `-c, --concurrency` | 图片并发数 | 4 |
| `-i, --no-images` | 不下载图片 | False |
| `-b, --headless` | 无头模式 | True |

---

## ⚙️ 配置

创建 `config.yaml` 自定义行为：

```yaml
zhihu:
  cookies: ./cookies.json  # 可选，登录后可抓取更多内容

crawler:
  humanize:
    enabled: true
    min_delay: 1.0   # 最小请求间隔 (秒)
    max_delay: 3.0   # 最大请求间隔 (秒)

  images:
    concurrency: 4
    timeout: 30.0

output:
  directory: data
  format: markdown
```

---

## 📂 项目结构

```
.
├── main.py              # 交互式 TUI 入口
├── cli/app.py           # Typer CLI 命令
├── core/
│   ├── scraper.py       # Playwright 爬虫引擎
│   ├── converter.py     # HTML → Markdown 转换器
│   ├── config.py        # 配置 + 日志 + Humanizer
│   └── errors.py        # 异常分类体系
├── static/
│   ├── stealth.min.js   # 浏览器指纹伪装
│   └── z_core.js        # 签名算法
├── config.yaml          # 项目配置
├── pyproject.toml       # 依赖管理
└── cookies.json         # 知乎登录凭证
```

---

## 🛠️ 技术栈

<div align="center">

**[Playwright](https://playwright.dev/)** · **[httpx](https://www.python-httpx.org/)** · **[Rich](https://github.com/Textualize/rich)**

**[Typer](https://typer.tiangolo.com/)** · **[markdownify](https://github.com/matthewwithanm/python-markdownify)** · **[structlog](https://www.structlog.org/)**

</div>

---

## ⚠️ 免责声明

1. 本项目仅供学术研究和学习交流使用
2. 使用者应遵守知乎相关服务协议
3. 请勿用于任何商业用途
4. 因使用本项目产生的法律纠纷，由使用者自行承担

---

<div align="center">

**如果对你有帮助，请 ⭐ Star 支持！**

[![Stargazers over time](https://stars.medv.io/yuchenzhu-research/zhihu-scraper.svg)](https://stars.medv.io/yuchenzhu-research/zhihu-scraper)

</div>