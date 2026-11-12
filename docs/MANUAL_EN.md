# Zhihu-Scraper User Manual

[简体中文](MANUAL.md) · [繁體中文](MANUAL_ZH_HANT.md) · **English** · [Project home](../README_EN.md)

[Install and update](#install) · [Common commands](#commands) · [Sign in](#login) · [Settings](#settings) · [Output files](#outputs) · [Resume](#resume) · [Troubleshooting](#troubleshooting)

<a name="install"></a>

## Install and update

Install Git and Python 3.12 or newer. Clone the repository and enter its directory before choosing an installation method.

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
```

### Use uv

On Windows, macOS, and Linux, [uv](https://docs.astral.sh/uv/getting-started/installation/) installs the dependency versions pinned in the repository.

```bash
uv sync --locked
uv run zhihu --version
```

Signing in, browser fallback, and PDF export require a browser. The tool tries system Chrome first. If Chrome is unavailable, install Playwright's Chromium. On a fresh Linux system, the second command also installs required system libraries and may ask for your `sudo` password.

```bash
uv run playwright install chromium
# On Linux when system libraries are also needed
uv run playwright install --with-deps chromium
```

To update an existing checkout, run `git pull --ff-only` and `uv sync --locked` in the repository. If you use Playwright's Chromium, rerun the browser installation command after updating.

### Use an install script

The scripts create `.venv` in the repository and install the project and Chromium. The Linux script also installs the required browser libraries.

**macOS / Linux**

```bash
./scripts/install.sh
source .venv/bin/activate
zhihu --version
```

**Windows PowerShell**

```powershell
.\scripts\install.ps1
.\.venv\Scripts\Activate.ps1
zhihu --version
```

### Install manually with pip

Run `python -m venv .venv` in the repository, then activate the environment using the command for your platform above. On macOS or Linux, use `python3` if that is the command for your Python 3.12 or newer installation.

```bash
python -m pip install -e .
python -m playwright install chromium
```

On Linux, use `python -m playwright install --with-deps chromium` if you also need the system libraries. If you activated `.venv`, drop `uv run` from the examples below.

<a name="commands"></a>

## Common commands

Replace `"URL"` with a full Zhihu link starting with `https://`. See the [project home](../README_EN.md) for supported link types.

| Goal | Command |
| --- | --- |
| Save Markdown and local media | `uv run zhihu fetch "URL"` |
| Also save offline HTML | `uv run zhihu fetch --html "URL"` |
| Also export a PDF | `uv run zhihu fetch --pdf "URL"` |
| Also save comments | `uv run zhihu fetch --comments "URL"` |
| Keep media as source links | `uv run zhihu fetch --no-media "URL"` |
| Choose an output directory | `uv run zhihu fetch -o "./archive" "URL"` |
| Load a settings file | `uv run zhihu fetch -s settings.toml "URL"` |

Options can be combined, as in `uv run zhihu fetch --html --comments "URL"`. With comments enabled, each item saves up to 10 top-level comments and 10 replies per comment by default. Adjust these limits in [settings](#settings).

Run `uv run zhihu --help` to see the available commands, or `uv run zhihu fetch --help` for all fetch options. The `init`, `login`, and `check` commands also accept `--help`.

<a name="login"></a>

## Sign in and store cookies

When Zhihu requires you to sign in, create a settings file and have the tool open a browser.

```bash
uv run zhihu init
uv run zhihu login -s settings.toml
```

Sign in through the browser window. The tool waits up to 180 seconds and saves your cookies after verifying the session. The default location is `.local/cookies.json`. The previous file is preserved if you cancel, the session times out, or the save fails. Follow the printed instructions to set `cookie_file` in the existing `[network]` section of `settings.toml`. If you used the default location, add the following line to that section.

```toml
cookie_file = ".local/cookies.json"
```

```bash
uv run zhihu check -s settings.toml
uv run zhihu fetch --html -s settings.toml "https://zhuanlan.zhihu.com/p/108271985"
```

If you already have a signed-in local Chrome with remote debugging (CDP) enabled, use `uv run zhihu login --cdp http://127.0.0.1:9222` to read its Zhihu cookies.

You can also import JSON as a Zhihu cookie name-to-value object or use the [example list format](../cookies.example.json). List entries must specify `zhihu.com` or a subdomain. To check a file directly, run `uv run zhihu check --cookie-file "./.local/cookies.json"`.

The cookie file stores login credentials in plain text. Keep it in a private local directory. Git ignores `.local/`, and `settings.toml` only needs the path to the file. Remove credentials and other private information from issue reports.

<a name="settings"></a>

## Settings file

Run `uv run zhihu init` to generate a `settings.toml` with defaults. The command preserves existing files. Pass `-s settings.toml` each time you want to use the file. Relative paths start from the directory where you run the command.

| Section | Settings |
| --- | --- |
| `[archive]` | Destination `output_dir`, formats `markdown`, `html`, and `pdf`, comments `comments`, `comment_roots`, and `comment_replies`, and media switch `media_download` |
| `[network]` | `cookie_file`, `proxy`, `timeout`, `retries`, `page_size`, `request_interval`, and random wait `request_jitter` |
| `[browser]` | Browser policy `fallback`, hidden browser window `headless`, and local debugging endpoint `cdp_url` |

Command-line options override the file for the current run. Use `--no-html`, `--no-pdf`, `--no-comments`, or `--no-media` to turn off the corresponding feature. With `--browser auto` (the default), the tool tries HTTP/API first and uses a browser when needed. Use `never` for HTTP/API only or `always` to get the target page data from the browser first. Later pages of a question or column can still use the API.

Use `--cdp` or `browser.cdp_url` to connect to a local browser with remote debugging enabled. The endpoint must use HTTP or WebSocket on `localhost`, `127.0.0.1`, or `[::1]`. The configured `network.proxy` applies to HTTP requests, media downloads, and browsers launched by the tool. An attached browser uses its own proxy settings.

<a name="outputs"></a>

## Output files and formats

The default destination is `知乎归档/` in the current directory. Each target gets its own folder with its main document and any media downloaded to `media/`. A complete question archive combines the answers into one document. A column archive contains an index and saves the articles in `内容/`. Move the whole folder to keep relative links working.

- **Markdown** preserves the structure of the content and the original TeX.
- **Media** remain source links if downloads are disabled or an optional download fails. If a standalone video's main file fails to download, the command reports an error.
- **Offline HTML** opens in a browser and uses local styles from `assets/`. Supported formulas render as native MathML.
- **PDF** uses Chrome or Chromium to render local content. Videos are represented by source links. A column has a PDF for its index and one for each article. For PDF-only output, set `markdown = false`, `html = false`, and `pdf = true` under `[archive]`. At least one output format must be enabled.

<a name="resume"></a>

## Recover from an interruption

Questions and columns save each item as it finishes. The terminal shows the progress file path, usually `归档进度.md` for a full run. Rerun the original command after an interruption. The tool reads the list from the start and reuses the existing directory and valid media. It publishes the new complete column index or merged question document once the run succeeds.

If you know the **API pagination offset** for a question's answer list, you can continue at that position. The `9980` below is an example offset. The saved count shown in the terminal can differ because of deduplication.

```bash
uv run zhihu fetch "https://www.zhihu.com/question/1976120753834443272" -s settings.toml --offset 9980 --no-html --no-pdf
```

- Use the original archive directory. Pass the same `-o` if you used one before. Drop `-s settings.toml` if you use built-in defaults.
- A positive `--offset` requires a question URL and Markdown-only output. Keep `archive.markdown = true`.
- The tool skips saved answer fragments by ID and writes new ones to `回答片段/`. Its index is usually `续抓进度.md`. Existing complete documents are preserved.
- Reaching the final page finishes the fragment run. To rebuild the complete question document, run the command again with `--offset` omitted.

When a media download is interrupted, rerunning the same target can continue a `.part` download if the server supplies reliable validation information.

<a name="troubleshooting"></a>

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| Zhihu requires sign-in or the session expired | Run `uv run zhihu check -s settings.toml`, then `uv run zhihu login -s settings.toml` to refresh the session. Pass the same settings file when fetching. |
| The browser is missing or PDF export fails | Check that Chrome opens, or install Playwright's Chromium as shown in [Install and update](#install). |
| The output path is too long on Windows | Use `-o` with a short absolute path such as `-o "C:/archive"`, or set `archive.output_dir`. Move the entire archive to the new location if you intend to continue an interrupted run. |
| HTTP 429 or a message asking you to wait | Wait before retrying. Each HTTP request and each media download has a total retry wait budget of 60 seconds. For batch archives, increase `network.request_interval` to slow down requests. |
| A question or column stops partway through | Check the terminal's `中断原因` (interruption reason) and the progress file. When reporting the problem, include the command, tool version, operating system, and redacted error output. |

Search or report problems in [GitHub Issues](https://github.com/yuchenzhu-research/zhihu-scraper/issues).
