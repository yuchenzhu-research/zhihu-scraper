<div align="center">

# Zhihu-Scraper
### Local-First Zhihu Archival Scraper

<p><strong>A local-first Zhihu capture and archive project: protocol-first by default, browser fallback only when needed, with direct outputs to Markdown, image folders, and SQLite.</strong></p>

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
> **Disclaimer**
>
> This project is for learning, research, personal archiving, and technical exploration only. Follow Zhihu's Terms of Service, robots restrictions, and local laws. Do not use it for unauthorized scraping, resale, credential abuse, mass automation, or any illegal activity.

## 1. What this project is

`Zhihu-Scraper` is not a hosted scraping platform and not a SaaS product.  
It is a **local-first** archival tool with a narrow goal:

- take a Zhihu link
- fetch the content and metadata
- convert it to Markdown
- download images
- store the archive and search data locally

Good fit:

- personal archiving
- research collection
- CLI-first workflows
- local files plus local database
- an engineering project that keeps evolving

Not a fit:

- large-scale hosted scraping
- turnkey GUI product
- immediate JSON / CSV / MySQL export
- topic pages, site-wide search, broader discovery coverage

## 2. Current project status

This repository is no longer in the early “stack scripts into one file” stage.  
It has already gone through a full governance and restructuring cycle.

Current status in plain terms:

- core CLI paths work
- the Textual TUI is now the default interactive entry
- README / manual / `--help` / tests are being synchronized on purpose
- the six-stage hardening branch has already been merged back to `main`
- config and scraper result contracts are now moving toward typed boundaries
- further refactoring is still expected, especially around `core/config.py`, `core/scraper.py`, TUI state flow, and cross-platform validation

## 3. What works today

### Supported fetch targets

- single answers
- column articles
- latest N answers from a question page
- recent answers from a creator profile
- recent articles from a creator profile
- incremental collection monitoring

### Supported outputs

- `index.md`
- `images/`
- `zhihu.db`
- creator metadata files

### Supported entry styles

- `zhihu`
- `./zhihu`
- `python3 cli/app.py`

### Supported interaction styles

- regular CLI commands
- default **Textual TUI**
- compatibility fallback via `interactive --legacy`

## 4. What does not exist yet

- topic-page scraping
- JSON export
- CSV export
- MySQL persistence
- polished GUI
- LLM-based analysis
- first-class Windows installation experience

Those remain roadmap items, not current delivered features.

## 5. Python baseline

The repository is now aligned to:

- **Python 3.14+**

This is not just a cosmetic version bump. The runtime, tests, CI, and docs now move together on the 3.14+ baseline.

## 6. Quick start

