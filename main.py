import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

from typing import Optional
import functools
from concurrent.futures import ThreadPoolExecutor
import questionary
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich.progress import track
from rich import print as rprint

from core.converter import ZhihuConverter
from core.scraper import ZhihuDownloader, PROXY_SERVER

# 初始化 Rich Console
console = Console()
executor = ThreadPoolExecutor(max_workers=1)

# ==========================================
# 批量下载列表 (不想用命令行输入时，在这里填入链接)
# ==========================================
BATCH_URLS = []

DATA_DIR = Path(__file__).parent / "data"

async def _async_input(prompt: str) -> str:
    """封装 rich 的 console.input 为异步模式，比 questionary.text 稳定。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, console.input, prompt)


# ── 工具函数 ─────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """清理文件名常用非法字符。"""
    name = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "_", name)
    name = name.strip(" .")
    if len(name) > 50:
        name = name[:50].rstrip(" .")
    return name or "untitled"


def extract_urls(text: str) -> list[str]:
    """从文本中提取知乎链接。"""
    pattern = r"https?://(?:www\.|zhuanlan\.)?zhihu\.com/(?:p/\d+|question/\d+(?:/answer/\d+)?)"
    return list(dict.fromkeys(re.findall(pattern, text)))


def _print_banner():
    """打印真正酷炫的、完美对齐的 Banner。"""

    # 1. 准备 Banner 内容
    zh_text = Text("知    乎    爬    虫", style="bold cyan")
    
    # 更加紧凑且清晰的 ASCII 字体
    en_banner_raw = r"""
  ____  _   _ ___ _   _ _   _      ____   ____ ____      _    ____  _____ ____  
 |_  / | | | |_ _| | | | | | |    / ___| / ___|  _ \    / \  |  _ \| ____|  _ \ 
  / /  | |_| || || |_| | | | |    \___ \| |   | |_) |  / _ \ | |_) |  _| | |_) |
 / /_  |  _  || ||  _  | |_| |     ___) | |___|  _ <  / ___ \|  __/| |___|  _ < 
/____| |_| |_|___|_| |_|\___/     |____/ \____|_| \_\/_/   \_\_|   |_____|_| \_\
    """
    en_text = Text(en_banner_raw, style="bold dodger_blue1")

    # 2. 准备状态表格
    proxy = "未检测到"
    if PROXY_SERVER:
        proxy = PROXY_SERVER
        
    cookie_status = "[green]已配置[/green]" if (Path("cookies.json").exists()) else "[red]未配置[/red]"
    
    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold magenta", justify="right")
    info_table.add_column()
    info_table.add_row("Version:", "2.1.0")
    info_table.add_row("Proxy:", proxy)
    info_table.add_row("Cookie:", cookie_status)
    info_table.add_row("Output:", str(DATA_DIR))

    # 3. 组合并居中打印
    banner_group = Group(
        Align.center(zh_text),
        Align.center(en_text),
        Align.center(Panel(
            info_table, 
            title="[bold yellow]System Status[/bold yellow]", 
            border_style="bright_blue",
            expand=False,
            padding=(1, 4)
        ))
    )
    
    console.print(banner_group)
    console.print("\n")


async def parse_question_options(url: str) -> dict:
    """交互式解析问题抓取选项。"""
    
    # 1. 检查 Cookie (复用 downloader 的逻辑)
    downloader = ZhihuDownloader(url)
    if not await downloader.has_valid_cookies():
        console.print("[yellow]⚠️  未检测到有效登录信息 (z_c0)，强制使用游客模式 (Top 3)[/yellow]")
        return {"start": 0, "limit": 3}

    # 2. 交互菜单 (异步)
    choice = await questionary.select(
        "请选择抓取模式:",
        choices=[
            "1. 按数量抓取 (Top N)",
            "2. 按范围抓取 (Start -> End)",
            "3. 返回默认 (Top 3)"
        ]
    ).ask_async()
    
    if not choice: # Ctrl+C
        return {"start": 0, "limit": 3}
        
    if choice.startswith("1"):
        limit = await questionary.text(
            "请输入抓取数量:",
            default="20",
            validate=lambda text: text.isdigit() and int(text) > 0 or "请输入正整数"
        ).ask_async()
        return {"start": 0, "limit": int(limit) if limit else 3}
        
    elif choice.startswith("2"):
        console.print("[dim]提示: 支持输入 '答主名字' 或 '回答链接/ID'[/dim]")
        start = await questionary.text("起始锚点 (Start):").ask_async()
        end = await questionary.text("结束锚点 (End):").ask_async()
        
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
        
        # 使用 Status Spinner 代替刷屏日志
        with console.status(f"[bold green]正在请求页面...[/bold green] {self.url}", spinner="dots"):
            data = await downloader.fetch_page(**self.scrape_config)

        if isinstance(data, list):
            console.print(f"📦 抓取到 [bold cyan]{len(data)}[/bold cyan] 个内容，开始处理...")
            # 批量处理进度条? 这里简单起见还是逐个处理，为了 Vibe 效果，可以用 track
            
            for item in track(data, description="正在转换文档..."):
                res = await self._process_one(item, downloader.page_type)
                self.summary.append(res)
        else:
            res = await self._process_one(data, downloader.page_type)
            self.summary.append(res)
            
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
            result["status"] = f"❌ 失败: {e}"
        
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
            answer = await _async_input("🔗 [bold cyan]输入知乎链接 (或 'q' 退出): [/]")
            
            if not answer or answer.strip().lower() == 'q':
                console.print("[bold cyan]👋 See you next time![/bold cyan]")
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
        console.rule(f"[bold]开始处理 {len(urls)} 个任务[/bold]")
        
        all_results = []
        
        for url in urls:
            scrape_config = {}
            if "/question/" in url and "/answer/" not in url:
                console.print(f"\n[bold cyan]⚙️  检测到问题链接:[/bold cyan] {url}")
                scrape_config = await parse_question_options(url)
            
            try:
                pipeline = Pipeline(url, scrape_config=scrape_config)
                results = await pipeline.run()
                all_results.extend(results)
            except Exception as e:
                console.print(f"[bold red]❌ 严重错误:[/bold red] {e}")
        
        # 打印汇总表格
        if all_results:
            table = Table(title="✅ 任务执行汇总", show_header=True, header_style="bold magenta")
            table.add_column("作者/标题", style="dim")
            table.add_column("状态", justify="center")
            table.add_column("保存路径", style="green")
            
            for res in all_results:
                table.add_row(
                    f"{res['author']}\n[dim]{res['title'][:20]}[/dim]",
                    res['status'],
                    res['path']
                )
            
            console.print(table)
            console.print("\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass