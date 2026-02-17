# 🕷️ Zhihu-Scraper

<div align="left">

**高保真知乎内容离线备份工具** · **LaTeX 公式完美渲染** · **Markdown 导出**

---

### 📦 安装

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
python -m venv venv && source venv/bin/activate
pip install -e ".[cli]"
playwright install chromium
```

---

### ⚡ 快速开始

```bash
# 抓取问题 (前 10 个回答)
zhihu fetch "https://www.zhihu.com/question/123456" -n 10

# 批量抓取
zhihu batch ./urls.txt -c 4 -o ./data

# 查看配置
zhihu config --show
```

---

### ✨ 核心特性

| | |
|:--|:--|
| 🎓 | **LaTeX 公式** - 支持 `*{N}{X}` 复杂矩阵 |
| 🖼️ | **图片本地化** - 自动下载高清原图 |
| 🧹 | **智能去噪** - 自动剔除广告和噪音 |
| 🤖 | **双重界面** - 交互式 CLI + 命令行 |
| 🛡️ | **反爬对抗** - Stealth JS + 随机延迟 |

---

### 📖 使用指南

**CLI 命令**

| 命令 | 说明 |
|:---|:---|
| `zhihu fetch <url>` | 抓取单个链接 |
| `zhihu batch <file>` | 批量抓取 |
| `zhihu config` | 配置管理 |
| `zhihu check` | 环境检查 |

**抓取选项**

| 选项 | 说明 | 默认 |
|:---|:---|:---|
| `-n, --limit` | 限制回答数量 | 全部 |
| `-o, --output` | 输出目录 | ./data |
| `-c, --concurrency` | 图片并发数 | 4 |
| `-i, --no-images` | 不下载图片 | False |
| `-b, --headless` | 无头模式 | True |

---

### ⚙️ 配置 (config.yaml)

```yaml
humanize:           # 防反爬
  min_delay: 1.0    # 最小请求间隔 (秒)
  max_delay: 3.0    # 最大请求间隔 (秒)

browser:           # 浏览器
  headless: true
  timeout: 30000

images:            # 图片下载
  concurrency: 4
  timeout: 30.0
```

---

### 📂 项目结构

```
.
├── main.py              # 交互式 CLI
├── cli/app.py           # Typer 命令行
├── core/
│   ├── scraper.py       # 爬虫引擎
│   ├── converter.py     # HTML → Markdown
│   ├── config.py        # 配置 + 日志
│   └── errors.py        # 异常体系
├── static/
│   ├── stealth.min.js
│   └── z_core.js
├── config.yaml
├── pyproject.toml
└── cookies.json
```

---

### 🛠️ 技术栈

```
Playwright    ·    httpx    ·    BeautifulSoup4
markdownify   ·    Rich     ·    Typer
structlog     ·    PyYAML
```

---

### ⚠️ 免责声明

1. 仅用于计算机技术研究，严禁商业盈利
2. 使用者应遵守目标网站协议
3. 开发者不对不当使用承担责任
4. 请尊重原创，仅个人学习收藏

---

<div align="center">

**如果对你有帮助，请 ⭐ Star 支持！**

</div>