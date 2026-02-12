import asyncio
import re
import sys
import time
import functools
from datetime import datetime
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

from core.converter import ZhihuConverter
from core.scraper import ZhihuDownloader, PROXY_SERVER

# ==========================================
# 核心配色系统 (Theme Tokens)
# ==========================================
THEME = {
    "accent": "#00C8FF",    # 霓虹蓝
    "secondary": "#FF1493", # 亮桃红
    "warn": "#EBFF3B",      # 亮黄
    "text": "#FFFFFF",      # 纯白
    "dim": "#666666",       # 暗灰
    "success": "#00FF55"    # 荧光绿
}

# 初始化 Rich Console
console = Console()
executor = ThreadPoolExecutor(max_workers=1)

# Questionary 样式
q_style = Style([
    ('question', f'fg:{THEME["accent"]} bold'),
    ('answer', f'fg:{THEME["success"]}'),
    ('pointer', f'fg:{THEME["secondary"]} bold'),
    ('highlighted', f'fg:{THEME["accent"]} bold'),
    ('selected', f'fg:{THEME["success"]}'),
    ('separator', f'fg:{THEME["dim"]}'),
    ('instruction', f'fg:{THEME["dim"]}'),
])
executor = ThreadPoolExecutor(max_workers=1)

# ==========================================
# 批量下载列表 (不想用命令行输入时，在这里填入链接)
# ==========================================
BATCH_URLS = []

DATA_DIR = Path(__file__).parent / "data"

async def _async_input(prompt_text: str) -> str:
    """封装 rich 的 console.input 为异步模式，带有现代感的 Prompt。"""
    full_prompt = Text.assemble(
        (f" ❯ ", f"bold {THEME['secondary']}"),
        (prompt_text, f"bold {THEME['accent']}")
    )
    loop = asyncio.get_event_loop()
    # 使用 ThreadPoolExecutor 运行同步的 console.input
    return await loop.run_in_executor(executor, console.input, full_prompt)


# ── 工具函数 ─────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """清理文件名常用非法字符。"""
    name = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "_", name)
    name = name.strip(" .")
    if len(name) > 50:
        name = name[:50].rstrip(" .")
    return name or "untitled"


def extract_urls(text: str) -> list[str]:
    """从文本中提取知乎链接，支持不带 https:// 的输入。"""
    # 允许协议头可选
    pattern = r"(?:https?://)?(?:www\.|zhuanlan\.)?zhihu\.com/(?:p/\d+|question/\d+(?:/answer/\d+)?)"
    matches = re.findall(pattern, text)
    results = []
    for m in matches:
        if not m.startswith("http"):
            m = "https://" + m
        results.append(m)
    return list(dict.fromkeys(results))


def _print_banner():
    """打印符合 Americana Fusion 风格的 Dashboard Header。"""
    # 顶部装饰器
    top_deco = Text("⚡ MODULE: DATA_EXTRACTION_UNIT ⚡", style=f"bold {THEME['accent']}")
    
    # 知乎 (Neon Branding)
    zhihu_header = Text("█ 知 乎 █", style=f"bold {THEME['secondary']}")
    
    # SCRAPER (Refined Slant Art)
    scraper_art = r"""
   _____ __________  ___    ____  __________ 
  / ___// ____/ __ \/   |  / __ \/ ____/ __ \
  \__ \/ /   / /_/ / /| | / /_/ / __/ / /_/ /
 ___/ / /___/ _, _/ ___ |/ ____/ /___/ _, _/ 
/____/\____/_/ |_/_/  |_/_/   /_____/_/ |_|  
""".strip("\n")

    # 底部元数据
    bot_deco = Text("INTELLIGENT CRAWLER ENGINE", style=f"{THEME['dim']} italic")
    
    # 组合 Banner
    header_content = Group(
        Align.center(top_deco),
        Align.center(zhihu_header),
        Align.center(Text(scraper_art, style=f"bold {THEME['accent']}")),
        Align.center(bot_deco)
    )
    
    header_panel = Panel(
        header_content,
        border_style=THEME["accent"],
        box=box.ROUNDED,
        padding=(1, 2),
        width=70
    )

    # Status Panel (横向单行)
    proxy_status = f"[{THEME['success']}]ON[/]" if PROXY_SERVER else f"[{THEME['dim']}]OFF[/]"
    cookie_status = f"[{THEME['success']}]VALID[/]" if Path("cookies.json").exists() else f"[{THEME['warn']}]MISSING[/]"
    
    status_line = Text.assemble(
        " 🔗 ", ("GATEWAY: ", THEME["accent"]), (proxy_status, ""),
        "  |  ",
        " 🔑 ", ("SEAL: ", THEME["accent"]), (cookie_status, ""),
        "  |  ",
        " 📂 ", ("ARCHIVE: ", THEME["accent"]), (str(DATA_DIR), THEME["text"]),
        "  |  ",
        " 🕸️ ", ("CORE: ", THEME["accent"]), (f"[{THEME['secondary']}]LINKED[/]", "")
    )
    
    status_panel = Panel(
        Align.center(status_line),
        border_style=THEME["dim"],
        box=box.HORIZONTALS,
        padding=(0, 1),
        width=70
    )

    console.print(Align.center(header_panel))
    console.print(Align.center(status_panel))
    console.print("\n")