### 6.1 Clone

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
```

### 6.2 Install

Recommended path:

```bash
./install.sh
```

If you want to fully rebuild the environment:

```bash
./install.sh --recreate
```

### 6.3 Configure cookies

The default runtime directory is now `.local/`:

```bash
mkdir -p .local
cp cookies.example.json .local/cookies.json
```

Then fill in your own:

- `z_c0`
- `d_c0`

The project also supports:

- `.local/cookie_pool/*.json`

And still keeps compatibility with legacy paths:

- `cookies.json`
- `cookie_pool/`

### 6.4 Hello world

```bash
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

### 6.5 Default home entry

```bash
zhihu
```

### 6.6 Full manual

```bash
zhihu manual
```

## 7. Command surface

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

### Common examples

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

## 8. Interactive workbench (TUI)

`interactive` now defaults to the **Textual TUI**.

Current TUI capabilities include:

- full-screen workbench
- centered layout
- input bar
- question-page limit selection
- current draft
- recent execution results
- retry flow

What is still being refined:

- tighter state panels
- clearer result summaries
- more typed contract integration
- less dependence on legacy flow

The old Rich / questionary flow is still present, but only as:

- regression fallback
- compatibility path
- non-default route

Use:

```bash
zhihu interactive
zhihu interactive --legacy
```

## 9. Output structure

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
│  └─ demo-user/
│     ├─ creator.json
│     ├─ README.md
│     └─ 2026-04-03_title--article-1/
│        └─ index.md
└─ zhihu.db
```

Meaning:

- normal outputs go under `entries/`
- creator mode goes under `creators/<url_token>/`
- SQLite lives at `zhihu.db`
- output naming has been moved toward shell-friendly patterns

## 10. Platform support boundary

Platform support here is an explicit engineering boundary, not a marketing sentence.

### macOS

- primary maintained platform
- installation, CLI, and TUI are validated here first

### Linux

- core CLI is usable
- path behavior, browser fallback, and install ergonomics are still being hardened

### Windows

- acknowledged as a target platform
- not a first-class installation path yet
- currently depends on runbook-style setup

Related docs:

- [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md)
- [docs/WINDOWS_RUNBOOK.md](docs/WINDOWS_RUNBOOK.md)

## 11. Configuration system

Default config location:

```text
config.yaml
```

Current config governance work already includes:

- separate config schema
- separate config runtime loader
- separate logging setup
- centralized project-path resolution
- backward-compatibility handling for older config fields

Inspect current effective config with:

```bash
zhihu config --show
zhihu config --path
```

## 12. Architecture and module state

### CLI layer

The CLI entrypoint is no longer supposed to hold every responsibility directly.
Important current boundaries include:

- `cli/app.py`
- `cli/launcher_flow.py`
- `cli/manual_content.py`
- `cli/config_view.py`
- `cli/healthcheck.py`
- `cli/save_pipeline.py`
- `cli/save_contracts.py`
- `cli/creator_metadata.py`

### Core layer

The core layer has also started moving away from oversized mixed-responsibility files:

- `core/config.py` is now a facade
- `core/config_runtime.py`
- `core/config_schema.py`
- `core/logging_setup.py`
- `core/project_paths.py`
- `core/scraper.py`
- `core/scraper_payloads.py`
- `core/scraper_contracts.py`

### Current direction

The real engineering direction is not “add more features at any cost”.  
It is:

- stabilize config boundaries
- stabilize scraper/result contracts
- keep large files from growing again
- continue separating TUI / CLI / core responsibilities

## 13. What today’s engineering work actually did

This was not just one or two patches. It was a staged governance and restructuring effort.

### Stage 1: governance foundation

- reorganized `references/`
- established skill foundation layout
- documented repository boundaries and stage docs

### Stage 2: system audit

- audited command surface
- audited platform support
- audited README / manual drift
- produced the stage-2 quality audit

### Stage 3: P0 usability fixes

- cleaned up `check`
- cleaned up missing-dependency messaging
- added platform boundary docs
- started splitting `cli/app.py`

### Stage 4: structural refactor

- extracted save pipeline
- extracted config view layer
- extracted scraper payload normalization

### Stage 5: validation matrix

- added command-surface tests
- added install-contract tests
- formalized the validation matrix
- added the Windows runbook

### Stage 6: release readiness and merge prep

- release review document
- issue-reply templates
- merge playbook

### New tranche after Stage 6

After the six stages, another engineering tranche continued with:

- config schema / runtime / logging / path separation
- typed save result contracts
- creator metadata rendering extraction
- pagination stats added to typed question fetch results

## 14. Testing and validation

The repository is no longer in “it seems to run on my machine” mode.

Current validation includes:

- `py_compile`
- unit tests
- command-surface guards
- docs-sync guards
- install-contract guards
- save pipeline guards
- scraper payload / contract guards
- TUI regressions
- CLI `--help` smoke checks

Validation matrix doc:

- [docs/STAGE5_VALIDATION_MATRIX.md](docs/STAGE5_VALIDATION_MATRIX.md)

## 15. Important repository docs

- [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md)
- [docs/WINDOWS_RUNBOOK.md](docs/WINDOWS_RUNBOOK.md)
- [docs/STAGE1_SKILL_FOUNDATION.md](docs/STAGE1_SKILL_FOUNDATION.md)
- [docs/STAGE2_QUALITY_AUDIT.md](docs/STAGE2_QUALITY_AUDIT.md)
- [docs/STAGE5_VALIDATION_MATRIX.md](docs/STAGE5_VALIDATION_MATRIX.md)
- [docs/STAGE6_RELEASE_REVIEW.md](docs/STAGE6_RELEASE_REVIEW.md)
- [docs/STAGE6_ISSUE_REPLY_TEMPLATES.md](docs/STAGE6_ISSUE_REPLY_TEMPLATES.md)
- [docs/STAGE6_MERGE_PLAYBOOK.md](docs/STAGE6_MERGE_PLAYBOOK.md)

## 16. Current engineering focus

The current focus is not to pile on more surface features. It is to keep the project structurally healthy:

- continue reducing `core/config.py`
- continue reducing `core/scraper.py`
- keep expanding typed contracts
- keep lowering CLI / TUI / core coupling
- keep improving cross-platform validation
- keep README / manual / tests / CI aligned

## 17. Roadmap

Already done:

- [x] single-answer fetching
- [x] column-article fetching
- [x] question-page pagination
- [x] creator fetching
- [x] incremental collection monitoring
- [x] Markdown + images + SQLite outputs
- [x] default interactive workbench (Textual TUI)
- [x] six-stage governance and merge back to main

Still not done:

- [ ] topic-page scraping
- [ ] JSON export
- [ ] CSV export
- [ ] MySQL persistence
- [ ] deeper TUI state-machine cleanup
- [ ] stronger Windows support
- [ ] stronger automated browser-fallback verification
- [ ] GUI
- [ ] LLM-based analysis features

## 18. FAQ

### Why Python 3.14+ now?

Because runtime expectations, tests, CI, and documentation have now been aligned to 3.14+ instead of keeping an older baseline alive.

### Why can it still run without cookies?

Guest mode can handle some public paths, but visibility and stability are both weaker. Creator pages, question pages, and collection monitoring rely much more on logged-in sessions.

### Why is `interactive --legacy` still there?

Because it is now a regression and fallback path, not the preferred interface.

### Why is this README so long now?

Because this version optimizes for “put the current state on the table” rather than polished brevity. It is meant to be broad, categorial, and easy to hand off for a second editing pass.
