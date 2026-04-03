"""
app.py - CLI Enhancement Module

Provides modern command-line interface using Typer with auto-completion support.

Core Functions:
- fetch: Scrape single Zhihu link (article/answer/question)
- creator: Scrape answers and articles from a Zhihu creator profile
- batch: Batch scrape multiple links
- monitor: Incremental monitoring of collections
- query: Search scraped content in SQLite database
- interactive: Interactive scraping mode
- config: View/manage configuration
- check: Check environment dependencies

Usage Examples:
    zhihu fetch "https://www.zhihu.com/p/123456"
    zhihu fetch "https://www.zhihu.com/question/123456" -n 10
    zhihu batch ./urls.txt -c 8
    zhihu monitor 78170682 -o ./data
    zhihu query "深度学习" -l 20

================================================================================
app.py — CLI 增强模块

使用 Typer 提供现代化命令行接口，支持参数自动补全。

核心功能：
- fetch: 抓取单个知乎链接 (文章/回答/问题)
- creator: 抓取知乎作者主页下的回答和专栏
- batch: 批量抓取多个链接
- monitor: 增量监控收藏夹
- query: 在 SQLite 数据库中检索已抓取的内容
- interactive: 交互式抓取模式
- config: 查看/管理配置
- check: 检查环境依赖

使用示例：
    zhihu fetch "https://www.zhihu.com/p/123456"
    zhihu fetch "https://www.zhihu.com/question/123456" -n 10
    zhihu batch ./urls.txt -c 8
    zhihu monitor 78170682 -o ./data
    zhihu query "深度学习" -l 20
================================================================================
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from random import uniform
import asyncio
import json
import sys
import typer
from rich import print as rprint
from rich.console import Console
from rich.text import Text

from cli.healthcheck import render_environment_check
from cli.launcher_flow import LauncherCommands, LauncherRuntime, run_launcher, run_onboard_flow
from cli.manual_content import build_manual_text
from cli.optional_deps import get_questionary as _get_questionary
from core.config import get_config, get_logger, get_humanizer, resolve_project_path
from core.utils import sanitize_filename, extract_urls
from core.scraper import ZhihuDownloader, ZhihuCreatorDownloader
from core.converter import ZhihuConverter
from core.errors import handle_error

# ============================================================
# CLI Application Initialization (CLI 应用初始化)
# ============================================================

app = typer.Typer(
    name="zhihu",
    help="🕷️ Zhihu High-Quality Content Scraper / 知乎高质量内容爬取工具",
    add_completion=False,
    no_args_is_help=False,
)

# Runtime defaults must stay side-effect free at import time.
# 运行时默认值不能在 import 阶段触发配置加载或 Cookie 读取。
DEFAULT_OUTPUT_DIR = Path("data")
DEFAULT_BROWSER_HEADLESS = True
console = Console()


# ============================================================
# Utility Functions (工具函数)
# ============================================================

# Note: sanitize_filename and extract_urls are now imported from core.utils
# to avoid code duplication across CLI and interactive modules.

def _get_cfg():
    """Load runtime config lazily / 延迟加载运行时配置"""
    return get_config()


def _get_log():
    """Get configured logger lazily / 延迟获取已配置日志器"""
    _get_cfg()
    return get_logger()


def _get_default_output_dir() -> Path:
    """Resolve output dir from runtime config / 从运行时配置解析输出目录"""
    return resolve_project_path(_get_cfg().output.directory)


def _get_default_browser_headless() -> bool:
    """Resolve browser headless flag from runtime config / 从运行时配置解析无头模式"""
    return _get_cfg().zhihu.browser.headless


def _resolve_output_dir(output: Optional[Path]) -> Path:
    """Resolve CLI output option with runtime fallback / 解析 CLI 输出目录并回落到运行时配置"""
    return output if output is not None else _get_default_output_dir()


def _resolve_headless(headless: Optional[bool]) -> bool:
    """Resolve CLI headless option with runtime fallback / 解析 CLI 无头参数并回落到运行时配置"""
    return _get_default_browser_headless() if headless is None else headless


def print_result(
    title: str,
    author: str,
    success: bool,
    path: str = "",
    error: Optional[str] = None
) -> None:
    """
    Print single result / 打印单条结果
    """
    if success:
        rprint(f"✅ [bold cyan]{author}[/] - [white]{title[:30]}...[/]")
        rprint(f"   📁 {path}")
    else:
        rprint(f"❌ [bold cyan]{author}[/] - [yellow]{title[:30]}...[/]")
        rprint(f"   💥 {error}")


def build_output_folder_name(item_date: str, title: str, author: str, item_key: str) -> str:
    """
    Render output directory name from config template and append a stable unique suffix.
    根据配置模板生成输出目录名，并附加稳定唯一后缀。
    """
    cfg = _get_cfg()
    folder_template = cfg.output.folder_format or "[{date}] {title}"
    try:
        rendered = folder_template.format(date=item_date, title=title, author=author)
    except KeyError:
        rendered = f"[{item_date}] {title}"

    rendered = sanitize_filename(rendered, max_length=100, shell_safe=True)
    safe_item_key = sanitize_filename(item_key, max_length=80, shell_safe=True)
    return f"{rendered}--{safe_item_key}"


def resolve_entries_output_dir(base_dir: Path) -> Path:
    """
    Resolve the content root for normal fetch/batch/monitor outputs.
    解析普通抓取输出的内容根目录。
    """
    if base_dir.name == "entries":
        return base_dir
    return base_dir / "entries"


def resolve_creator_output_dir(base_dir: Path, url_token: str) -> Path:
    """
    Resolve the content root for creator outputs.
    解析作者模式输出的内容根目录。
    """
    safe_token = sanitize_filename(url_token, max_length=80)
    return base_dir / "creators" / safe_token


def print_question_limit_warning(limit: int) -> None:
    """
    Print risk warning for large question-page fetches.
    对大数量问题页抓取打印风险提示。
    """
    if limit > 50:
        rprint("[bold yellow]⚠️ Large batch detected / 大批量抓取提示[/bold yellow]")
        rprint("   请求超过 50 条回答时，会触发多页连续请求，触发风控的概率会明显上升。")
        rprint("   Requests above 50 answers increase anti-bot risk due to multi-page API access.")
    elif limit > 20:
        rprint("[yellow]⚠️ Multi-page fetch enabled / 已启用多页抓取[/yellow]")
        rprint("   超过 20 条回答会进入分页抓取，并在页间自动插入随机等待。")
        rprint("   Requests over 20 answers will use pagination with random waits between pages.")


def print_creator_limit_warning(answers: int, articles: int) -> None:
    """
    Print warning when creator mode will trigger multi-page requests.
    当 creator 模式会触发多页请求时打印提示。
    """
    if answers > 20 or articles > 20:
        rprint("[yellow]⚠️ Creator mode will use pagination / 作者模式将启用分页抓取[/yellow]")
        rprint("   大于 20 条时会进行多页 API 请求，并自动加入随机等待。")
        rprint("   Requests above 20 items use paginated API access with built-in random delays.")


def _build_launcher_runtime() -> LauncherRuntime:
    return LauncherRuntime(
        console=console,
        get_cfg=_get_cfg,
        get_questionary=_get_questionary,
        get_default_output_dir=_get_default_output_dir,
        get_default_browser_headless=_get_default_browser_headless,
        resolve_project_path=resolve_project_path,
        commands=LauncherCommands(
            fetch=fetch,
            creator=creator,
            batch=batch,
            monitor=monitor,
            query=query_db,
            interactive=interactive,
            check=check,
            manual=manual,
        ),
    )


def _run_onboard_flow(*, from_command: bool = False) -> None:
    run_onboard_flow(_build_launcher_runtime(), from_command=from_command)


def _run_launcher() -> None:
    run_launcher(_build_launcher_runtime())


# ============================================================
# Command Definitions (命令定义)
# ============================================================

@app.command("manual")
def manual() -> None:
    """
    Show the built-in terminal manual with paging support.
    显示内置终端说明书，支持分页查看。
    """
    default_output_dir = _get_default_output_dir()
    manual_text = build_manual_text(default_output_dir)

    with console.pager(styles=True):
        console.print(Text(manual_text, justify="left"))


@app.command("onboard")
def onboard() -> None:
    """
    Guided first-run onboarding.
    首次使用引导。
    """
    _run_onboard_flow(from_command=True)


@app.command("fetch")
def fetch(
    url: str = typer.Argument(..., help="Zhihu link(s) (article/answer/question) / 知乎链接（支持多条，含混杂文本）"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output directory / 输出目录"),
    limit: Optional[int] = typer.Option(None, "-n", "--limit", help="Limit answer count (question pages only) / 限制回答数量 (仅限问题页)"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="Don't download images / 不下载图片"),
    headless: Optional[bool] = typer.Option(None, "-b", "--headless/--no-headless", help="Run browser in headless mode / 无头模式运行浏览器"),
) -> None:
    """
    Scrape one or more Zhihu links. Automatically extracts URLs from text.
    抓取一个或多个知乎链接。支持从混杂文本中自动提取。

    Supported link types:
    - Column article: https://zhuanlan.zhihu.com/p/123456
    - Single answer: https://www.zhihu.com/question/123/answer/456
    - Question page (batch): https://www.zhihu.com/question/123

    Examples:
    zhihu fetch "https://www.zhihu.com/p/123456"
    zhihu fetch "Text containing https://www.zhihu.com/p/123 https://www.zhihu.com/p/456"
    zhihu fetch "https://www.zhihu.com/question/123456" -n 10
    """
    cfg = _get_cfg()
    log = _get_log()
    output_dir = _resolve_output_dir(output)
    headless_mode = _resolve_headless(headless)

    urls = extract_urls(url)
    if not urls:
        rprint("[red]❌ No valid Zhihu links found in input / 未在输入中找到有效链接[/red]")
        raise SystemExit(1)

    if limit is not None and limit < 1:
        raise typer.BadParameter("Question-page limit must be at least 1 / 问题页抓取数量至少为 1")

    rprint(f"🔍 Found {len(urls)} link(s) / 识别到 {len(urls)} 个链接")
    log.info("fetch_started", count=len(urls), limit=limit)

    try:
        # Check login once / 统一检测一次 Cookie
        from core.api_client import ZhihuAPIClient
        temp_client = ZhihuAPIClient()
        if not temp_client._cookies_dict and cfg.zhihu.cookies_required:
            rprint("[yellow]⚠️  No valid Cookie detected, will use guest mode / 未检测到有效 Cookie，将使用游客模式[/yellow]")

        for i, target_url in enumerate(urls):
            if len(urls) > 1:
                rprint(f"\n[bold green]🚀 Task {i+1}/{len(urls)}:[/] {target_url}")

            # Prepare scraping configuration / 准备抓取配置
            scrape_config = {}
            if limit and "/question/" in target_url and "/answer/" not in target_url:
                print_question_limit_warning(limit)
                scrape_config = {"start": 0, "limit": limit}

            # Execute scraping / 执行抓取
            asyncio.run(_fetch_and_save(
                url=target_url,
                output_dir=output_dir,
                scrape_config=scrape_config,
                download_images=not no_images,
                headless=headless_mode
            ))

    except Exception as e:
        handle_error(e, log)
        raise SystemExit(1)


@app.command("batch")
def batch(
    input_file: Path = typer.Argument(..., help="URL list file (one link per line) / URL列表文件 (每行一个链接)"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output directory / 输出目录"),
    concurrency: int = typer.Option(4, "-c", "--concurrency", help="Concurrency count (recommend 4-8) / 并发数 (建议 4-8)"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="Don't download images / 不下载图片"),
    headless: Optional[bool] = typer.Option(None, "-b", "--headless/--no-headless", help="Run browser in headless mode / 无头模式运行浏览器"),
) -> None:
    """
    Batch scrape multiple Zhihu links.
    批量抓取多个知乎链接。

    Reads URL list from file and executes scraping tasks concurrently.
    从文件中读取 URL 列表，并发执行抓取任务。

    Examples:
        zhihu batch ./urls.txt
        zhihu batch ./urls.txt -c 8 -o ./output
    """
    log = _get_log()
    output_dir = _resolve_output_dir(output)
    headless_mode = _resolve_headless(headless)

    if not input_file.exists():
        rprint(f"[red]❌ File not found / 文件不存在: {input_file}[/red]")
        raise SystemExit(1)

    urls = extract_urls(input_file.read_text())
    if not urls:
        rprint("[red]❌ No valid links found / 未找到有效链接[/red]")
        raise SystemExit(1)

    # Limit concurrency to avoid triggering anti-crawling / 限制并发数，避免触发反爬
    max_concurrency = min(concurrency, len(urls), 8)
    log.info("batch_started", file=str(input_file), count=len(urls), concurrency=max_concurrency)
    rprint(f"[bold]📋 Batch task / 批量任务: {len(urls)} links (concurrency / 并发: {max_concurrency})[/bold]")

    # Execute concurrently / 并发执行
    results = asyncio.run(_batch_concurrent(
        urls=urls,
        output_dir=output_dir,
        concurrency=max_concurrency,
        download_images=not no_images,
        headless=headless_mode
    ))

    # Statistics / 统计结果
    success = sum(1 for r in results if r["success"])
    failed = len(results) - success

    rprint(f"\n[bold]📊 Batch completed / 批量完成: {success} success / 成功, {failed} failed / 失败[/bold]")
    log.info("batch_completed", success=success, failed=failed)


@app.command("creator")
def creator(
    creator: str = typer.Argument(..., help="Zhihu creator profile URL or token / 知乎用户主页 URL 或 token"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output directory / 输出目录"),
    answers: int = typer.Option(10, "--answers", help="Maximum number of answers / 最大回答数量"),
    articles: int = typer.Option(5, "--articles", help="Maximum number of articles / 最大专栏数量"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="Don't download images / 不下载图片"),
) -> None:
    """
    Scrape answers and articles from a Zhihu creator profile.
    抓取知乎作者主页下的回答和专栏文章。

    Examples:
        zhihu creator https://www.zhihu.com/people/hu-xi-jin
        zhihu creator hu-xi-jin --answers 20 --articles 10
    """
    cfg = _get_cfg()
    log = _get_log()
    output_dir = _resolve_output_dir(output)

    if answers < 0 or articles < 0:
        raise typer.BadParameter("Creator limits must be 0 or greater / 作者抓取数量必须大于等于 0")
    if answers == 0 and articles == 0:
        raise typer.BadParameter("At least one content type must be enabled / 至少抓取一种内容类型")

    log.info("creator_started", creator=creator, answers=answers, articles=articles)
    rprint(f"[bold]👤 Creator mode / 作者模式: {creator}[/bold]")

    try:
        from core.api_client import ZhihuAPIClient

        temp_client = ZhihuAPIClient()
        if not temp_client._cookies_dict and cfg.zhihu.cookies_required:
            rprint("[yellow]⚠️  No valid Cookie detected, creator mode may be incomplete / 未检测到有效 Cookie，作者模式可能不完整[/yellow]")

        print_creator_limit_warning(answers, articles)

        asyncio.run(_fetch_creator_and_save(
            creator=creator,
            output_dir=output_dir,
            answer_limit=answers,
            article_limit=articles,
            download_images=not no_images,
        ))
    except Exception as e:
        handle_error(e, log)
        raise SystemExit(1)


@app.command("monitor")
def monitor(
    collection_id: str = typer.Argument(..., help="Zhihu collection ID (e.g., 78170682) / 知乎收藏夹ID (如 78170682)"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output directory / 输出目录"),
    concurrency: int = typer.Option(4, "-c", "--concurrency", help="Concurrency count / 并发数"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="Don't download images / 不下载图片"),
    headless: Optional[bool] = typer.Option(None, "-b", "--headless/--no-headless", help="Headless mode / 无头模式"),
) -> None:
    """
    Incrementally monitor and scrape new content from Zhihu collections.
    增量监控并抓取知乎收藏夹的新增内容。

    Features:
    - Check new content in collection (since last monitor)
    - Auto deduplicate, skip already scraped content
    - Download new content and save locally
    - Update state file, record latest progress

    功能说明：
    - 检查收藏夹中新增的内容（自上次监控以来）
    - 自动去重，跳过已抓取的内容
    - 下载新增内容并保存到本地
    - 更新状态文件，记录最新进度

    Examples:
        zhihu monitor 78170682                    # Monitor with default config / 监控默认配置
        zhihu monitor 78170682 -o ./data         # Specify output directory / 指定输出目录
        zhihu monitor 78170682 -c 8             # Increase concurrency / 提高并发数
    """
    log = _get_log()
    output_dir = _resolve_output_dir(output)
    headless_mode = _resolve_headless(headless)

    log.info("monitor_started", collection_id=collection_id)
    rprint(f"[bold]📡 Starting incremental monitoring / 启动增量监控: Collection / 收藏夹 {collection_id}[/bold]")

    from core.monitor import CollectionMonitor
    m = CollectionMonitor(data_dir=str(output_dir))

    try:
        new_items, new_last_id = m.get_new_items(collection_id)
    except Exception as e:
        handle_error(e, log)
        raise SystemExit(1)

    if not new_items:
        rprint("[green]✨ No new content in collection, monitoring ends / 收藏夹没有新增内容，监控结束。[/green]")
        return

    rprint(f"\n[bold]🛒 Preparing to download {len(new_items)} new items... / 准备下载 {len(new_items)} 个新内容...[/bold]")

    urls = [item["url"] for item in new_items]
    max_concurrency = min(concurrency, len(urls), 8)

    results = asyncio.run(_batch_concurrent(
        urls=urls,
        output_dir=output_dir,
        concurrency=max_concurrency,
        download_images=not no_images,
        headless=headless_mode,
        collection_id=collection_id
    ))

    success = sum(1 for r in results if r["success"])
    failed = len(results) - success

    rprint(f"\n[bold]📊 Monitor download completed / 监控下载完成: {success} success / 成功, {failed} failed / 失败[/bold]")

    if failed == 0 and success > 0:
        m.mark_updated(collection_id, new_last_id)
        rprint(f"[cyan]✅ Saved latest progress pointer / 已保存最新进度指针: {new_last_id}[/cyan]")
    elif failed > 0:
        rprint("[yellow]⚠️ Partial failures detected, monitoring pointer was not advanced / 存在失败项，本次不会推进监控游标，避免漏抓。[/yellow]")


@app.command("query")
def query_db(
    keyword: str = typer.Argument(..., help="Keyword to search / 要搜索的关键词"),
    limit: int = typer.Option(10, "-l", "--limit", help="Maximum number of results / 最大显示结果数量"),
    data_dir: Optional[str] = typer.Option(None, "-d", "--data-dir", help="Data directory / 数据目录"),
) -> None:
    """
    Search scraped Zhihu content in local SQLite database.
    在本地 SQLite 数据库中检索已抓取的知乎内容。

    Database structure:
    - Table: articles
    - Fields: answer_id, type, title, author, url, content_md, collection_id, created_at, updated_at

    Examples:
        zhihu query "深度学习"              # Search title and content / 搜索标题和内容
        zhihu query "Transformer" -l 20     # Limit results / 限制结果数量
        zhihu query "LLM" -d ./custom_data  # Specify data directory / 指定数据目录
    """
    resolved_data_dir = data_dir or str(_get_default_output_dir())
    from core.db import ZhihuDatabase
    from rich.table import Table

    db_path = Path(resolved_data_dir) / "zhihu.db"
    if not db_path.exists():
        rprint("[red]❌ Zhihu database not found. Please run fetch or monitor first / 未找到知乎数据库，请先执行抓取任务 (fetch 或 monitor)。[/red]")
        raise SystemExit(1)

    db = ZhihuDatabase(str(db_path))
    results = db.search_articles(keyword, limit)
    db.close()

    if not results:
        rprint(f"[yellow]⚠️ No articles found containing '[bold]{keyword}[/bold]' / 未找到包含关键词 '[bold]{keyword}[/bold]' 的文章。[/yellow]")
        return

    table = Table(title=f"🔍 Search Results / 检索结果: '{keyword}' (first / 前 {len(results)} items)")
    table.add_column("Type", justify="center", style="cyan")
    table.add_column("Author", style="green")
    table.add_column("Title", style="magenta", overflow="fold")
    table.add_column("Captured At", style="dim")
    table.add_column("Zhihu ID", justify="right", style="blue")

    for row in results:
        table.add_row(
            row["type"],
            row["author"],
            row["title"],
            row["created_at"].split("T")[0],
            row["answer_id"]
        )

    rprint(table)


@app.command("interactive")
def interactive(
    legacy: bool = typer.Option(
        False,
        "--legacy",
        help="Deprecated fallback to the legacy Rich/questionary workflow / 已弃用的旧版 Rich/questionary 回退流程",
    ),
) -> None:
    """
    Launch the interactive archive workspace.
    启动交互式归档工作台。

    Features:
    - Full-screen archive workbench with in-app URL input
    - Responsive centered layout, question-page limit modal, queue, recent results, and retry flow
    - Deprecated legacy fallback for regression checks only

    功能：
    - 内置链接输入栏的全屏归档工作台
    - 响应式居中布局、问题页数量弹层、队列、最近结果与失败重试
    - 仅用于回归检查的旧版回退入口

    Example:
        zhihu interactive
        zhihu interactive --legacy
    """
    log = _get_log()
    try:
        if legacy:
            from cli.interactive_legacy import run_interactive as run_legacy_interactive

            asyncio.run(run_legacy_interactive())
        else:
            from cli.interactive import run_interactive

            run_interactive()
    except Exception as e:
        handle_error(e, log)


@app.command("config")
def config_cmd(
    show: bool = typer.Option(False, "--show", help="Show current configuration / 显示当前配置"),
    path: bool = typer.Option(False, "--path", help="Show configuration file path / 显示配置文件路径"),
) -> None:
    """
    View or manage configuration.
    查看或管理配置。

    Examples:
        zhihu config --show    # Show current config / 显示当前配置
        zhihu config --path    # Show config file path / 显示配置文件路径
    """
    if path:
        from pathlib import Path as P
        config_path = P(__file__).parent.parent / "config.yaml"
        rprint(f"📄 Configuration file / 配置文件: [cyan]{config_path}[/]")
        raise SystemExit(0)

    if show:
        cfg = _get_cfg()
        from core.cookie_manager import resolve_cookie_file_path, resolve_cookie_pool_dir

        configured_cookie_path = resolve_project_path(cfg.zhihu.cookies_file)
        active_cookie_path = resolve_cookie_file_path(cfg.zhihu.cookies_file)
        active_pool_dir = resolve_cookie_pool_dir(cfg.zhihu.cookies_pool_dir)
        log_path = resolve_project_path(cfg.logging.file) if cfg.logging.file else "disabled / 已关闭"
        rprint(Panel(
            Text(f"""
