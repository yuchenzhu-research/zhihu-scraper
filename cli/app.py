"""
app.py - CLI Enhancement Module

Provides modern command-line interface using Typer with auto-completion support.

Core Functions:
- fetch: Scrape single Zhihu link (article/answer/question)
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
import typer
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text

from core.config import get_config, get_logger, get_humanizer
from core.utils import sanitize_filename, extract_urls
from core.scraper import ZhihuDownloader
from core.converter import ZhihuConverter
from core.errors import handle_error

# ============================================================
# CLI Application Initialization (CLI 应用初始化)
# ============================================================

app = typer.Typer(
    name="zhihu",
    help="🕷️ Zhihu High-Quality Content Scraper / 知乎高质量内容爬取工具",
    add_completion=False,
    no_args_is_help=True,
)

# Initialize configuration and logging / 初始化配置和日志
cfg = get_config()
log = get_logger()


# ============================================================
# Utility Functions (工具函数)
# ============================================================

# Note: sanitize_filename and extract_urls are now imported from core.utils
# to avoid code duplication across CLI and interactive modules.

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


# ============================================================
# Command Definitions (命令定义)
# ============================================================

@app.command("fetch")
def fetch(
    url: str = typer.Argument(..., help="Zhihu link (question/answer/column) / 知乎链接 (问题/回答/专栏)"),
    output: Path = typer.Option(Path("./data"), "-o", "--output", help="Output directory / 输出目录"),
    limit: Optional[int] = typer.Option(None, "-n", "--limit", help="Limit answer count (question pages only) / 限制回答数量 (仅限问题页)"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="Don't download images / 不下载图片"),
    headless: bool = typer.Option(True, "-b", "--headless", help="Run browser in headless mode / 无头模式运行浏览器"),
) -> None:
    """
    Scrape a single Zhihu link.
    抓取单个知乎链接。

    Supported link types:
    - Column article: https://zhuanlan.zhihu.com/p/123456
    - Single answer: https://www.zhihu.com/question/123/answer/456
    - Question page (batch): https://www.zhihu.com/question/123

    Examples:
        zhihu fetch "https://www.zhihu.com/p/123456"
        zhihu fetch "https://www.zhihu.com/question/123456" -n 10
        zhihu fetch "https://www.zhihu.com/p/abcdef" -o ./output
    """
    log.info("fetch_started", url=url, limit=limit)

    try:
        downloader = ZhihuDownloader(url)

        # Check if login is required / 检测是否需要登录
        if not downloader.has_valid_cookies() and cfg.zhihu.cookies_required:
            rprint("[yellow]⚠️  No valid Cookie detected, will use guest mode / 未检测到有效 Cookie，将使用游客模式[/yellow]")

        # Prepare scraping configuration / 准备抓取配置
        scrape_config = {}
        if limit and "/question/" in url and "/answer/" not in url:
            scrape_config = {"start": 0, "limit": limit}

        # Execute scraping / 执行抓取
        rprint(f"🌍 Accessing / 正在访问: {url}")

        asyncio.run(_fetch_and_save(
            url=url,
            output_dir=output,
            scrape_config=scrape_config,
            download_images=not no_images,
            headless=headless
        ))

    except Exception as e:
        handle_error(e, log)
        raise SystemExit(1)


@app.command("batch")
def batch(
    input_file: Path = typer.Argument(..., help="URL list file (one link per line) / URL列表文件 (每行一个链接)"),
    output: Path = typer.Option(Path("./data"), "-o", "--output", help="Output directory / 输出目录"),
    concurrency: int = typer.Option(4, "-c", "--concurrency", help="Concurrency count (recommend 4-8) / 并发数 (建议 4-8)"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="Don't download images / 不下载图片"),
    headless: bool = typer.Option(True, "-b", "--headless", help="Run browser in headless mode / 无头模式运行浏览器"),
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
        output_dir=output,
        concurrency=max_concurrency,
        download_images=not no_images,
        headless=headless
    ))

    # Statistics / 统计结果
    success = sum(1 for r in results if r["success"])
    failed = len(results) - success

    rprint(f"\n[bold]📊 Batch completed / 批量完成: {success} success / 成功, {failed} failed / 失败[/bold]")
    log.info("batch_completed", success=success, failed=failed)


@app.command("monitor")
def monitor(
    collection_id: str = typer.Argument(..., help="Zhihu collection ID (e.g., 78170682) / 知乎收藏夹ID (如 78170682)"),
    output: Path = typer.Option(Path("./data"), "-o", "--output", help="Output directory / 输出目录"),
    concurrency: int = typer.Option(4, "-c", "--concurrency", help="Concurrency count / 并发数"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="Don't download images / 不下载图片"),
    headless: bool = typer.Option(True, "-b", "--headless", help="Headless mode / 无头模式"),
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
    log.info("monitor_started", collection_id=collection_id)
    rprint(f"[bold]📡 Starting incremental monitoring / 启动增量监控: Collection / 收藏夹 {collection_id}[/bold]")

    from core.monitor import CollectionMonitor
    m = CollectionMonitor(data_dir=str(output))

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
        output_dir=output,
        concurrency=max_concurrency,
        download_images=not no_images,
        headless=headless,
        collection_id=collection_id
    ))

    success = sum(1 for r in results if r["success"])
    failed = len(results) - success

    rprint(f"\n[bold]📊 Monitor download completed / 监控下载完成: {success} success / 成功, {failed} failed / 失败[/bold]")

    if success > 0:
        m.mark_updated(collection_id, new_last_id)
        rprint(f"[cyan]✅ Saved latest progress pointer / 已保存最新进度指针: {new_last_id}[/cyan]")


@app.command("query")
def query_db(
    keyword: str = typer.Argument(..., help="Keyword to search / 要搜索的关键词"),
    limit: int = typer.Option(10, "-l", "--limit", help="Maximum number of results / 最大显示结果数量"),
    data_dir: str = typer.Option("./data", "-d", "--data-dir", help="Data directory (default ./data) / 数据目录（默认 ./data）"),
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
    from core.db import ZhihuDatabase
    from rich.table import Table

    db_path = Path(data_dir) / "zhihu.db"
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
def interactive() -> None:
    """
    Launch interactive scraping mode with neon console panel.
    启动带霓虹控制台面板的交互式抓取模式。

    Features:
    - Color terminal interface
    - Guided URL input
    - Real-time capture progress
    - View capture history

    功能：
    - 彩色终端界面
    - 引导式输入 URL
    - 实时显示抓取进度
    - 查看抓取历史记录

    Example:
        zhihu interactive
    """
    from cli.interactive import run_interactive
    try:
        asyncio.run(run_interactive())
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
        rprint(Panel(
            Text(f"""
