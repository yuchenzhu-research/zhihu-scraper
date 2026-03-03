"""
interactive.py - Interactive Panel Module (Americana Fusion Style)

Inherits the brilliant terminal Dashboard from legacy main.py and integrates with v3.0 database engine.

================================================================================
interactive.py — 交互式面板模块 (Americana Fusion 风格)

继承旧版 main.py 的绚丽终端 Dashboard，并对接 v3.0 的 db 引擎。
================================================================================
"""

import asyncio
import time
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import questionary
from questionary import Style
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskProgressColumn
from rich import box
from rich.live import Live

from core.config import get_config, get_logger
from core.utils import extract_urls
from core.scraper import ZhihuDownloader
from cli.app import _fetch_and_save

# ==========================================
# Initialize Configuration and Logging (初始化配置和日志)
# ==========================================
cfg = get_config()
log = get_logger()

# ==========================================
# Core Color Theme System (Theme Tokens) / 核心配色系统
# ==========================================
THEME = {
    "accent": "#00C8FF",    # Neon Blue / 霓虹蓝
    "secondary": "#FF1493", # Bright Pink / 亮桃红
    "warn": "#EBFF3B",      # Bright Yellow / 亮黄
    "text": "#FFFFFF",      # Pure White / 纯白
    "dim": "#666666",       # Dark Gray / 暗灰
    "success": "#00FF55"    # Fluorescent Green / 荧光绿
}

console = Console()
executor = ThreadPoolExecutor(max_workers=1)

q_style = Style([
    ('question', f'fg:{THEME["accent"]} bold'),
    ('answer', f'fg:{THEME["success"]}'),
    ('pointer', f'fg:{THEME["secondary"]} bold'),
    ('highlighted', f'fg:{THEME["accent"]} bold'),
    ('selected', f'fg:{THEME["success"]}'),
    ('separator', f'fg:{THEME["dim"]}'),
    ('instruction', f'fg:{THEME["dim"]}'),
])

DATA_DIR = Path(cfg.output.directory)


async def _async_input(prompt_text: str) -> str:
    """
    Wrap rich console.input as async mode
    封装 rich 的 console.input 为异步模式
    """
    full_prompt = Text.assemble(
        (f" ❯ ", f"bold {THEME['secondary']}"),
        (prompt_text, f"bold {THEME['accent']}")
    )
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, console.input, full_prompt)


# Note: extract_urls is now imported from core.utils to avoid code duplication


def _print_banner():
    """
    Print Dashboard Header in Americana Fusion style
    打印符合 Americana Fusion 风格的 Dashboard Header
    """
    top_deco = Text("⚡ MODULE: DATA_EXTRACTION_UNIT ⚡", style=f"bold {THEME['accent']}")
    zhihu_header = Text("█ 知 乎 █", style=f"bold {THEME['secondary']}")
    scraper_art = r"""
   _____ __________  ___    ____  __________
  / ___// ____/ __ \/   |  / __ \/ ____/ __ \
  \__ \/ /   / /_/ / /| | / /_/ / __/ / /_/ /
 ___/ / /___/ _, _/ ___ |/ ____/ /___/ _, _/
/____/\____/_/ |_/_/  |_/_/   /_____/_/ |_|
""".strip("\n")

    bot_deco = Text("INTELLIGENT CRAWLER ENGINE (v3.0 DB-LINKED)", style=f"{THEME['dim']} italic")

    header_content = Group(
        Align.center(top_deco),
        Align.center(zhihu_header),
        Align.center(Text(scraper_art, style=f"bold {THEME['accent']}")),
        Align.center(bot_deco)
    )

    header_panel = Panel(
        header_content, border_style=THEME["accent"], box=box.ROUNDED, padding=(1, 2), width=70
    )

    cookie_status = f"[{THEME['success']}]VALID[/]" if Path("cookies.json").exists() else f"[{THEME['warn']}]MISSING[/]"

    status_line = Text.assemble(
        " 🔑 ", ("SEAL: ", THEME["accent"]), (cookie_status, ""), "  |  ",
        " 📂 ", ("ARCHIVE: ", THEME["accent"]), (f"[{THEME['success']}]SQLite + FS[/]", ""), "  |  ",
        " 🕸️ ", ("CORE: ", THEME["accent"]), (f"[{THEME['secondary']}]API PROTOCOL[/]", "")
    )

    status_panel = Panel(
        Align.center(status_line), border_style=THEME["dim"], box=box.HORIZONTALS, padding=(0, 1), width=70
    )

    console.print(Align.center(header_panel))
    console.print(Align.center(status_panel))
    console.print("\n")