[b]配置路径 (Config Path):[/] {Path(__file__).parent.parent / "config.yaml"}

[b]输出目录 (Output Directory):[/] {cfg.output.directory}
[b]Cookie文件 (Cookie File):[/] {configured_cookie_path}
[b]当前生效Cookie (Active Cookie):[/] {active_cookie_path}
[b]Cookie池目录 (Cookie Pool):[/] {active_pool_dir}
[b]日志文件 (Log File):[/] {log_path}
[b]日志级别 (Log Level):[/] {cfg.logging.level}
[b]浏览器 (Browser):[/] {"Headless / 无头" if cfg.zhihu.browser.headless else "Visible / 有头"}
[b]重试次数 (Retry Attempts):[/] {cfg.crawler.retry.max_attempts}
[b]图片并发 (Image Concurrency):[/] {cfg.crawler.images.concurrency}
[b]Cookie轮换 (Cookie Rotation):[/] {"Enabled / 启用" if hasattr(cfg, 'zhihu') and cfg.zhihu.cookies_required else "Disabled / 禁用"}
            """.strip(), justify="left"),
            title="🛠️ Current Configuration / 当前配置",
            border_style="cyan"
        ))


@app.command("check")
def check() -> None:
    """
    Check environment dependencies and configuration.
    检查环境依赖和配置是否正常。

    Checks:
    1. config.yaml exists
    2. configured cookie file valid
    3. Playwright browser available
    """
    render_environment_check()


# ============================================================
# Internal Helpers (内部助手)
# ============================================================


async def _batch_concurrent(
    urls: List[str],
    output_dir: Path,
    concurrency: int,
    download_images: bool,
    headless: bool,
    collection_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Core implementation of concurrent batch scraping.
    并发批量抓取核心实现。

    Anti-crawling strategies:
    - Use semaphore to limit maximum concurrency
    - Random delay between tasks (0.5~6 seconds)

    防风控策略：
    - 使用信号量限制最大并发数
    - 任务间随机延迟 (0.5~6秒)

    Args:
        urls: URL list / URL 列表
        output_dir: Output directory / 输出目录
        concurrency: Concurrency count / 并发数
        download_images: Whether to download images / 是否下载图片
        headless: Headless mode / 无头模式
        collection_id: Collection ID (for database association) / 收藏夹 ID (用于关联数据库记录)

    Returns:
        Result list with success, url, etc. fields / 结果列表，每个元素包含 success, url 等字段
    """
    semaphore = asyncio.Semaphore(concurrency)
    humanizer = get_humanizer()
    log = _get_log()

    async def fetch_one(url: str, index: int) -> Dict[str, Any]:
        async with semaphore:
            # Random delay between tasks to avoid triggering anti-crawling
            # 任务间随机延迟，避免触发反爬
            # Delay increases with task index to reduce simultaneous requests probability
            # 延迟时间随任务序号递增，降低同时发起的概率
            if index > 0:
                delay = uniform(0.5, 2.0) * (index % 3 + 1)
                await asyncio.sleep(delay)

            try:
                await _fetch_and_save(
                    url=url,
                    output_dir=output_dir,
                    scrape_config={},
                    download_images=download_images,
                    headless=headless,
                    collection_id=collection_id
                )
                return {"url": url, "success": True}
            except Exception as e:
                handle_error(e, log)
                return {"url": url, "success": False, "error": str(e)}

    # Create all tasks / 创建所有任务
    tasks = [fetch_one(url, i) for i, url in enumerate(urls)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Clean up results / 清理结果
    cleaned = []
    for r in results:
        if isinstance(r, dict):
            cleaned.append(r)
        else:
            cleaned.append({"url": "unknown", "success": False})

    return cleaned


async def _fetch_and_save(
    url: str,
    output_dir: Path,
    scrape_config: dict,
    download_images: bool = True,
    headless: bool = True,
    collection_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Execute scraping and save to local files and database.
    执行抓取并保存到本地文件和数据库。

    Complete workflow:
    1. Use ZhihuDownloader to scrape page data
    2. Extract image URLs and download to images/ directory
    3. Use ZhihuConverter to convert HTML to Markdown
    4. Save as index.md file
    5. Save to SQLite database

    完整执行流程：
    1. 使用 ZhihuDownloader 抓取页面数据
    2. 提取图片 URL 并下载到 images/ 目录
    3. 使用 ZhihuConverter 将 HTML 转换为 Markdown
    4. 保存为 index.md 文件
    5. 保存到 SQLite 数据库

    Args:
        url: Zhihu link / 知乎链接
        output_dir: Output directory / 输出目录
        scrape_config: Scraping config (like limit, start) / 抓取配置 (如 limit, start)
        download_images: Whether to download images / 是否下载图片
        headless: Headless mode (not effective in API mode) / 无头模式 (API 模式下不生效)
        collection_id: Collection ID (for database record association) / 收藏夹 ID (关联数据库记录)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    downloader = ZhihuDownloader(url)
    fetch_kwargs = dict(scrape_config)
    fetch_kwargs["headless"] = headless
    data = await downloader.fetch_page(**fetch_kwargs)

    if not data:
        rprint("[yellow]⚠️  No content obtained / 未获取到内容[/yellow]")
        return []

    items = data if isinstance(data, list) else [data]
    return await _save_items(
        items=items,
        content_root=resolve_entries_output_dir(output_dir),
        db_root=output_dir,
        download_images=download_images,
        source_url_fallback=url,
        collection_id=collection_id,
    )


async def _fetch_creator_and_save(
    creator: str,
    output_dir: Path,
    answer_limit: int,
    article_limit: int,
    download_images: bool = True,
) -> None:
    """
    Fetch creator content and save it using the standard local output pipeline.
    抓取作者内容，并复用标准本地输出流程保存。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    downloader = ZhihuCreatorDownloader(creator)
    result = await downloader.fetch_items(answer_limit=answer_limit, article_limit=article_limit)
    creator_info = result.get("creator", {})
    items = result.get("items", [])
    sync_info = result.get("sync", {})

    if not items:
        rprint("[yellow]⚠️  No creator content obtained / 未获取到作者内容[/yellow]")
        return

    creator_name = creator_info.get("name", creator_info.get("url_token", creator))
    rprint(f"[cyan]👤 Creator / 作者[/cyan]: {creator_name} ({creator_info.get('url_token', 'unknown')})")
    if creator_info.get("follower_count") or creator_info.get("following_count"):
        rprint(
            f"   👥 Followers / 粉丝: {creator_info.get('follower_count', 0)}"
            f" | Following / 关注: {creator_info.get('following_count', 0)}"
        )

    creator_root = resolve_creator_output_dir(output_dir, creator_info.get("url_token", creator))

    saved_records = await _save_items(
        items=items,
        content_root=creator_root,
        db_root=output_dir,
        download_images=download_images,
        source_url_fallback=f"https://www.zhihu.com/people/{creator_info.get('url_token', creator)}",
    )

    _write_creator_metadata(creator_root, creator_info, saved_records, sync_info)


async def _save_items(
    *,
    items: List[Dict[str, Any]],
    content_root: Path,
    db_root: Path,
    download_images: bool,
    source_url_fallback: str,
    collection_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Save normalized content items to Markdown, images, and SQLite.
    将标准化内容保存到 Markdown、图片目录和 SQLite。
    """
    from datetime import datetime

    cfg = _get_cfg()
    content_root.mkdir(parents=True, exist_ok=True)

    image_cfg = cfg.crawler.images
    images_subdir = cfg.output.images_subdir or "images"
    today = datetime.now().strftime("%Y-%m-%d")

    from core.db import ZhihuDatabase

    db = ZhihuDatabase(str(db_root / "zhihu.db"))
    saved_records: List[Dict[str, Any]] = []
    try:
        for item in items:
            title = sanitize_filename(item["title"])
            author = sanitize_filename(item["author"])
            item_date = item.get("date") or today
            source_url = item.get("url") or source_url_fallback
            item_key = sanitize_filename(f"{item.get('type', 'item')}-{item.get('id', 'unknown')}", max_length=80)

            folder_name = build_output_folder_name(item_date, title, author, item_key)
            folder = content_root / folder_name
            folder.mkdir(parents=True, exist_ok=True)

            # Download images / 下载图片
            img_map = {}
            if download_images:
                img_urls = ZhihuConverter.extract_image_urls(item["html"])
                if img_urls:
                    rprint(f"   📥 Downloading {len(img_urls)} images... / 下载 {len(img_urls)} 张图片...")
                    img_map = await ZhihuDownloader.download_images(
                        img_urls,
                        folder / images_subdir,
                        concurrency=image_cfg.concurrency,
                        timeout=image_cfg.timeout,
                        relative_prefix=images_subdir,
                    )

            # Convert and save Markdown / 转换并保存 Markdown
            converter = ZhihuConverter(img_map=img_map)
            md = converter.convert(item["html"])

            header = (
                f"# {item['title']}\n\n"
                f"> **Author / 作者**: {item['author']}  \n"
                f"> **Source / 来源**: [{source_url}]({source_url})  \n"
                f"> **Date / 日期**: {item_date}\n\n"
                "---\n\n"
            )

            out_path = folder / "index.md"
            full_md = header + md
            out_path.write_text(full_md, encoding="utf-8")

            db.save_article(item, full_md, collection_id=collection_id)
            saved_records.append({
                "item": item,
                "folder": folder,
                "markdown_path": out_path,
            })

            rprint(f"✅ Saved / 保存: [cyan]{author}[/] - {title[:25]}...")
            rprint(f"   📁 {out_path} & DB / 入库 DB")
    finally:
        db.close()

    return saved_records


def _write_creator_metadata(
    creator_root: Path,
    creator_info: Dict[str, Any],
    saved_records: List[Dict[str, Any]],
    sync_info: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write creator metadata files under the creator directory.
    在作者目录下写入元信息文件。
    """
    from datetime import datetime

    fetched_at = datetime.now().isoformat(timespec="seconds")
    answer_records = [record for record in saved_records if record["item"].get("type") == "answer"]
    article_records = [record for record in saved_records if record["item"].get("type") == "article"]
    sync_info = sync_info or {}
    answer_sync = sync_info.get("answers", {})
    article_sync = sync_info.get("articles", {})
    recent_records = sorted(
        saved_records,
        key=lambda record: record["item"].get("date", ""),
        reverse=True,
    )[:5]

    creator_payload = {
        "user_id": creator_info.get("user_id", ""),
        "name": creator_info.get("name", creator_info.get("url_token", "unknown")),
        "url_token": creator_info.get("url_token", "unknown"),
        "profile_url": creator_info.get("profile_url", f"https://www.zhihu.com/people/{creator_info.get('url_token', 'unknown')}"),
        "avatar_url": creator_info.get("avatar_url", ""),
        "headline": creator_info.get("headline", ""),
        "description": creator_info.get("description", ""),
        "follower_count": creator_info.get("follower_count", 0),
        "following_count": creator_info.get("following_count", 0),
        "voteup_count": creator_info.get("voteup_count", 0),
        "answer_count": creator_info.get("answer_count", 0),
        "articles_count": creator_info.get("articles_count", 0),
        "question_count": creator_info.get("question_count", 0),
        "video_count": creator_info.get("video_count", 0),
        "column_count": creator_info.get("column_count", 0),
        "fetched_at": fetched_at,
        "last_sync_at": fetched_at,
        "saved_answers": len(answer_records),
        "saved_articles": len(article_records),
        "local_root": str(creator_root),
        "sync": {
            "answers": answer_sync,
            "articles": article_sync,
        },
        "recent_items": [
            {
                "id": record["item"].get("id", ""),
                "type": record["item"].get("type", ""),
                "title": record["item"].get("title", ""),
                "date": record["item"].get("date", ""),
                "markdown_path": str(record["markdown_path"].relative_to(creator_root)),
            }
            for record in recent_records
        ],
        "items": [
            {
                "id": record["item"].get("id", ""),
                "type": record["item"].get("type", ""),
                "title": record["item"].get("title", ""),
                "date": record["item"].get("date", ""),
                "url": record["item"].get("url", ""),
                "markdown_path": str(record["markdown_path"].relative_to(creator_root)),
            }
            for record in saved_records
        ],
    }

    creator_json_path = creator_root / "creator.json"
    creator_json_path.write_text(
        json.dumps(creator_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        f"# {creator_payload['name']}",
        "",
        f"> **User ID**: `{creator_payload['user_id'] or 'unknown'}`  ",
        f"> **URL Token**: `{creator_payload['url_token']}`  ",
        f"> **Zhihu Profile / 作者主页**: [{creator_payload['profile_url']}]({creator_payload['profile_url']})  ",
        f"> **Fetched At / 抓取时间**: {creator_payload['fetched_at']}  ",
        f"> **Last Sync / 最近同步**: {creator_payload['last_sync_at']}",
        "",
    ]

    if creator_payload["avatar_url"]:
        lines.extend([
            f"> **Avatar / 头像**: {creator_payload['avatar_url']}",
            "",
        ])

    if creator_payload["headline"]:
        lines.extend([
            f"> **Headline / 简介**: {creator_payload['headline']}",
            "",
        ])

    if creator_payload["description"] and creator_payload["description"] != creator_payload["headline"]:
        lines.extend([
            f"> **Description / 描述**: {creator_payload['description']}",
            "",
        ])

    lines.extend([
        "## Summary / 概览",
        "",
        f"- Followers / 粉丝: {creator_payload['follower_count']}",
        f"- Following / 关注: {creator_payload['following_count']}",
        f"- Total upvotes / 总获赞: {creator_payload['voteup_count']}",
        f"- Zhihu answers / 知乎回答数: {creator_payload['answer_count']}",
        f"- Zhihu articles / 知乎专栏数: {creator_payload['articles_count']}",
        f"- Zhihu questions / 提问数: {creator_payload['question_count']}",
        f"- Zhihu videos / 视频数: {creator_payload['video_count']}",
        f"- Zhihu columns / 专栏数: {creator_payload['column_count']}",
        f"- Saved answers / 已保存回答: {creator_payload['saved_answers']}",
        f"- Saved articles / 已保存专栏: {creator_payload['saved_articles']}",
        f"- Local root / 本地目录: `{creator_payload['local_root']}`",
        "",
        "## Sync Status / 同步状态",
        "",
        f"- Answers: requested {answer_sync.get('requested_limit', 0)}, saved {answer_sync.get('saved_count', 0)}, pages {answer_sync.get('pages_fetched', 0)}, last_offset {answer_sync.get('last_offset', 0)}, reached_end {answer_sync.get('reached_end', False)}, stopped_early {answer_sync.get('stopped_early', False)}",
        f"- Articles: requested {article_sync.get('requested_limit', 0)}, saved {article_sync.get('saved_count', 0)}, pages {article_sync.get('pages_fetched', 0)}, last_offset {article_sync.get('last_offset', 0)}, reached_end {article_sync.get('reached_end', False)}, stopped_early {article_sync.get('stopped_early', False)}",
        "",
        "## Recent Items / 最近内容",
        "",
    ])

    if creator_payload["recent_items"]:
        lines.extend([
            "| Type | Title | Date | Markdown |",
            "|---|---|---|---|",
        ])
        for item in creator_payload["recent_items"]:
            escaped_title = item["title"].replace("|", "\\|")
            lines.append(
                f"| {item['type']} | {escaped_title} | {item['date']} | "
                f"[index.md]({item['markdown_path']}) |"
            )
        lines.append("")

    lines.extend([
        "## Items / 内容列表",
        "",
    ])

    for section_title, records in (
        ("### Answers / 回答", answer_records),
        ("### Articles / 专栏", article_records),
    ):
        lines.extend([section_title, ""])
        if not records:
            lines.extend(["- None / 暂无", ""])
            continue

        lines.extend([
            "| Title | Date | Markdown | Source |",
            "|---|---|---|---|",
        ])
        for record in records:
            item = record["item"]
            title = item.get("title", "").replace("|", "\\|")
            item_date = item.get("date", "")
            markdown_rel = record["markdown_path"].relative_to(creator_root)
            source_url = item.get("url", "")
            lines.append(
                f"| {title} | {item_date} | "
                f"[index.md]({markdown_rel.as_posix()}) | [source]({source_url}) |"
            )
        lines.append("")

    creator_readme_path = creator_root / "README.md"
    creator_readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ============================================================
# Entry Point (入口点)
# ============================================================

def main() -> None:
    """CLI entry point / CLI 入口"""
    if len(sys.argv) == 1:
        _run_launcher()
        return
    app()


if __name__ == "__main__":
    main()
