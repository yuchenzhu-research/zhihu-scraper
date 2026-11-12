# 开发指南

[项目首页](../README.md) · [使用手册](MANUAL.md) · [架构说明](ARCHITECTURE.md) · [功能范围与路线图](FEATURE_TODO.md)

## 在 Python 中归档

`archive_url()` 是命令行和 Python 脚本共用的同步入口。下面将一篇文章保存为 Markdown、离线 HTML 和本地媒体。

```python
from pathlib import Path

from zhihu_scraper import ArchiveSettings, archive_url

report = archive_url(
    "https://zhuanlan.zhihu.com/p/108271985",
    ArchiveSettings(output_dir=Path("知乎归档"), html=True),
)

print(report.target.title)
print(report.receipt.entry_directory)
```

`ArchiveReport` 中的 `target` 是归一化后的内容，`receipt` 记录实际输出路径。媒体下载失败和内嵌视频解析警告分别见 `report.media_failures` 和 `report.embedded_video_warnings`。脚本也可以显式传入 `load_settings(Path("settings.toml"))` 的返回值。

### 批量进度和续抓

- 调用 `archive_url(url, settings, progress=callback)` 时，问题和专栏会通过 `BatchProgress` 通知 `started`、`saved`、`completed` 和 `interrupted`。`completed` 是本轮成功保存的条数，`total` 是可选的来源估计值。
- 批量保存开始后发生异常时，可从 `BatchArchiveInterruptedError.completed` 和 `receipt.entry_directory` 找到已写入的结果。`progress_saved` 表示中断时是否成功更新了 `receipt.progress_path`。按 `Ctrl+C` 取消时仍会收到 `KeyboardInterrupt`。
- 问题归档可传入 `offset=9980`，其中 `9980` 是示例，实际值应来自知乎分页请求。使用原有输出目录并启用 Markdown、关闭 HTML 和 PDF。续抓会按回答 ID 跳过已保存的片段，把新回答和索引分别写到 `回答片段/` 与 `续抓进度.md`。需要完整合并文档时，用默认的 `offset=0` 运行。

### 测试与扩展

`build_workflow()` 可注入 HTTP 客户端、浏览器工厂和归档器。自定义归档器通过 `archive()` 返回 `ArchiveReceipt`，提供输出路径与媒体失败信息。批量归档器还需实现 `begin_batch(target, offset=0)`，返回提供 `write_item`、`finish` 和 `interrupt` 的会话。续抓时，工作流使用会话的 `saved_item_ids` 跳过已保存的回答。模块职责和参考项目见[架构说明](ARCHITECTURE.md)。

## 本地检查与 CI

在仓库根目录安装锁定的开发依赖并运行常用检查。

```bash
uv sync --locked --extra dev
uv run --no-sync python -m pytest
uv run --no-sync python -m ruff check zhihu_scraper tests
uv run --no-sync python -m ruff format --check zhihu_scraper tests
uv run --no-sync python -m mypy zhihu_scraper
uv run --no-sync python -m compileall -q zhihu_scraper
uv lock --check
uv run --no-sync zhihu --help
```

常规测试使用本地数据和替身客户端。[CI](../.github/workflows/ci.yml) 在 Windows、macOS 和 Linux 上覆盖 Python 3.12、3.13、3.14，测试时将 `ResourceWarning` 当作错误。Ubuntu 另有一个任务，按 `pyproject.toml` 的版本约束安装依赖并验证 Chromium 启动与 PDF 导出。

### 真实浏览器 PDF 检查

下面用 Playwright 安装的 Chromium 验证 PDF 可读、专栏目录移动后链接仍有效，以及导出时未请求远程资源。新装的 Linux 环境可以在浏览器安装命令中添加 `--with-deps`，一并安装系统依赖。

```bash
uv run --no-sync python -m playwright install chromium
uv run --no-sync python tests/smoke/pdf_export.py
```

本机已有可识别的 Chrome 时，也可给 `pdf_export.py` 传入 `--system-chrome`。

### 真实知乎检查

只在需要验证真实接口时显式运行这套测试。先按[使用手册](MANUAL.md)配置自己的 Cookie，再在 macOS 或 Linux 的终端中运行以下命令，将示例路径替换为本地 Cookie 文件路径。

```bash
ZHIHU_LIVE=1 ZHIHU_COOKIE_FILE=/private/path/cookies.json \
  uv run --no-sync python -m pytest tests/live/live_archive.py
```

Windows PowerShell 用户可用 `$env:ZHIHU_LIVE` 和 `$env:ZHIHU_COOKIE_FILE` 设置相同的环境变量，然后运行同一条 `uv run` 命令。