async def parse_question_options(url: str) -> dict:
    """
    Parse question scraping options interactively
    交互式解析问题抓取选项
    """
    downloader = ZhihuDownloader(url)
    if not downloader.has_valid_cookies():
        console.print("[yellow]⚠️  No valid login info (z_c0) detected, forced guest mode (Top 3) / 未检测到有效登录信息 (z_c0)，强制使用游客模式 (Top 3)[/yellow]")
        return {"start": 0, "limit": 3}

    choice = await questionary.select(
        "Please select scraping mode / 请选择抓取模式:",
        choices=["1. Scrape by quantity (Top N) / 按数量抓取 (Top N)", "2. Return default (Top 3) / 返回默认 (Top 3)"],
        style=q_style
    ).ask_async()

    if not choice:
        return {"start": 0, "limit": 3}

    if choice.startswith("1"):
        limit = await questionary.text(
            "Please enter scraping quantity / 请输入抓取数量:", default="20",
            validate=lambda text: text.isdigit() and int(text) > 0 or "Please enter positive integer / 请输入正整数",
            style=q_style
        ).ask_async()
        return {"start": 0, "limit": int(limit) if limit else 3}

    return {"start": 0, "limit": 3}


# ==========================================
# Interactive Main Entry (交互式主入口)
# ==========================================

async def run_interactive():
    """
    Main interactive loop
    交互式主入口
    """
    _print_banner()

    while True:
        answer = await _async_input("Please enter Zhihu link (or 'q' to exit) / 请输入知乎链接 (或 'q' 退出): ")

        if not answer or answer.strip().lower() == 'q':
            console.print(f"[{THEME['dim']}]Shutting down... / 正在关闭...[/]")
            time.sleep(0.3)
            break

        answer = answer.strip()
        urls = extract_urls(answer)

        if not urls:
            if answer and answer.lower() != 'q':
                console.print("[red]❌ No valid link recognized, please retry / 未识别到有效链接，请重试[/red]")
            continue

        console.rule(f"[bold {THEME['accent']}]Processing {len(urls)} Task(s) / 正在处理 {len(urls)} 个任务[/]")

        for url in urls:
            scrape_config = {}
            if "/question/" in url and "/answer/" not in url:
                console.print(f"\n[{THEME['accent']}]⚙️  Question detected / 检测到问题:[/][dim] {url}[/]")
                scrape_config = await parse_question_options(url)

            try:
                progress = Progress(
                    SpinnerColumn(style=THEME["secondary"]),
                    TextColumn("[bold white]{task.description}"),
                    BarColumn(complete_style=THEME["accent"], finished_style=THEME["success"]),
                    TaskProgressColumn(),
                    expand=True
                )
                with Live(progress, console=console, refresh_per_second=10):
                    task_id = progress.add_task("🚀 Extracting and Saving to Database... / 正在提取并保存到数据库...", total=None)

                    # Call core pipeline with database storage / 调用带有数据库存储的底层核心管道
                    await _fetch_and_save(
                        url=url,
                        output_dir=DATA_DIR,
                        scrape_config=scrape_config,
                        download_images=True,
                        headless=True
                    )

                    progress.update(task_id, completed=1, total=1, description="✨ Task completed and DB synced / 任务完成并已同步数据库!")
            except Exception as e:
                console.print(f"[bold {THEME['secondary']}]✘ Critical Error / 严重错误:[/][red] {e}[/]")

        # Give user a moment to read results / 给用户一小段停顿阅读结果
        print("\n")