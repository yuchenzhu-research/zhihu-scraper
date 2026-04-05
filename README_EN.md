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

- **Link Universal**: Supports individual answers, question pages (auto Top-N extraction), column articles, and creator profiles.
- **Local Supremacy**: Outputs directly to `Markdown` files, offline image directories (Images), and `SQLite` metadata.
- **Anti-Detection**: Ultra-fast protocol-first extraction with a native headless browser fallback for complex pages.
- **Real-Time Monitoring**: Beyond one-time scrapes, it supports continuous incremental monitoring of your favorite collections via the `monitor` command.
- **Modern TUI**: Forget cluttered logs natively using the `Textual TUI` to manage task queues, review failures, and retry at the press of a button.

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
