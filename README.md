# 🔥 Zhihu-Scraper | 知乎内容增强型备份工具 �

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python3.9+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Data-Local%20Backup-success.svg" alt="Data">
</p>

## 📖 项目简介

**Zhihu-Scraper** 是一个专注于**个人内容归档**与**知识备份**的开源工具。它基于 **Playwright** 驱动，通过自动化浏览器环境，高效、稳定地将知乎优质内容（专栏文章、回答）转换为**本地可读的 Markdown 文件**。

不同于传统爬虫，本项目采用全模拟用户浏览方案，旨在为用户提供一种可靠的**离线阅读**与**数据备份**解决方案。🚀

---

## ✨ 核心特性

#### 🛡️ 稳定自动化内核
- ✅ **智能浏览器环境**：基于 Playwright 自动化技术，通过模拟真实用户交互（滚动、点击）获取渲染数据。
- ✅ **持久化会话**：支持复用浏览器上下文 (Context)，减少重复登录验证，提升采集稳定性。
- ✅ **自适应请求签名**：内置标准算法适配逻辑，自动生成请求所需的校验参数，确保数据接口调用顺畅。

#### 📄 高保真格式还原
- ✅ **Markdown 转换**：精准解析 HTML 结构，完美还原标题、加粗、引用、代码块等排版细节。
- ✅ **LaTeX 公式支持**：自动识别数学公式并转换为标准 LaTeX 语法 (`$E=mc^2$`)，便于在 Obsidian/Typora 中渲染。
- ✅ **资源本地化**：自动下载文章中的图片与头图，替换为相对路径引用，**实现真正的离线阅读**。

#### ⚡️ 便捷批量处理
- ✅ **智能内容提取**：支持粘贴混合文本（如聊天记录），自动识别并提取其中的知乎链接。
- ✅ **批量任务队列**：支持预设 URL 列表，一键批量备份多篇文章。

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

### 方式一：交互式模式
直接运行主程序，粘贴你想要备份的知乎链接（支持混合文本）：
```bash
python3 main.py
```
*提示：看到 `🔗 请粘贴知乎链接:` 时，直接粘贴即可，回车开始执行。*

### 方式二：批量模式
打开 `main.py`，修改顶部的 `BATCH_URLS` 列表。

---

## 4. 代理配置 (自动检测)

无需手动修改代码！程序启动时会自动检测 macOS 的系统代理设置（支持 Shadowrocket / ClashX 等）。

- **自动模式**：如果有代理（如 `127.0.0.1:1082`），程序会自动使用。
- **直连模式**：如果未检测到代理，则自动直连。
- **手动覆盖**：如果需要强制指定，可以在 `scraper.py` 中修改 `PROXY_SERVER`。

```python
# scraper.py 默认逻辑
PROXY_SERVER = get_auto_proxy()
```
```python
BATCH_URLS = [
    "https://zhuanlan.zhihu.com/p/475751340",
    "https://www.zhihu.com/question/277497549/answer/394815744",
]
```
保存后运行 `python3 main.py`，程序将自动处理列表中的所有内容。

---

## 📂 输出结构

所有备份数据将保存在 `data/` 目录下：
```text
data/
├── [2026-02-11] 暑期科研如何发CVPR - 高继扬/
│   ├── index.md      # 转换后的 Markdown 正文
│   └── images/       # 本地化图片资源
└── [2022-03-16] CS PhD申请总结 - Ava/
    ├── index.md
    └── images/
```

---

## ⚠️ 免责声明 (Disclaimer)

> [!IMPORTANT]
> **使用本项目即代表您已阅读并同意以下条款。**

1. **项目性质**：本项目仅供**计算机技术研究**（如浏览器自动化测试、数据解析算法）与**个人学习交流**使用。
2. **使用限制**：
   - 严禁将本项目用于任何**商业盈利**、**大规模数据采集**或**破坏平台正常运营**的行为。
   - 用户应自行确保其使用行为符合所在国家/地区的法律法规以及目标平台的用户协议。
3. **责任承担**：
   - 因用户不当使用本项目而导致的任何法律后果（包括但不限于账号异常、IP 限制、法律诉讼等），均由使用者自行承担，开发者不负任何责任。
4. **知识产权**：
   - 本项目部分算法逻辑源于开源社区的技术研究成果，仅作为学习案例展示。如有侵权，请联系删除。

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=yuchenzhu-research/zhihu-scraper&type=Date)](https://star-history.com/#yuchenzhu-research/zhihu-scraper&Date)

---

<p align="center">
  如果不小心帮到了你，请给个 ⭐ <b>Star</b> 支持一下！
</p>