async def parse_question_options(url: str) -> dict:
    """交互式解析问题抓取选项。"""
    
    # 1. 检查 Cookie (复用 downloader 的逻辑)
    downloader = ZhihuDownloader(url)
    if not downloader.has_valid_cookies():
        console.print("[yellow]⚠️  未检测到有效登录信息 (z_c0)，强制使用游客模式 (Top 3)[/yellow]")
        return {"start": 0, "limit": 3}

    # 2. 交互菜单 (异步)
    choice = await questionary.select(
        "请选择抓取模式:",
        choices=[
            "1. 按数量抓取 (Top N)",
            "2. 按范围抓取 (Start -> End)",
            "3. 返回默认 (Top 3)"
        ],
        style=q_style
    ).ask_async()
    
    if not choice: # Ctrl+C
        return {"start": 0, "limit": 3}
        
    if choice.startswith("1"):
        limit = await questionary.text(
            "请输入抓取数量:",
            default="20",
            validate=lambda text: text.isdigit() and int(text) > 0 or "请输入正整数",
            style=q_style
        ).ask_async()
        return {"start": 0, "limit": int(limit) if limit else 3}
        
    elif choice.startswith("2"):
        console.print(f"[{THEME['dim']}]提示: 支持输入 '答主名字' 或 '回答链接/ID'[/]")
        start = await questionary.text("起始锚点 (Start):", style=q_style).ask_async()
        end = await questionary.text("结束锚点 (End):", style=q_style).ask_async()
        
        s_anchor = _parse_anchor(start)
        e_anchor = _parse_anchor(end)
        
        if s_anchor and e_anchor:
            return {
                "start": 0, "limit": 3,
                "start_anchor": s_anchor,
                "end_anchor": e_anchor
            }
        else:
            console.print("[red]❌ 锚点解析失败，回退到默认模式[/red]")
            return {"start": 0, "limit": 3}
            
    return {"start": 0, "limit": 3}


def _parse_anchor(val: str) -> Optional[dict]:
    if not val: return None
    m = re.search(r"answer/(\d+)", val)
    if m: return {"type": "answer_id", "value": m.group(1)}
    return {"type": "author", "value": val}


# ── 流水线 ───────────────────────────────────────────────────

