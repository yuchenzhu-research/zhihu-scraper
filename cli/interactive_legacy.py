"""
interactive_legacy.py - Legacy interactive workflow

Provides a guided terminal workspace for capturing Zhihu links into local archives.

================================================================================
interactive_legacy.py — 旧版交互式归档工作台

保留旧版 Rich / questionary 交互流程，作为 TUI 重构期间的回退入口。
================================================================================
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import StringIO

from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.align import Align
from rich.padding import Padding
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskProgressColumn
from rich import box
from rich.live import Live

from core.config import get_config, resolve_project_path
from core.cookie_manager import has_available_cookie_sources
from core.utils import extract_urls
from core.scraper import ZhihuDownloader
from cli.app import _fetch_and_save, _get_questionary

# ==========================================
# Minimal Theme Tokens / 极简主题变量
# ==========================================
THEME = {
    "accent": "#0A84FF",
    "text": "#F5F5F7",
    "muted": "#8E8E93",
    "line": "#3A3A3C",
    "panel": "#1C1C1E",
    "success": "#30D158",
    "warn": "#FFD60A",
    "danger": "#FF453A",
}

console = Console()
executor = ThreadPoolExecutor(max_workers=1)

def _q_style():
    Style = _get_questionary().Style
    return Style([
        ('question', f'fg:{THEME["accent"]} bold'),
        ('answer', f'fg:{THEME["text"]}'),
        ('pointer', f'fg:{THEME["accent"]} bold'),
        ('highlighted', f'fg:{THEME["text"]} bg:{THEME["accent"]} bold'),
        ('selected', f'fg:{THEME["success"]}'),
        ('separator', f'fg:{THEME["line"]}'),
        ('instruction', f'fg:{THEME["muted"]}'),
    ])

def _get_cfg():
    """Load runtime config lazily / 延迟加载运行时配置"""
    return get_config()


def _get_data_dir():
    """Resolve data dir lazily / 延迟解析数据目录"""
    return resolve_project_path(_get_cfg().output.directory)


async def _async_input(prompt_text: str) -> str:
    """
    Wrap rich console.input as async mode
    封装 rich 的 console.input 为异步模式
    """
    full_prompt = Text.assemble(
        ("• ", f"bold {THEME['accent']}"),
        (prompt_text, f"bold {THEME['text']}")
    )
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, console.input, full_prompt)


# Note: extract_urls is now imported from core.utils to avoid code duplication


def _layout_metrics() -> tuple[int, int]:
    """
    Compute responsive layout sizes from current terminal width.
    根据当前终端宽度计算响应式布局尺寸。
    """
    terminal_width = max(console.size.width, 48)
    frame_width = min(108, max(68, int(terminal_width * 0.70)))
    frame_width = min(frame_width, terminal_width - 4)
    card_width = max(18, (frame_width - 4) // 3)
    return frame_width, card_width


def _build_status_card(label: str, value: str, tone: str, width: int) -> Panel:
    """
    Build a compact status card.
    构建紧凑状态卡片。
    """
    title = Text(label, style=f"bold {THEME['muted']}")
    body = Text(value, style=f"bold {THEME[tone]}")
    return Panel(
        Align.center(Group(title, body)),
        box=box.ROUNDED,
        border_style=THEME["line"],
        padding=(0, 1),
        width=width,
    )


def _print_banner():
    """
    Render the interactive workspace header.
    渲染交互式工作台头部。
    """
    cfg = _get_cfg()
    frame_width, card_width = _layout_metrics()
    cookie_status = (
        ("已就绪", "success")
        if has_available_cookie_sources(cfg.zhihu.cookies_file, cfg.zhihu.cookies_pool_dir)
        else ("未检测到", "warn")
    )
    browser_status = ("无头", "muted") if cfg.zhihu.browser.headless else ("显示窗口", "accent")

    eyebrow = Text("ZHIHU ARCHIVE", style=f"bold {THEME['accent']}")
    title = Text("知乎归档台", style=f"bold {THEME['text']}")
    subtitle = Text(
        "把回答、问题与专栏保存为 Markdown 和本地索引",
        style=THEME["muted"],
    )

    header_panel = Panel(
        Align.center(Group(eyebrow, title, subtitle)),
        border_style=THEME["line"],
        box=box.ROUNDED,
        padding=(1, 3),
        width=frame_width,
    )

    cards = [
        _build_status_card("Cookie", cookie_status[0], cookie_status[1], card_width),
        _build_status_card("存储", "Markdown / SQLite", "success", card_width),
        _build_status_card("浏览器", browser_status[0], browser_status[1], card_width),
    ]

    status_renderable = Columns(
        cards,
        equal=True,
        expand=False,
        align="center",
        padding=(0, 1),
    )

    hint_panel = Panel(
        Align.center(
            Text(
                "粘贴知乎链接并回车开始归档。输入 q 退出。",
                style=THEME["muted"],
            )
        ),
        border_style=THEME["line"],
        box=box.ROUNDED,
        padding=(0, 2),
        width=frame_width,
    )

    workspace = Group(
        Align.center(header_panel),
        Align.center(status_renderable),
        Align.center(hint_panel),
    )
    workspace_height = _measure_renderable_height(workspace)
    top_padding = max(0, (console.size.height - workspace_height) // 2 - 2)

    console.clear()
    console.print(Padding(workspace, (top_padding, 0, 0, 0)))
    console.print()


def _measure_renderable_height(renderable) -> int:
    """
    Measure rendered line height for vertical centering.
    计算渲染后的行数，用于垂直居中。
    """
    buffer = StringIO()
    probe = Console(
        width=console.size.width,
        file=buffer,
        force_terminal=False,
        color_system=None,
        legacy_windows=False,
    )
    probe.print(renderable)
    lines = buffer.getvalue().rstrip("\n").splitlines()
    return len(lines)


async def parse_question_options(url: str) -> dict:
    """
    Parse question scraping options interactively
    交互式解析问题抓取选项
    """
    questionary = _get_questionary()
    downloader = ZhihuDownloader(url)
    if not downloader.has_valid_cookies():
        console.print(
            f"[{THEME['warn']}]未检测到可用 Cookie，将使用游客模式，仅抓取前 3 条。[/]"
        )
        return {"start": 0, "limit": 3}

    choice = await questionary.select(
        "选择抓取方式:",
        choices=[
            "抓取指定数量（Top N）",
            "使用默认数量（Top 3）",
        ],
        style=_q_style()
    ).ask_async()

    if not choice:
        return {"start": 0, "limit": 3}

    if choice.startswith("抓取指定数量"):
        limit = await questionary.text(
            "请输入抓取数量:", default="20",
            validate=lambda text: text.isdigit() and int(text) > 0 or "请输入正整数",
            style=_q_style()
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
    cfg = _get_cfg()
    data_dir = _get_data_dir()
    _print_banner()

    while True:
        answer = await _async_input("输入知乎链接")

        if not answer or answer.strip().lower() == 'q':
            console.print(f"[{THEME['muted']}]已退出归档工作台。[/]")
            await asyncio.sleep(0.2)
            break

        answer = answer.strip()
        urls = extract_urls(answer)

        if not urls:
            if answer and answer.lower() != 'q':
                console.print(f"[{THEME['danger']}]未识别到有效知乎链接，请重新输入。[/]")
            continue

        console.rule(f"[bold {THEME['accent']}]开始处理 {len(urls)} 个链接[/]")

        for url in urls:
            scrape_config = {}
            if "/question/" in url and "/answer/" not in url:
                console.print(f"\n[{THEME['accent']}]检测到问题页[/] [{THEME['muted']}]{url}[/]")
                scrape_config = await parse_question_options(url)

            try:
                progress = Progress(
                    SpinnerColumn(style=THEME["accent"]),
                    TextColumn(f"[bold {THEME['text']}]{{task.description}}"),
                    BarColumn(complete_style=THEME["accent"], finished_style=THEME["success"]),
                    TaskProgressColumn(text_format=f"[{THEME['muted']}]{{task.percentage:>3.0f}}%"),
                    expand=True
                )
                with Live(progress, console=console, refresh_per_second=10):
                    task_id = progress.add_task("正在抓取内容并写入归档", total=None)

                    await _fetch_and_save(
                        url=url,
                        output_dir=data_dir,
                        scrape_config=scrape_config,
                        download_images=True,
                        headless=cfg.zhihu.browser.headless
                    )

                    progress.update(task_id, completed=1, total=1, description="归档完成")
                console.print(f"[{THEME['success']}]已保存到本地归档[/] [{THEME['muted']}]{url}[/]")
            except Exception as e:
                console.print(f"[bold {THEME['danger']}]处理失败[/] [{THEME['text']}]{e}[/]")

        print("\n")
