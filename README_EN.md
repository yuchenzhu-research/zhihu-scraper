<div align="center">

# Zhihu-Scraper
### Local-first Zhihu Archiving Tool

<p><strong>A local-first Zhihu extraction and archiving project: protocol-first, with browser fallback when needed, writing directly to Markdown, image folders, and SQLite.</strong></p>

<p>
  <img src="https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg" alt="CI Badge" />
  <img src="https://img.shields.io/static/v1?label=python&message=3.14%2B&color=3776AB&style=flat-square&logo=python&logoColor=white" alt="Python Badge" />
  <img src="https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper?style=flat-square" alt="License Badge" />
</p>

<p>
  <a href="README.md">简体中文</a> · <strong>English</strong>
</p>

</div>

> [!WARNING]
> This project is for learning, research, personal archiving, and technical exploration only.

## 1. What This Project Is

This repository is a **local-first** Zhihu archiving tool.

Its main goals are:

- accept Zhihu links
- fetch body content and key metadata
- convert content to Markdown
- download images
- persist archives locally with SQLite

It is suitable for:

- personal archiving
- research collection
- command-line workflows
- local file + local database usage

It is not intended to be:

- an online scraping platform
- a hosted service
- a GUI-first product
- a full-site data pipeline

## 2. Current Scope

Currently supported:

- single answers
- column articles
- latest N answers from a question page
- recent answers and articles from a creator profile
- incremental collection monitoring
- Markdown + images + SQLite outputs
- default interactive workbench: **Textual TUI**
- compatibility fallback: `interactive --legacy`

Not treated as current delivered features:

- topic-page scraping
- GUI application
- hosted service model
- MySQL / remote storage as default targets

## 3. Quick Start

### 3.1 Install

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
./install.sh
```

To rebuild the environment:

```bash
./install.sh --recreate
```

Current maintained baseline:

- Python 3.14+

### 3.2 Prepare Cookies

The runtime directory is centered on `.local/`:

```bash
mkdir -p .local
cp cookies.example.json .local/cookies.json
```

Fill in:

- `z_c0`
- `d_c0`

Historical paths are still compatible:

- `cookies.json`
- `cookie_pool/`

After setup, use the following commands to confirm whether runtime resolution
is still hitting legacy repo-root compatibility paths:

- `zhihu config --show`
- `zhihu check`

They show the configured path, active path, and whether legacy cookie-path
fallback is still active.

### 3.3 Minimal Run

```bash
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

Open the home entry or TUI:

```bash
zhihu
zhihu interactive
zhihu interactive --legacy
```

Entry topology:

- `zhihu`
  opens the home launcher for first-run guidance, command navigation, and checks
- `zhihu interactive`
  opens the default Textual TUI archive workbench directly
- `zhihu interactive --legacy`
  opens the old Rich / questionary fallback for compatibility and troubleshooting

## 4. Command Overview

Current core commands:

- `zhihu onboard`
- `zhihu fetch`
- `zhihu creator`
- `zhihu batch`
- `zhihu monitor`
- `zhihu query`
- `zhihu interactive`
- `zhihu config --show`
- `zhihu check`
- `zhihu manual`

Entry topology:

- `zhihu`
  enters the home launcher when invoked without arguments
- `zhihu interactive`
  goes straight to the recommended Textual TUI
- `zhihu interactive --legacy`
  goes straight to the compatibility fallback

Common examples:

```bash
zhihu onboard
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
zhihu creator "https://www.zhihu.com/people/iterator"
zhihu batch urls.txt
zhihu monitor 78170682
zhihu query "Transformer"
zhihu interactive
zhihu interactive --legacy
zhihu config --show
zhihu check
zhihu manual
```

Notes:

- `zhihu query` now shows the stable identity `content_key = type:id`
- `answer_id` remains as a compatibility field, but is no longer the primary public identifier

## 5. Output Layout

Default output root:

```text
data/
```

Typical structure:

```text
data/
├─ entries/
│  └─ 2026-04-03_title--answer-123456/
│     ├─ index.md
│     └─ images/
├─ creators/
│  └─ <url_token>/
│     ├─ creator.json
│     └─ README.md
└─ zhihu.db
```

## 6. Basic Directory Guide

```text
cli/    command entrypoints, interaction, save orchestration
core/   scraping, config, conversion, database, runtime logic
docs/   platform, config, workflow and maintenance docs
tests/  unittest regression suite
data/   default archive output
.local/ cookies, logs and runtime files
```

## 7. Platform Support

The explicit support boundary lives in [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md).

In short:

- macOS: primary maintained platform
- Linux: actively hardened
- Windows: documented, but not yet a first-class install path

Windows-specific notes:

- [docs/WINDOWS_RUNBOOK.md](docs/WINDOWS_RUNBOOK.md)

## 8. More Documentation

Use this README as the external entrypoint.  
For maintenance and collaboration details, continue with:

- [MANUAL.md](MANUAL.md)
- [AGENTS.md](AGENTS.md)
- [docs/dependency-map.md](docs/dependency-map.md)
- [docs/config.md](docs/config.md)
- [docs/workflows.md](docs/workflows.md)

## 9. Interactive Entry Notes

`zhihu` without arguments opens the home launcher.  
`zhihu interactive` is the direct command for the **Textual TUI**.

The old Rich / questionary path is still available via:

```bash
zhihu interactive --legacy
```

It is kept for compatibility and troubleshooting, not as the preferred path.  
The scraping pipeline remains protocol-first, with browser fallback only when needed.
