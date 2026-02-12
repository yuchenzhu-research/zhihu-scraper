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

### 1. 环境安装
```bash
# 克隆代码
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper

# 安装依赖 (推荐使用 venv)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置权限 (推荐)
虽然本工具支持游客模式，但建议配置 Cookie 以解锁完整功能（如抓取更多回答、查看完整内容）。

1. 在项目根目录创建 `cookies.json`。
2. 填入你的知乎 Cookie（至少包含 `z_c0`）：
   ```json
   [
     {
       "name": "z_c0",
       "value": "你的Cookie值(2.0|...)",
       "domain": ".zhihu.com",
       "path": "/"
     }
   ]
   ```
> **提示**: 你可以使用 EditThisCookie 插件导出，或者按 F12 在网络请求头中找到 `cookie` 字段。

### 3. 运行爬虫
```bash
python3 main.py
```
粘贴知乎链接（问题/回答/文章）后，程序会自动识别模式。

#### 🕹️ 模式说明

| 模式 | 触发条件 | 说明 |
| :--- | :--- | :--- |
| **游客模式** | 无 `cookies.json` | 仅抓取前 **3** 个回答 (知乎限制) |
| **登录模式** | 有有效 Cookie | 解锁全部功能，支持以下两种抓取方式 |

**登录模式下的两种玩法：**

1. **按数量抓取 (Count Mode)**
   - 输入 `1`，设定要抓取的回答数量 (img. `20`)。
   - 程序将从顶部开始，抓取指定数量的回答。

2. **按范围抓取 (Range Mode)**
   - 输入 `2`，设定 **起始锚点** 和 **结束锚点**。
   - 支持 **答主名字** (如 `FishDreamer`) 或 **回答链接**。
   - **效果**: 自动抓取两个锚点之间（闭区间）的所有回答。
   - *适合存档特定时间段或特定话题下的高质量讨论。*

### 4. 常见问题 (Troubleshooting)

**问题**: 抓取只有前 5 个回答，后面加载不出？
**解决**: 本工具内置了自动修复机制：
1. **自动点击 "显示全部"**: 程序会尝试点击页面上的折叠按钮。
2. **自动切换排序**: 如果仍然卡顿，程序会自动尝试切换到 **"按时间排序"**。
   - 此时请耐心等待 10-20 秒，通常能成功加载更多内容。

---

## 📂 项目结构 (Project Structure)

本项目采用模块化设计，清晰分离了核心逻辑、静态资源和输出数据。

```text
.
├── main.py              # 🚀 启动入口 (Entry Point)
├── core/                # 🧠 核心逻辑包
│   ├── scraper.py       # 爬虫大脑：负责页面抓取、滚动加载、反爬对抗
│   └── converter.py     # 格式转换：负责 HTML -> Markdown、LaTeX 公式修复
├── static/              # 🧶 静态资源
│   ├── stealth.min.js   # 使得 puppeteer 对抗反爬的 JS 库
│   └── z_core.js        # 知乎 x-zse-96 签名算法环境
├── cookies.json         # 🍪 用户凭证 (需手动创建)
└── data/                # 💾 输出目录 (Output)
    └── [日期] 问题标题/
        ├── index.md     # 转换后的 Markdown 内容 (Obsidian/Logseq 友好)
        └── images/      # 本地化存储的图片资源
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