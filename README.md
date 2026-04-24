<div align="center">

# Zhihu-Scraper
**知乎本地归档，从未如此优雅**

<p>
  <img src="https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg" alt="CI Badge" />
  <img src="https://img.shields.io/static/v1?label=python&message=3.14%2B&color=3776AB&style=flat-square&logo=python&logoColor=white" alt="Python Badge" />
  <img src="https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper?style=flat-square" alt="License Badge" />
</p>

<p>
  <strong>简体中文</strong> · <a href="README_EN.md">English</a>
</p>

</div>

Zhihu-Scraper 是一个**本地优先**的抓取归档工具。输入一条链接，即可自动提取正文与元数据、下载原图，并原生地转换为高清 Markdown 和 SQLite 索引库长期保存。

它是面向命令行工作流的最佳搭档，拒绝云端绑定，数据彻底归属自己。

> [!WARNING]  
> 本项目仅用于学习、研究、个人归档与技术交流。请遵守服务条款、爬虫约束和当地法律法规。

> [!NOTE]
> 当前项目收束在 `v3.0.1-final`。后续不再承诺持续适配知乎接口、页面结构或风控变化；已导出的 Markdown、图片和 SQLite 数据仍是主要长期价值。

<br>

## 🚀 一分钟入门

只需克隆仓库，运行自动化环境脚本，接着输入 `zhihu` 命令，这就是全部。

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper

# 自动创建 venv 并安装依赖
./install.sh
```

现在，试着抓取你的第一条回答：

```bash
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

或者打开沉浸式全屏工作台，享受交互式的归档乐趣：

```bash
zhihu
```

## ✨ 核心能力

- **单链归档**：支持回答、问题页（Top 抓取）、专栏、创作者主页等当前已验证路径。
- **本地至上**：直接写出 `Markdown`文件、离线图片目录 (Images) 与 `SQLite`元数据。
- **协议优先**：默认走 API / HTML 协议路径，专栏等复杂页面可尝试浏览器回退。
- **增量监控**：`monitor` 命令可基于本地状态文件检查收藏夹新增内容。
- **Textual TUI**：提供全屏工作台、任务队列、最近结果、失败重试和语言切换。

## 📚 详细文档与配置

想要了解如何注入 Cookie `z_c0`？如何编写复杂查询？了解每个 CLI 的进阶用法？

Zhihu-Scraper 包含非常详尽的文档结构：

- ⚙️ **[核心说明书 (MANUAL)](MANUAL.md)**：CLI 所有进阶参数、Cookie 路径配置、TUI 操作快捷键详解。
- 🛠 **[环境兼容性查询](docs/PLATFORM_SUPPORT.md)**：Windows / Linux 部署的专属指引。
- 🤖 **[Agent 执行边界](AGENTS.md)**：适合参与共建的代码助手与协作者阅读的架构守则。

<br>

<div align="center">
  <sub>Built with ❤️ by Yuchen Zhu Research.</sub>
</div>