class Pipeline:
    def __init__(self, url: str, output_dir: Path = DATA_DIR, scrape_config: Optional[dict] = None):
        self.url = url
        self.output_dir = output_dir
        self.scrape_config = scrape_config or {}
        self.summary = [] # 记录结果用于表格展示

    async def run(self) -> list:
        downloader = ZhihuDownloader(self.url)
        
        # 使用自定义的 Progress
        progress = Progress(
            SpinnerColumn(style=THEME["secondary"]),
            TextColumn("[bold white]{task.description}"),
            BarColumn(complete_style=THEME["accent"], finished_style=THEME["success"]),
            TaskProgressColumn(),
            expand=True
        )

        with Live(progress, console=console, refresh_per_second=10):
            task_id = progress.add_task("🚀 Extracting knowledge...", total=None)
            data = await downloader.fetch_page(**self.scrape_config)
            progress.update(task_id, description="📦 Data received, starting conversion...")

            if isinstance(data, list):
                progress.update(task_id, total=len(data))
                for item in data:
                    progress.update(task_id, description=f"📝 Converting: {item['title'][:20]}...")
                    res = await self._process_one(item, downloader.page_type)
                    self.summary.append(res)
                    progress.advance(task_id)
            else:
                res = await self._process_one(data, downloader.page_type)
                self.summary.append(res)
                progress.update(task_id, completed=1, total=1)
            
            progress.update(task_id, description="✨ Task completed!")
            
        return self.summary

    async def _process_one(self, info: dict, page_type: str) -> dict:
        title = info["title"]
        author = info["author"]
        html = info["html"]
        
        # 结果对象
        result = {
            "title": title,
            "author": author,
            "status": "✅ 成功",
            "path": ""
        }

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            safe_title = sanitize_filename(title)
            safe_author = sanitize_filename(author)

            if page_type == "question":
                folder_name = sanitize_filename(f"[{today}] {title}")
                file_name = f"{safe_author}.md"
            else:
                date_str = info.get("date", today)
                folder_name = sanitize_filename(f"[{date_str}] {title} - {author}")
                file_name = "index.md"

            folder = self.output_dir / folder_name
            img_dir = folder / "images"
            folder.mkdir(parents=True, exist_ok=True)

            # 下载图片
            img_urls = ZhihuConverter.extract_image_urls(html)
            img_map = {}
            if img_urls:
                # 这里的 print 会打断 progress bar，但在 single item 时没关系
                # 为了完美，这里先静默下载或简单输出
                img_map = await ZhihuDownloader.download_images(img_urls, img_dir)

            # HTML -> Markdown
            converter = ZhihuConverter(img_map=img_map)
            md = converter.convert(html)

            # 保存
            header = (
                f"# {title}\n\n"
                f"> **作者**: {author}  \n"
                f"> **来源**: [{self.url}]({self.url})  \n"
                f"> **日期**: {today}\n\n"
                f"---\n\n"
            )
            out_path = folder / file_name
            out_path.write_text(header + md, encoding="utf-8")
            
            # 清理空目录
            if img_dir.exists() and not any(img_dir.iterdir()):
                img_dir.rmdir()
                
            # 记录相对路径
            try:
                result["path"] = str(out_path.relative_to(Path.cwd()))
            except:
                result["path"] = str(out_path)
                
        except Exception as e:
            result["status"] = f"✘ Failed: {str(e)[:20]}"
        
        return result


# ── 主循环 ───────────────────────────────────────────────────

async def main() -> None:
    _print_banner()
    
    while True:
        # 获取输入
        if BATCH_URLS:
            console.print(f"[bold yellow]📋 检测到批量任务 ({len(BATCH_URLS)} 个)[/bold yellow]")
            urls = list(BATCH_URLS)
            BATCH_URLS.clear()
        else:
            # 使用 rich 原生 input 的封装版，彻底解决 ghost prompt 冲突问题
            answer = await _async_input("请输入知乎链接 (或 'q' 退出): ")
            
            if not answer or answer.strip().lower() == 'q':
                console.print(f"[{THEME['dim']}]Shutting down...[/]")
                time.sleep(0.3)
                break
            
            answer = answer.strip()
            urls = extract_urls(answer)
            
        if not urls:
            if answer and answer.lower() != 'q':
                # 批量任务无需报错，正常循环
                if not BATCH_URLS:
                    console.print("[red]❌ 未识别到有效链接，请重试[/red]")
            continue
            
        # 处理链接
        console.rule(f"[bold {THEME['accent']}]Processing {len(urls)} Task(s)[/]")
        
        all_results = []
        
        for url in urls:
            scrape_config = {}
            if "/question/" in url and "/answer/" not in url:
                console.print(f"\n[{THEME['accent']}]⚙️  Question detected:[/][dim] {url}[/]")
                scrape_config = await parse_question_options(url)
            
            try:
                pipeline = Pipeline(url, scrape_config=scrape_config)
                results = await pipeline.run()
                all_results.extend(results)
            except Exception as e:
                console.print(f"[bold {THEME['secondary']}]✘ Critical Error:[/][red] {e}[/]")
        
        # 打印汇总表格
        if all_results:
            table = Table(
                title=f"[{THEME['success']}]✔ Task Execution Summary[/]", 
                box=box.ROUNDED,
                header_style=f"bold {THEME['accent']}"
            )
            table.add_column("Author/Title", style="dim")
            table.add_column("Status", justify="center")
            table.add_column("Path", style=THEME["success"])
            
            for res in all_results:
                status_color = THEME["success"] if "✔" in res['status'] else THEME["secondary"]
                table.add_row(
                    f"{res['author']}\n[dim]{res['title'][:25]}...[/dim]",
                    f"[{status_color}]{res['status']}[/]",
                    res['path']
                )
            
            console.print(Align.center(table))
            console.print("\n")

if __name__ == "__main__":
    try:
        with console.status("⚡ [bold]System Initializing...[/bold]", spinner="aesthetic"):
            time.sleep(0.5)
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print(f"\n[{THEME['dim']}]Operation cancelled by user. Shutting down...[/]")
        time.sleep(0.3)