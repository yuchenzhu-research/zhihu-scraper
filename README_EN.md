<div align="center">

# Zhihu-Scraper
**Local-first Zhihu Archiving, More Elegant Than Ever**

<p>
  <img src="https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg" alt="CI Badge" />
  <img src="https://img.shields.io/static/v1?label=python&message=3.14%2B&color=3776AB&style=flat-square&logo=python&logoColor=white" alt="Python Badge" />
  <img src="https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper?style=flat-square" alt="License Badge" />
</p>

<p>
  <a href="README.md">简体中文</a> · <strong>English</strong>
</p>

</div>

Zhihu-Scraper is a **local-first** crawling and archiving tool. Paste a link, and it automatically extracts the main content, metadata, downloads images, and natively converts everything into high-quality Markdown and an SQLite index database for long-term storage.

It's the ultimate companion for command-line workflows—reject cloud lock-ins and keep complete ownership of your data locally.

> [!WARNING]  
> This project is strictly for learning, research, and personal archiving. Please comply with Terms of Service, crawler guidelines, and local laws.

> [!NOTE]
> This project is now closed at `v3.0.1-final`. Future compatibility with Zhihu API, page structure, or anti-bot changes is not guaranteed; exported Markdown, images, and SQLite data are the long-term deliverables.

<br>

## 🚀 Quick Start

Just clone the repository, run the automatic environment script, and type `zhihu`. That’s it.

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper

# Creates venv and installs dependencies automatically
./install.sh
```

Now, try archiving your first answer:

```bash
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

Or open the immersive full-screen workbench and enjoy an interactive archiving experience:

```bash
zhihu
```

## ✨ Core Features

- **Local Archiving Paths**: Supports individual answers, question pages (Top-N extraction), column articles, and creator profiles on the currently validated paths.
- **Local Supremacy**: Outputs directly to `Markdown` files, offline image directories (Images), and `SQLite` metadata.
- **Protocol First**: Uses protocol-first API / HTML paths, with browser fallback available for complex column pages.
- **Incremental Monitoring**: The `monitor` command can check collection updates with local state.
- **Textual TUI**: A full-screen workbench for queues, recent results, retry flow, and language switching.

## 📚 Documentation & Configuration

Want to know how to inject your `z_c0` Cookie? Write complex queries? Understand advanced CLI usage?

We provide comprehensive documentations:

- ⚙️ **[Core Manual (MANUAL)](MANUAL.md)**: Details on all CLI advanced parameters, Cookie path configs, and TUI shortcuts.
- 🛠 **[Platform Compatibility](docs/PLATFORM_SUPPORT.md)**: Specific deployment guidelines for Windows and Linux.
- 🤖 **[Agent Boundaries](AGENTS.md)**: Architectural ground rules designed for AI coding assistants and code contributors.

<br>

<div align="center">
  <sub>Built with ❤️ by Yuchen Zhu Research.</sub>
</div>
