"""
manual_content.py - Built-in terminal manual content

Keeps the large manual body out of cli/app.py so command routing and operator
documentation are no longer mixed into one oversized file.
"""

from __future__ import annotations

from pathlib import Path


def build_manual_text(default_output_dir: Path) -> str:
    return f"""
NAME
  zhihu - Local-first Zhihu extractor with Markdown + SQLite outputs
  zhihu - 面向本地归档的知乎提取工具（Markdown + SQLite）

SYNOPSIS
  zhihu <command> [options]
  ./zhihu <command> [options]
  python3 cli/app.py <command> [options]

INSTALL MODEL
  - `pyproject.toml` is the dependency source of truth
  - `./install.sh` is the official one-shot installer
  - `./install.sh --recreate` rebuilds `.venv` from scratch
  - `zhihu` is the preferred global entrypoint after installation
  - `./zhihu` remains the repository-local fallback and prefers the local `.venv`

PAGER
  Exit manual / 退出说明书:
  - press `q` in most terminals / 大多数终端按 `q`
  - if pager is not active: `Ctrl+C` / 若分页器未接管可按 `Ctrl+C`

HOME MENU
  Open / 打开:
  - `zhihu`
  - `./zhihu`
  - `python3 cli/app.py`

  Behavior / 行为:
  - opens the home launcher, not the Textual workbench itself
  - 打开首页 launcher，而不是直接进入 Textual 工作台

  Controls / 操作方式:
  - arrow keys: move / 方向键移动
  - `Enter`: confirm / 回车确认
  - `Space`: toggle checkbox options / 空格勾选复选项
  - `Ctrl+C`: exit current screen / 退出当前界面

INTERACTIVE MODES
  - `zhihu interactive`
    direct entry to the default Textual TUI / 直达默认 Textual TUI
  - `zhihu interactive --legacy`
    compatibility fallback to the old Rich/questionary flow / 兼容回退到旧版 Rich/questionary

COMMAND INDEX
  - onboard
  - fetch
  - creator
  - batch
  - monitor
  - query
  - interactive
  - config --show / --path
  - check
  - manual

COMMAND REFERENCE

1) fetch
  Purpose:
  - scrape one URL, or extract and scrape multiple Zhihu URLs from mixed text
  - 支持从混合文本中自动识别多条知乎链接并抓取

  Supported links:
  - article: https://zhuanlan.zhihu.com/p/<id>
  - answer:  https://www.zhihu.com/question/<qid>/answer/<aid>
  - question page: https://www.zhihu.com/question/<qid>

  Options:
  - `-o, --output PATH` output base directory
  - `-n, --limit INT` question-page answer count (must be >= 1)
  - `-i, --no-images` skip image downloading
  - `-b, --headless` browser headless switch for fallback path

  Behavior:
  - article path: protocol HTML fetch first, then one cookie-rotation retry, then Playwright fallback if still blocked
  - `-n <= 20`: usually single page
  - `-n > 20`: auto pagination with random waits
  - `-n > 50`: higher anti-bot risk warning

  Examples:
  - `zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"`
  - `zhihu fetch "text ... https://www.zhihu.com/question/28696373 ..."`
  - `zhihu fetch "https://www.zhihu.com/question/28696373" -n 10`

2) creator
  Purpose:
  - fetch creator answers + articles in batch
  - 批量抓取作者回答和专栏

  Input:
  - profile URL: `https://www.zhihu.com/people/<url_token>`
  - raw token: `<url_token>`

  Options:
  - `-o, --output PATH` output base directory
  - `--answers INT` max answers (default 10, >= 0)
  - `--articles INT` max articles (default 5, >= 0)
  - `-i, --no-images` skip image downloading

  Defaults:
  - answers = 10
  - articles = 5
  - output base = `{default_output_dir}`

  Examples:
  - `zhihu creator "https://www.zhihu.com/people/iterator"`
  - `zhihu creator iterator --answers 20 --articles 10`

3) batch
  Purpose:
  - load URL list file and fetch concurrently
  - 从文件读取 URL 列表并发抓取

  Options:
  - `-o, --output PATH`
  - `-c, --concurrency INT` requested concurrency (effective cap: 8)
  - `-i, --no-images`
  - `-b, --headless`

  Example:
  - `zhihu batch urls.txt -c 4`

4) monitor
  Purpose:
  - incremental monitoring for a Zhihu collection
  - 知乎收藏夹增量监控与下载

  Options:
  - `-o, --output PATH`
  - `-c, --concurrency INT` (effective cap: 8)
  - `-i, --no-images`
  - `-b, --headless`

  Behavior:
  - checks new items since last pointer
  - pointer advances only when current round has no failures
  - unsupported-only new collection items still advance the pointer so the same non-archiveable head items are not re-scanned forever
  - avoids skipping failed items in next run

  Example:
  - `zhihu monitor 78170682 -c 4`

5) query
  Purpose:
  - query local `zhihu.db`
  - 在本地数据库中检索标题与正文

  Options:
  - `-l, --limit INT` max rows (default 10)
  - `-d, --data-dir PATH` where `zhihu.db` is located

  Example:
  - `zhihu query "Transformer" -l 20`

6) interactive
  Purpose:
  - full-screen archive workbench with draft, queue, recent-result, and retry flow
  - 全屏归档工作台，包含草案、队列、最近结果与失败重试

  Entrypoints:
  - `zhihu` opens the launcher first
  - `zhihu interactive` opens the Textual workbench directly
  - `zhihu interactive --legacy` opens the deprecated fallback

  Current support:
  - answer / article / question links
  - `Enter`: build current draft
  - `Ctrl+R`: execute current draft
  - `Ctrl+Y`: load retry draft from the latest failed records
  - does NOT parse `people/...` creator links in interactive mode
  - use `creator` command for profile URLs
  - `--legacy`: deprecated fallback to the old Rich/questionary flow

7) config
  Purpose:
  - show loaded configuration

  Options:
  - `--show` print current config summary
  - `--path` show config file path

  Examples:
  - `zhihu config --show`
  - `zhihu config --path`

8) check
  Purpose:
  - environment sanity checks

  Checks:
  - `config.yaml` existence
  - configured cookie file validity
  - Playwright availability under current browser config

  Example:
  - `zhihu check`

9) manual
  Purpose:
  - open this built-in manual in pager

OUTPUT STRUCTURE
  Base: `{default_output_dir}`

  - `entries/`
    normal outputs from fetch / batch / monitor
  - `creators/<url_token>/`
    creator-mode outputs
  - `zhihu.db`
    shared SQLite database

  Creator directory files:
  - `creator.json`: creator metadata + sync state
  - `README.md`: local index for this creator

PLATFORM SUPPORT
  - macOS: primary maintained platform
  - Linux: actively hardened CLI path
  - Windows: not yet a first-class install path
  - see `docs/PLATFORM_SUPPORT.md` for the explicit support boundary

  ARCHITECTURE (LAYER MAP)
  CLI Layer
  - `cli/app.py` command routing + terminal entrypoint
  - `cli/archive_execution.py` shared execution bridge for CLI / TUI / legacy
  - `cli/config_view.py` config summary rendering
  - `cli/launcher_flow.py` home menu + onboarding flow
  - `cli/manual_content.py` built-in manual source
  - `cli/save_pipeline.py` archive save orchestration
  - `cli/interactive.py` Textual-based interactive workbench
  - `cli/interactive_legacy.py` deprecated Rich/questionary fallback

  Fetch Layer
  - `core/scraper.py`
    URL type detection, protocol-first fetch, question pagination,
    creator pagination, image download
  - `core/scraper_payloads.py`
    normalized payload builders for article / answer / creator content

  Access Layer
  - `core/api_client.py` Zhihu API access + cookie-based requests
  - `core/browser_fallback.py` Playwright fallback (mainly article path)

  Data Layer
  - `core/converter.py` HTML -> Markdown conversion
  - `core/db.py` SQLite persistence and query
  - `core/monitor.py` incremental collection pointer management

  Config & Runtime
  - `core/config.py` config loading + logging + humanized delay
  - `core/cookie_manager.py` cookie file + cookie pool handling

CURRENT LIMITS
  - interactive mode does not accept creator profile URLs (`people/...`)
  - article path is protocol-first, but some columns still need Playwright fallback under active WAF
  - browser fallback is strongest on article path; answer/question stay API-first
  - query uses SQLite keyword matching, not advanced ranking search

QUICK START
  - `./install.sh`
  - `./install.sh --recreate`  # when the local environment is broken
  - `zhihu`                    # open the home menu / 打开首页菜单
  - `zhihu interactive`        # open the Textual TUI directly / 直达 Textual 工作台
  - `zhihu check`
  - `zhihu manual`
""".strip()
