# Windows Runbook / Windows 运行说明

`zhihu-scraper` 目前把 Windows 视为实验性目标平台，而不是和 macOS / Linux 同等级的一等安装路径。

This runbook exists so Windows support is at least documented, bounded, and reviewable while the repository is still being hardened.

## Current Position / 当前定位

- Windows is **not** a first-class installation path yet
- `install.sh` is **not** a Windows installer
- the recommended validation path is currently:
  - Git Bash or PowerShell for CLI
  - a local Python 3.14+ installation
  - optional Playwright only after the pure API path is working

## Minimal Manual Setup / 最小手动安装路径

1. Clone the repository

```powershell
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
```

2. Create a virtual environment

```powershell
py -3.14 -m venv .venv
```

3. Activate it

```powershell
.venv\Scripts\activate
```

4. Install the project

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
```

5. Optional: enable browser fallback only after the base path works

```powershell
python -m pip install -e ".[full]"
python -m playwright install chromium
```

6. Prepare local runtime files

```powershell
mkdir .local
mkdir .local\cookie_pool
copy cookies.example.json .local\cookies.json
```

7. Run checks

```powershell
python cli\app.py check
python cli\app.py manual
```

## What to Expect / 当前预期

- `fetch`, `creator`, `batch`, `query`, and `check` are the preferred validation targets
- `interactive` may work, but it should still be treated as under verification on Windows
- Playwright fallback may require extra local browser / permission debugging
- if `pip install -e .` works but `.[full]` does not, the protocol/API path is still the first thing to validate

## Not Yet Guaranteed / 当前不保证

- `install.sh`
- `.venv/bin/...` style Unix paths
- shell behavior that depends on Bash / Zsh specifics
- a polished Windows launcher equivalent to `~/.local/bin/zhihu`

## Engineering Rule / 工程规则

Until Windows becomes a first-class path, new changes should avoid:

- hardcoding Unix-only launcher paths in user-facing guidance without alternatives
- introducing path naming that breaks in PowerShell or `cmd.exe`
- assuming Bash exists during normal usage

## Cross References / 关联文档

- [docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md)
- [docs/STAGE5_VALIDATION_MATRIX.md](docs/STAGE5_VALIDATION_MATRIX.md)