[b]配置路径 (Config Path):[/] {Path(__file__).parent.parent / "config.yaml"}

[b]输出目录 (Output Directory):[/] {cfg.output.directory}
[b]日志级别 (Log Level):[/] {cfg.logging.level}
[b]浏览器 (Browser):[/] {"Headless / 无头" if cfg.zhihu.browser.headless else "Visible / 有头"}
[b]重试次数 (Retry Attempts):[/] {cfg.crawler.retry.max_attempts}
[b]图片并发 (Image Concurrency):[/] {cfg.crawler.images.concurrency}
[b]Cookie轮换 (Cookie Rotation):[/] {"Enabled / 启用" if hasattr(cfg, 'zhihu') and cfg.zhihu.cookies_required else "Disabled / 禁用"}
            """.strip(), justify="left"),
            title="🛠��� Current Configuration / 当前配置",
            border_style="cyan"
        ))


@app.command("check")
def check() -> None:
    """
    Check environment dependencies and configuration.
    检查环境依赖和配置是否正常。

    Checks:
    1. config.yaml exists
    2. cookies.json valid
    3. Playwright browser available
    """
    from playwright.async_api import async_playwright

    rprint("🔍 System check... / 系统检查...\n")

    # Check config file / 检查配置文件
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        rprint("✅ config.yaml exists / 存在")
    else:
        rprint("❌ config.yaml missing / 不存在")

    # Check cookies / 检查 cookies
    cookies_path = Path(__file__).parent.parent / "cookies.json"
    has_cookie = cookies_path.exists() and "YOUR_COOKIE_HERE" not in cookies_path.read_text()
    rprint(f"{'✅' if has_cookie else '⚠️'} cookies.json {'valid / 有效' if has_cookie else 'not configured or invalid / 未配置或无效'}")

    # Check playwright / 检查 playwright
    try:
        asyncio.run(_check_playwright())
        rprint("✅ Playwright OK / 正常")
    except Exception as e:
        rprint(f"❌ Playwright error / 错误: {e}")


async def _check_playwright() -> None:
    """Check if playwright is available / 检查 playwright 是否可用"""
    async with async_playwright() as pw:
        await pw.chromium.launch(headless=True)


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
) -> None:
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
    from datetime import datetime

    downloader = ZhihuDownloader(url)
    data = await downloader.fetch_page(**scrape_config)

    if not data:
        rprint("[yellow]⚠️  No content obtained / 未获取到内容[/yellow]")
        return

    today = datetime.now().strftime("%Y-%m-%d")

    # Handle single or multiple results (question page returns multiple answers)
    # 处理单个或多个结果 (问题页返回多个回答列表)
    items = data if isinstance(data, list) else [data]

    for item in items:
        title = sanitize_filename(item["title"])
        author = sanitize_filename(item["author"])

        folder_name = f"[{today}] {title}"
        folder = output_dir / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        # Download images / 下载图片
        img_map = {}
        if download_images:
            img_urls = ZhihuConverter.extract_image_urls(item["html"])
            if img_urls:
                rprint(f"   📥 Downloading {len(img_urls)} images... / 下载 {len(img_urls)} 张图片...")
                img_map = await ZhihuDownloader.download_images(
                    img_urls,
                    folder / "images"
                )

        # Convert and save Markdown / 转换并保存 Markdown
        converter = ZhihuConverter(img_map=img_map)
        md = converter.convert(item["html"])

        header = (
            f"# {item['title']}\n\n"
            f"> **Author / 作者**: {item['author']}  \n"
            f"> **Source / 来源**: [{url}]({url})  \n"
            f"> **Date / 日期**: {today}\n\n"
            "---\n\n"
        )

        out_path = folder / "index.md"
        full_md = header + md
        out_path.write_text(full_md, encoding="utf-8")

        # Save to SQLite database / 保存到 SQLite 数据库
        from core.db import ZhihuDatabase
        db_folder = output_dir if output_dir.name == "data" else output_dir.parent
        if db_folder.name != "data":
             db_folder = Path("./data")  # fallback
        db = ZhihuDatabase(str(db_folder / "zhihu.db"))
        db.save_article(item, full_md, collection_id=collection_id)
        db.close()

        rprint(f"✅ Saved / 保存: [cyan]{author}[/] - {title[:25]}...")
        rprint(f"   📁 {out_path} & DB / 入库 DB")


# ============================================================
# Entry Point (入口点)
# ============================================================

def main() -> None:
    """CLI entry point / CLI 入口"""
    app()


if __name__ == "__main__":
    main()