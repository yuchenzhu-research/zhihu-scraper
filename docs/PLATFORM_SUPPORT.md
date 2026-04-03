# Platform Support / 平台支持边界

This document records the current support boundary for `zhihu-scraper`.
本文记录 `zhihu-scraper` 当前的平台支持边界。

## Support Tiers / 支持层级

| Platform | Tier | Current meaning |
| --- | --- | --- |
| macOS | Tier 1 | primary maintained platform, first-class local developer workflow |
| Linux | Tier 2 | actively hardened CLI path, but still catching shell and browser edge cases |
| Windows | Tier 3 | not yet a fully supported installation path |

## What "supported" currently means / 当前“支持”意味着什么

### Tier 1: macOS

- primary local development platform
- `zhihu` launcher and Textual TUI are expected to work here first
- manual validation happens here before other platforms

### Tier 1：macOS

- 当前主维护平台
- `zhihu` 启动入口和 Textual TUI 优先保证这里可用
- 新改动通常先在这里做人工验证

### Tier 2: Linux

- core CLI workflows should stay usable
- shell-friendly output naming is expected
- compatibility work is still ongoing for browser fallback and install ergonomics

### Tier 2：Linux

- 核心 CLI 路径应保持可用
- 输出目录命名应继续维持 shell-friendly
- 浏览器回退和安装体验仍在持续兼容加固

### Tier 3: Windows

- the repository acknowledges Windows as a target, but it is not yet a first-class setup path
- `install.sh` is not a Windows installer
- until a dedicated runbook and validation path exists, Windows should be treated as experimental

### Tier 3：Windows

- 仓库承认 Windows 是目标平台，但还不是一条正式的一等安装路径
- `install.sh` 不是 Windows 安装方案
- 在专门的 runbook 和验证链路补齐前，Windows 仍应视为实验性支持

## Current Validation Reality / 当前验证现状

- GitHub Actions validates `ubuntu-latest` and `macos-latest`
- unit tests currently cover:
  - CLI compatibility helpers
  - Textual TUI state and workflow basics
- cross-platform browser fallback is still not fully automated

- GitHub Actions 当前验证 `ubuntu-latest` 和 `macos-latest`
- 单测当前覆盖：
  - CLI 兼容辅助逻辑
  - Textual TUI 状态与基础工作流
- 跨平台浏览器回退仍未完全自动化

## Short-Term Engineering Rule / 短期工程规则

Until the Windows path is explicitly implemented, new features should avoid introducing more:

- Bash-only assumptions
- `.venv/bin/...` hardcoding in user-facing docs without Windows alternatives
- path patterns that depend on Unix shell semantics

在 Windows 路径明确实现之前，新功能应避免继续引入：

- Bash-only 假设
- 在用户文档里硬编码 `.venv/bin/...` 且不给 Windows 替代方案
- 依赖 Unix shell 语义的路径模式
