# 🚀 Zhihu-Scraper | 知乎万能离线备份工具

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python3.9+-yellow.svg" alt="Python">
  <img src="https://img.shields.io/badge/LaTeX-Perfect%20Render-blueviolet.svg" alt="LaTeX">
  <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

> **"让知乎的优质知识不再随风飘逝，而是静静躺在你的本地硬盘里。"**

**Zhihu-Scraper** 是一款专为知识深度爱好者打造的内容归档工具。它不仅仅是一个爬虫，更是一个**高保真排版还原引擎**。基于 Playwright 自动化驱动，它能将知乎专栏、回答完美转换为本地 Markdown，尤其解决了数学公式渲染、图片排版、视频卡片噪音等历史难题。

---

## 🔥 为什么选择这个项目？

### 1. 🎓 工业级 LaTeX 公式还原 (The Killer Feature)
- **零误差转换**：不仅支持标准 LaTeX 识别，还通过底层重构解决了 GitHub/KaTeX 不支持的 `*{N}{X}` 复杂矩阵定义，实测在 Obsidian、Typora、GitHub 中完美渲染。
- **占位符保护**：内置公式保护策略，确保在转换为 Markdown 过程中特殊字符不被转义。

### 2. 🖼️ 图片与资源彻底本地化
- **离线阅读**：自动抓取文章内所有图片及头图，自动下载并重写路径。断网环境下，你的知识库依然图文并茂。
- **高清原图**：优先采集 `data-actualsrc` 高清源，告别模糊缩略图。

### 3. 🧹 暴力去噪，极简排版
- **智能脱水**：自动剔除知乎烦人的广告卡片、视频占位符、点赞提醒、“查看更多”按钮，还你一个纯净的沉浸式阅读空间。

### 4. 🧠 极客友好，开箱即用
- **智能链接提取**：允许你粘贴一段杂乱的聊天记录或网页文本，程序会自动从中精准“钓出”所有合法的知乎链接并开启批量下载任务。
- **自动代理感应**：无需手动配置！自动侦测 macOS 系统代理（Shadowrocket/ClashX），支持直接访问（如果不需要代理）。

---

## 🛠️ 快速上手

### 环境安装
```bash
# 1. 克隆代码
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper

# 2. 安装依赖 (推荐 venv)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 运行
```bash
python3 main.py
```
> **用法提示**：你可以直接把知乎链接粘贴进去，也可以批量修改 `main.py` 中的 `BATCH_URLS` 列表。

---

## 📂 备份目录演示

下载后的文件结构极其规整，非常适合接入 **Obsidian** 或 **Logseq**：

```bash
data/
└── [2024-12-11] 概率论公式定理大全 - 超唐体/
    ├── index.md        # 转换后的高保真 Markdown
    └── images/         # 自动归档的图片资源
```

---

## ⚖️ 免责声明 (Disclaimer)

> [!CAUTION]
> **使用本项目即代表您已阅读并同意以下条款：**

1. **学术研究限制**：本项目代码仅用于计算机技术研究（如自动化测试、算法解密、离线化存储）与学习交流，严禁将本项目直接或间接用于任何商业非法盈利行为。
2. **遵守 Robots 协议**：使用者在运行本项目前，应自行熟悉并遵守相关网站的 `robots.txt` 规则及相关用户协议。
3. **法律责任自负**：本项目不含任何绕过付款限制的功能。开发者不对用户因不当使用代码（如高频采集导致账号封禁、IP 受限或法律诉讼等）而产生的后果承担任何责任。
4. **尊重原创**：请在备份时尊重原作者的知识产权，内容请仅供个人收藏。

---

## 🌟 Star Trend

[![Star History Chart](https://api.star-history.com/svg?repos=yuchenzhu-research/zhihu-scraper&type=Date)](https://star-history.com/#yuchenzhu-research/zhihu-scraper&Date)

---

<p align="center">
  如果这个工具帮你保存了一篇好文章，请给个 ⭐ <b>Star</b> 吧！
</p>