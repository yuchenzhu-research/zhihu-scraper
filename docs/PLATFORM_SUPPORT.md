# Platform Support

This document records the current support boundary for `zhihu-scraper`.

## Support Tiers

| Platform | Tier | Current meaning |
| --- | --- | --- |
| macOS | Tier 1 | primary maintained platform, first-class local developer workflow |
| Linux | Tier 2 | actively hardened CLI path, but still catching shell and browser edge cases |
| Windows | Tier 3 | not yet a fully supported installation path |

## What "supported" currently means

### Tier 1: macOS

- primary local development platform
- `zhihu` launcher and Textual TUI are expected to work here first
- manual validation happens here before other platforms

### Tier 2: Linux

- core CLI workflows should stay usable
- shell-friendly output naming is expected
- compatibility work is still ongoing for browser fallback and install ergonomics

### Tier 3: Windows

- the repository acknowledges Windows as a target, but it is not yet a first-class setup path
- `install.sh` is not a Windows installer
- until a dedicated runbook and validation path exists, Windows should be treated as experimental

## Current validation reality

- GitHub Actions validates `ubuntu-latest` and `macos-latest`
- unit tests currently cover:
  - CLI compatibility helpers
  - Textual TUI state and workflow basics
- cross-platform browser fallback is still not fully automated

## Short-term engineering rule

Until the Windows path is explicitly implemented, new features should avoid introducing more:

- Bash-only assumptions
- `.venv/bin/...` hardcoding in user-facing docs without Windows alternatives
- path patterns that depend on Unix shell semantics
