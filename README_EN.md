# Zhihu-Scraper

**Save Zhihu content on your computer and read it offline.**

[![CI](https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB)](pyproject.toml)
[![MIT License](https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper)](LICENSE)

[简体中文](README.md) · [繁體中文](README_ZH_HANT.md) · **English**

Zhihu-Scraper is a local archiving tool for Zhihu. Give it a link to an article, answer, question, column, or standalone video. It saves **Markdown and local media** by default, with optional **offline HTML, PDF, and comments**.

[Quick start](#quick-start) · [Example output](#what-the-archive-looks-like) · [User manual](docs/MANUAL_EN.md)

## Quick start

Runs on Windows, macOS, and Linux. You need Git, Python 3.12 or later, and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
uv sync --locked
uv run playwright install chromium
uv run zhihu fetch "https://zhuanlan.zhihu.com/p/357892158"
```

Open the generated Markdown under `知乎归档/` in your current directory. A fresh Linux setup may also need browser system libraries. See [Installation and updates](docs/MANUAL_EN.md#install) for install scripts, pip, and browser setup.

## Supported Zhihu links

| Type | Example link | What gets saved |
| --- | --- | --- |
| Article | `zhuanlan.zhihu.com/p/<article ID>` | Body, author, media, and column information |
| Single answer | `zhihu.com/question/<question ID>/answer/<answer ID>` | The selected answer and its question information |
| Whole question | `zhihu.com/question/<question ID>` | The question and accessible answers, combined in one document after a complete run |
| Column | `zhihu.com/column/<column token>` | An index, accessible articles, and article navigation |
| Standalone video | `zhihu.com/zvideo/<video ID>` | The video file, title, and description when available |

Short answer links such as `zhihu.com/answer/<answer ID>` also work. Embedded Zhihu video cards are saved when the media is downloadable and kept as links otherwise. Author profiles, collections, search results, short posts, column collections, and paid Yanxuan content are currently outside the supported scope.

## What the archive looks like

The archive preserves the title, author, source link, images, tables, code blocks, and formulas alongside the text. A single article uses this layout by default. The `media/` folder is created when a download succeeds.

```text
知乎归档/
└── Article title/
    ├── Article title.md
    └── media/
        └── image file
```

With HTML enabled, open the archive in a browser to read it offline with its tables and formulas. This screenshot shows actual output generated from sample content.

![Offline HTML archive showing text, a formula, and a study schedule table](docs/images/offline-html-preview.png)

## Common tasks

| I want to… | See the manual |
| --- | --- |
| Export HTML or PDF, or save comments | [Choose output formats and comments](docs/MANUAL_EN.md#commands) |
| Archive content that requires sign-in | [Sign in and check your session](docs/MANUAL_EN.md#login) |
| Recover after an interruption or start at a known offset | [Check progress and resume](docs/MANUAL_EN.md#resume) |
| Change the output directory, proxy, or browser behavior | [Settings file](docs/MANUAL_EN.md#settings) |
| Fix an access, browser, or file path error | [Troubleshooting](docs/MANUAL_EN.md#troubleshooting) |

Question and column archives save progress item by item. For a long question, you can also fetch additional answer fragments from a known Zhihu pagination offset. The manual explains how the two recovery options work and what each one saves.

## Development and feedback

- [Development guide](docs/DEVELOPMENT.md) · Python API, local tests, and CI (Simplified Chinese)
- [Architecture and references](docs/ARCHITECTURE.md) · [Feature scope and roadmap](docs/FEATURE_TODO.md) (Simplified Chinese)
- [Report an issue](https://github.com/yuchenzhu-research/zhihu-scraper/issues) · Include the version, the command you ran, and the error with sensitive information removed

Licensed under the [MIT License](LICENSE). Archive content you have permission to access and respect platform rules, copyright, and privacy.
