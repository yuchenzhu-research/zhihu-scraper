# 🔥 Zhihu-Offline-Tool | 知乎内容完美离线化工具 🕷️

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python3.9+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg" alt="Platform">
</p>

## 📖 项目简介

**Zhihu-Offline-Tool** 是一个功能强大的知乎内容抓取与离线化工具。它基于 **Playwright** 和 **Python** 开发，突破了知乎严格的反爬虫限制，能够将知乎专栏文章和问题回答完美转换为**带本地图片的 Markdown 文件**。

无论是为了构建个人知识库，还是为了备份珍贵的回答，本项目都能助你一臂之力。🚀

---

## ✨ 核心特性

#### 🛡️ 强力反爬技术
- ✅ **集成 Stealth.js**：自动隐藏 WebDriver 特征，模拟真实用户浏览行为。
- ✅ **持久化上下文**：复用浏览器 Cookie 和 LocalStorage，避免频繁登陆验证。
- ✅ **JS 逆向算法**：内置核心签名生成逻辑，合法计算 `x-zse-96`，畅通无阻。

#### 📄 完美排版转换
- ✅ **Markdown 还原**：精准保留标题、加粗、引用、代码块等格式。
- ✅ **LaTeX 公式支持**：自动将知乎的图片公式转换为标准 LaTeX 语法 (`$E=mc^2$`)。
- ✅ **图片本地化**：自动下载文章中的所有图片（含头图），并替换链接为本地相对路径，**断网也能看**！

#### ⚡️ 高效批量处理
- ✅ **混合输入支持**：直接粘贴一大段含有链接的文本（如聊天记录），自动提取所有知乎链接。
- ✅ **批量队列**：支持在代码中预设 URL 列表，一键挂机下载成百上千篇文章。

---

## 🛠️ 安装指南

### 1. 克隆项目
```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
```

### 2. 环境准备 (推荐使用虚拟环境)
```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

---

## 🚀 快速开始

### 方式一：交互式命令行
直接运行主程序，粘贴你想要下载的知乎链接（支持混合文本）：
```bash
python3 main.py
```
*提示：看到 `🔗 请粘贴知乎链接:` 时，直接粘贴即可，回车开始下载。*

### 方式二：批量下载
打开 `main.py`，修改顶部的 `BATCH_URLS` 列表：
```python
BATCH_URLS = [
    "https://zhuanlan.zhihu.com/p/475751340",
    "https://www.zhihu.com/question/277497549/answer/394815744",
]
```
保存后运行 `python3 main.py`，程序将自动遍历下载列表中的所有内容。

---

## 📂 输出结构

所有下载内容将整齐地保存在 `data/` 目录下：
```text
data/
├── [2026-02-11] 暑期科研如何发CVPR - 高继扬/
│   ├── index.md      # 转换后的 Markdown 正文
│   └── images/       # 文章内包含的所有图片
└── [2022-03-16] CS PhD申请总结 - Ava/
    ├── index.md
    └── images/
```

---

## ⚠️ 免责声明 (Disclaimer)

> [!IMPORTANT]
> **请务必仔细阅读以下条款，使用本项目即代表您已同意。**

1. **项目性质**：本项目仅供计算机技术研究与学习交流使用（如学习 Python 爬虫架构、JS 逆向分析、Playwright 自动化测试等），**严禁用于任何商业盈利目的**。
2. **合法合规**：
   - 请勿将本项目用于大规模自动化抓取、破坏知乎平台生态或侵犯他人权益的行为。
   - 因不当使用本项目而导致的任何法律后果（包括但不限于账号被封、IP 封禁、法律诉讼等），均由使用者自行承担，原作者不负任何责任。
3. **知识产权**：
   - 项目中引用的 `zhihu.js` 及部分反爬策略源于开源社区的逆向分析成果，仅作为学习案例展示。
   - 如知乎官方或相关权利人认为本项目侵犯了您的权益，请通过 Issue 联系，我将第一时间删除相关代码或下架本项目。

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=yuchenzhu-research/zhihu-scraper&type=Date)](https://star-history.com/#yuchenzhu-research/zhihu-scraper&Date)

---

<p align="center">
  如果不小心帮到了你，请给个 ⭐ <b>Star</b> 支持一下！
</p>