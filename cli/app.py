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
from typing import Optional
import asyncio
import sys
import typer
from rich import print as rprint
from rich.console import Console
from rich.text import Text

from cli.archive_execution import get_workflow_service
from cli.config_view import build_config_snapshot, render_config_panel
from cli.healthcheck import render_environment_check
from cli.launcher_flow import LauncherCommands, LauncherRuntime, run_launcher, run_onboard_flow
from cli.manual_content import build_manual_text
from cli.optional_deps import get_questionary as _get_questionary
from core.config import get_config, get_logger, resolve_project_path
from core.utils import extract_urls
from core.errors import handle_error

# ============================================================
# CLI Application Initialization (CLI 应用初始化)
# ============================================================

app = typer.Typer(
    name="zhihu",
    help=(
        "🕷️ Local-first Zhihu archiver / 本地优先的知乎归档工具. "
        "Run without arguments to launch the interactive workspace / 无参数时直接启动交互式归档工作台。"
    ),
    add_completion=False,
    no_args_is_help=False,
)

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


def _get_workflow_service():
    return get_workflow_service(printer=rprint, logger=_get_log())


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

        if limit:
            for target_url in urls:
                if "/question/" in target_url and "/answer/" not in target_url:
                    print_question_limit_warning(limit)

        result = asyncio.run(
            _get_workflow_service().run_fetch_urls(
                urls=urls,
                output_dir=output_dir,
                limit=limit,
                download_images=not no_images,
                headless=headless_mode,
                stop_on_error=True,
            )
        )
        if result.has_failures:
            raise SystemExit(1)

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
    results = asyncio.run(
        _get_workflow_service().run_batch(
            urls=urls,
            output_dir=output_dir,
            concurrency=max_concurrency,
            download_images=not no_images,
            headless=headless_mode,
        )
    )

    # Statistics / 统计结果
    success = results.success_count
    failed = results.failed_count

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

        result = asyncio.run(
            _get_workflow_service().run_creator(
                creator=creator,
                output_dir=output_dir,
                answer_limit=answers,
                article_limit=articles,
                download_images=not no_images,
            )
        )
        if not result.success:
            raise SystemExit(1)
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

    try:
        result = asyncio.run(
            _get_workflow_service().run_monitor(
                collection_id=collection_id,
                output_dir=output_dir,
                concurrency=concurrency,
                download_images=not no_images,
                headless=headless_mode,
            )
        )
    except Exception as e:
        handle_error(e, log)
        raise SystemExit(1)

    if not result.has_new_activity:
        rprint("[green]✨ No new content in collection, monitoring ends / 收藏夹没有新增内容，监控结束。[/green]")
        return

    if not result.has_new_items:
        rprint(
            "[cyan]⏭️ Detected new collection activity, but no answer/article items were ready for archiving "
            f"/ 检测到收藏夹有新增动态，但没有可归档的回答或文章（跳过 {result.unsupported_count} 个不支持条目）。[/cyan]"
        )
        if result.pointer_advanced and result.next_pointer:
            rprint(f"[cyan]✅ Saved latest progress pointer / 已保存最新进度指针: {result.next_pointer}[/cyan]")
        return

    rprint(f"\n[bold]🛒 Preparing to download {result.discovered_count} new items... / 准备下载 {result.discovered_count} 个新内容...[/bold]")
    success = result.batch.success_count
    failed = result.batch.failed_count

    rprint(f"\n[bold]📊 Monitor download completed / 监控下载完成: {success} success / 成功, {failed} failed / 失败[/bold]")

    if result.pointer_advanced and result.next_pointer:
        rprint(f"[cyan]✅ Saved latest progress pointer / 已保存最新进度指针: {result.next_pointer}[/cyan]")
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
    - Fields: answer_id, content_key, type, title, author, url, content_md, collection_id, created_at, updated_at

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
    table.add_column("Content Key", style="blue")

    for row in results:
        table.add_row(
            row["type"],
            row["author"],
            row["title"],
            row["created_at"].split("T")[0],
            row["content_key"],
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
    - `zhihu` without arguments launches this TUI directly

    功能：
    - 内置链接输入栏的全屏归档工作台
    - 响应式居中布局、问题页数量弹层、队列、最近结果与失败重试
    - 仅用于回归检查的旧版回退入口
    - `zhihu` 无参数时直接启动此 TUI 工作台

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


config_app = typer.Typer(help="View or manage configuration. 查看或管理配置。")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show() -> None:
    """Show current configuration / 显示当前配置"""
    cfg = _get_cfg()
    from core.cookie_manager import describe_cookie_file_path, describe_cookie_pool_dir

    snapshot = build_config_snapshot(
        cfg=cfg,
        config_path=Path(__file__).parent.parent / "config.yaml",
        resolve_project_path=resolve_project_path,
        describe_cookie_file_path=describe_cookie_file_path,
        describe_cookie_pool_dir=describe_cookie_pool_dir,
    )
    rprint(render_config_panel(snapshot))


@config_app.command("path")
def config_path() -> None:
    """Show configuration file path / 显示配置文件路径"""
    from pathlib import Path as P
    config_path = P(__file__).parent.parent / "config.yaml"
    rprint(f"📄 Configuration file / 配置文件: [cyan]{config_path}[/]")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key to set (e.g., 'language') / 配置项名称"),
    value: str = typer.Argument(..., help="Value to set / 配置值"),
) -> None:
    """
    Set a configuration value. 目前仅支持语言切换。
    Examples:
        zhihu config set language en
        zhihu config set language zh_hant
    """
    from core.config_runtime import update_config
    from core.i18n import SUPPORTED_LANGUAGES

    if key == "language":
        if value not in SUPPORTED_LANGUAGES:
            rprint(f"[red]Error:[/] Unsupported language '{value}'. Supported: {list(SUPPORTED_LANGUAGES.keys())}")
            raise SystemExit(1)
        
        update_config({"global": {"language": value, "language_configured": True}})
        rprint(f"✅ Language updated to / 语言已更新为: [green]{value}[/]")
    else:
        rprint(f"[yellow]Warning:[/] Currently only 'language' can be set via this command. / 目前仅支持 'language'。")
        raise SystemExit(1)


@app.command("check")
def check() -> None:
    """
    Check environment dependencies and configuration.
    检查环境依赖和配置是否正常。

    Checks:
    1. config.yaml exists
    2. cookie readiness and configured/active path compatibility
    3. Playwright browser available
    """
    render_environment_check()

# ============================================================
# Entry Point (入口点)
# ============================================================

def main() -> None:
    """CLI entry point / CLI 入口"""
    if len(sys.argv) == 1:
        # Bare `zhihu` → launch TUI directly (first run shows language selector)
        from cli.interactive import run_interactive
        run_interactive()
        return
    app()


if __name__ == "__main__":
    main()
