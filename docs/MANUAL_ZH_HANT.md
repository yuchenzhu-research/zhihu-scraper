# Zhihu-Scraper 使用手冊

[简体中文](MANUAL.md) · **繁體中文** · [English](MANUAL_EN.md) · [專案首頁](../README_ZH_HANT.md)

[安裝與更新](#install) · [常用指令](#commands) · [登入與 Cookie](#login) · [設定](#settings) · [輸出檔案](#outputs) · [中斷與續抓](#resume) · [疑難排解](#troubleshooting)

<a name="install"></a>

## 安裝與更新

請先安裝 Git 和 Python 3.12 或更新版本。複製儲存庫後，進入專案目錄並選擇一種安裝方式。

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
```

### 使用 uv

Windows、macOS 與 Linux 都可使用 [uv](https://docs.astral.sh/uv/getting-started/installation/) 安裝專案鎖定的相依套件版本。

```bash
uv sync --locked
uv run zhihu --version
```

登入、瀏覽器備援與 PDF 匯出會使用瀏覽器。程式會先嘗試使用系統的 Chrome，找不到可用的 Chrome 時，可安裝 Playwright 的 Chromium。若是全新的 Linux 環境，可用第二條指令一併安裝系統套件，系統可能會要求輸入 `sudo` 密碼。

```bash
uv run playwright install chromium
# Linux 需要一併安裝系統套件時改用此行
uv run playwright install --with-deps chromium
```

要更新專案，請在專案目錄執行 `git pull --ff-only` 和 `uv sync --locked`。若使用 Playwright 管理的 Chromium，更新後可再執行瀏覽器安裝指令。

### 使用安裝指令碼

指令碼會建立 `.venv`，安裝專案及 Chromium，並在 Linux 上安裝瀏覽器需要的系統套件。

**macOS 或 Linux**

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

### 手動使用 pip

用 `python -m venv .venv` 建立虛擬環境。macOS 或 Linux 若只有 `python3` 指令，請改用 `python3 -m venv .venv`。用 `source .venv/bin/activate`（macOS 或 Linux）或 `.\.venv\Scripts\Activate.ps1`（Windows PowerShell）啟用後，執行下列指令。

```bash
python -m pip install -e .
python -m playwright install chromium
```

全新的 Linux 環境可改用 `python -m playwright install --with-deps chromium`。使用安裝指令碼或 pip 並啟用 `.venv` 後，下文的 `uv run zhihu …` 直接寫成 `zhihu …` 即可。

<a name="commands"></a>

## 常用指令

將下表中的 `"URL"` 換成以 `https://` 開頭的完整知乎連結。支援的連結類型請見[專案首頁](../README_ZH_HANT.md)。

| 想做什麼 | 指令 |
| --- | --- |
| 儲存 Markdown 和本機媒體 | `uv run zhihu fetch "URL"` |
| 同時輸出離線 HTML | `uv run zhihu fetch --html "URL"` |
| 同時輸出 PDF | `uv run zhihu fetch --pdf "URL"` |
| 擷取留言及回覆 | `uv run zhihu fetch --comments "URL"` |
| 只保留媒體連結 | `uv run zhihu fetch --no-media "URL"` |
| 指定輸出資料夾 | `uv run zhihu fetch -o "./archive" "URL"` |
| 使用設定檔 | `uv run zhihu fetch -s settings.toml "URL"` |

選項可以一起使用，例如 `uv run zhihu fetch --html --comments "URL"`。啟用留言後，每篇內容預設保存最多 10 則第一層留言，每則留言保存最多 10 則回覆。可在[設定](#settings)中調整上限。

用 `uv run zhihu --help` 查看子指令，或用 `uv run zhihu fetch --help` 查看擷取參數。`init`、`login` 和 `check` 也各有 `--help`。

<a name="login"></a>

## 登入與 Cookie

有些公開內容可以直接擷取。若知乎要求登入，先準備設定檔，再在開啟的瀏覽器中登入。指令會驗證登入狀態，再儲存 Cookie。

```bash
uv run zhihu init
uv run zhihu login -s settings.toml
```

依終端機提示，在 `settings.toml` 現有的 `[network]` 區段填入 `cookie_file`。預設儲存位置為 `.local/cookies.json`。

```toml
cookie_file = ".local/cookies.json"
```

```bash
uv run zhihu check -s settings.toml
uv run zhihu fetch --html -s settings.toml "https://zhuanlan.zhihu.com/p/108271985"
```

瀏覽器登入最多等待 180 秒。按 Ctrl+C 取消、逾時或儲存失敗時，原有的 Cookie 檔會保留。如果本機 Chrome 已開啟遠端偵錯並登入知乎，也可以用 `uv run zhihu login --cdp http://127.0.0.1:9222` 讀取知乎 Cookie。這個指令會保留目前開啟的頁面。

手動匯入時，可使用只含知乎 Cookie 的 JSON 鍵值物件，或依照[範例清單格式](../cookies.example.json)填寫。清單只接受網域為 `zhihu.com` 或其子網域的記錄。用 `uv run zhihu check --cookie-file "./.local/cookies.json"` 可檢查指定的檔案。

Cookie 檔以明文儲存登入憑證，請放在本機的私人資料夾。`.local/` 已排除於 Git 版控之外，設定檔只需填寫 Cookie 檔案路徑。回報問題前請移除登入憑證與其他私人資訊。

<a name="settings"></a>

## 設定檔

`uv run zhihu init` 會建立 `settings.toml`，並保留同名的既有檔案。擷取、登入及檢查時，用 `-s settings.toml` 指定設定檔。相對路徑以執行指令時所在的目錄為基準。

| 區段 | 可調整項目 |
| --- | --- |
| `[archive]` | 輸出目錄 `output_dir`、格式 `markdown`、`html`、`pdf`、留言設定 `comments`、`comment_roots`、`comment_replies` 及媒體下載 `media_download` |
| `[network]` | `cookie_file`、`proxy`、逾時 `timeout`、重試次數 `retries`、分頁大小 `page_size`、請求間隔 `request_interval` 和隨機等待時間 `request_jitter` |
| `[browser]` | `fallback`、`headless`、本機 Chrome 的 `cdp_url` |

指令列選項優先於設定檔。`--no-html`、`--no-pdf`、`--no-comments` 或 `--no-media` 可關閉本次擷取的對應選項。

`browser.fallback` 預設為 `auto`，HTTP 擷取受阻或資料無法使用時會嘗試瀏覽器。`never` 只使用 HTTP，`always` 會直接以瀏覽器讀取目標頁面，分頁及留言仍可能使用 HTTP。本次擷取可用 `--browser auto`、`--browser never` 或 `--browser always` 指定策略。

`network.proxy` 適用於 HTTP 請求、專案啟動的瀏覽器與媒體下載。若使用 `browser.cdp_url` 或擷取時指定 `--cdp`，外部 Chrome 會沿用自己的代理設定。CDP 僅接受本機迴路地址（`localhost`、`127.0.0.1` 或 `[::1]`）的 HTTP 或 WebSocket URL。

<a name="outputs"></a>

## 輸出檔案

預設存到目前工作目錄下的 `知乎归档/`。單篇內容通常會建立以標題命名的資料夾，並把下載成功的媒體放在 `media/`。完整問題會把各個回答合併成一份文件，專欄則會建立目錄與 `内容/`，分開保存各篇文章。要搬移或備份封存結果，請帶走整個資料夾，保留文件與媒體的相對位置。

- **Markdown** 保留正文結構和原始 TeX。
- **媒體** 關閉下載或選用的媒體下載失敗時，文件會保留來源連結。獨立影片的主要檔案下載失敗時，指令會回報錯誤。
- **離線 HTML** 可直接用瀏覽器開啟，樣式在 `assets/`。可轉換的公式以瀏覽器原生的 MathML 顯示。
- **PDF** 需要 Chrome 或 Chromium，能保存公式、表格與已下載的圖片，影片會以來源連結呈現。專欄索引和各篇文章會分別產生 PDF。若只想要 PDF，在設定檔的 `[archive]` 區段設為 `markdown = false`、`html = false`、`pdf = true`。設定檔至少需啟用一種輸出格式。

<a name="resume"></a>

## 中斷與續抓

問題與專欄會逐項保存。終端機會顯示進度檔路徑，一般封存的進度檔通常是 `归档进度.md`。中斷後重跑原指令，程式會重新讀取清單，並沿用原資料夾、檔名與有效的媒體檔。全部成功後才更新完整的問題文件或專欄目錄。

如果已知問題的知乎 API 分頁偏移量，可以沿用原設定和輸出資料夾，直接從該位置接續擷取。

```bash
uv run zhihu fetch "https://www.zhihu.com/question/1976120753834443272" -s settings.toml --offset 9980 --no-html --no-pdf
```

- `9980` 是範例。請從實際分頁請求取得 `offset`，已保存的回答數可能不同。
- 請沿用原本的封存目錄。先前用過 `-o` 時，請再次指定同一路徑。使用內建預設值時，可省略 `-s settings.toml`。
- 正數 `--offset` 只適用於問題連結，且只支援 Markdown 輸出。請保留 `archive.markdown = true`，並關閉 HTML 和 PDF。
- 程式會依回答 ID 略過已保存的回答片段，把新回答存進 `回答片段/`，索引通常寫在 `续抓进度.md`。原有完整文件會保留。
- 抓到末頁後，可透過索引閱讀本機片段。若要重新合併出完整文件，請執行未指定 `--offset` 的擷取指令。

同一目標的媒體下載中斷時，若伺服器提供可靠的驗證資訊，重跑可繼續下載既有的 `.part` 檔案。

<a name="troubleshooting"></a>

## 疑難排解

| 遇到的情況 | 可以怎麼做 |
| --- | --- |
| 登入已失效或知乎要求驗證 | 用 `uv run zhihu check -s settings.toml` 確認，再用 `uv run zhihu login -s settings.toml` 更新登入狀態。擷取時請使用同一份設定檔。 |
| 瀏覽器無法啟動或 PDF 無法輸出 | 依[安裝步驟](#install)安裝 Chromium。Linux 也需要瀏覽器的系統套件。 |
| HTTP 429 或伺服器要求稍後重試 | 等候一段時間再重跑。每次 HTTP 請求或個別媒體下載最多累計等待 60 秒後停止重試。批次擷取時，可增加 `network.request_interval` 來放慢請求頻率。 |
| Windows 提示輸出路徑太長 | 用 `-o "C:/archive"` 等較短的絕對路徑，也可以修改 `archive.output_dir`。如要繼續先前中斷的工作，先將整份封存資料移至新位置。 |
| 問題或專欄抓到一半停止 | 查看進度檔和終端機的「中断原因」，依[續抓步驟](#resume)重跑。若回報 Issue，可附上已去除登入憑證的指令、系統、版本及錯誤資訊。 |

可到 [GitHub Issues](https://github.com/yuchenzhu-research/zhihu-scraper/issues) 搜尋或回報問題。
