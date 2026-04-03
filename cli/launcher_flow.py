"""
launcher_flow.py - Home menu and onboarding flow

Moves the interactive home menu and first-run onboarding out of cli/app.py so
the top-level command file stays focused on command definitions and orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


@dataclass(frozen=True)
class LauncherCommands:
    fetch: Callable[..., None]
    creator: Callable[..., None]
    batch: Callable[..., None]
    monitor: Callable[..., None]
    query: Callable[..., None]
    interactive: Callable[..., None]
    check: Callable[..., None]
    manual: Callable[..., None]


@dataclass(frozen=True)
class LauncherRuntime:
    console: Console
    get_cfg: Callable[[], Any]
    get_questionary: Callable[[], Any]
    get_default_output_dir: Callable[[], Path]
    get_default_browser_headless: Callable[[], bool]
    resolve_project_path: Callable[[str], Path]
    commands: LauncherCommands


def _launcher_style(runtime: LauncherRuntime):
    """Lazy questionary style builder / 延迟构建 questionary 主题"""
    Style = runtime.get_questionary().Style
    return Style([
        ("question", "fg:#00C8FF bold"),
        ("answer", "fg:#FFFFFF"),
        ("pointer", "fg:#FF1493 bold"),
        ("highlighted", "fg:#00C8FF bold"),
        ("selected", "fg:#00FF55"),
        ("instruction", "fg:#777777"),
        ("text", "fg:#FFFFFF"),
    ])


def _input_positive_int(runtime: LauncherRuntime, prompt: str, default: str) -> int:
    questionary = runtime.get_questionary()
    value = questionary.text(
        prompt,
        default=default,
        validate=lambda text: text.isdigit() and int(text) > 0 or "请输入正整数",
        style=_launcher_style(runtime),
    ).ask()
    return int(value or default)


def _input_non_negative_int(runtime: LauncherRuntime, prompt: str, default: str) -> int:
    questionary = runtime.get_questionary()
    value = questionary.text(
        prompt,
        default=default,
        validate=lambda text: text.isdigit() or "请输入非负整数",
        style=_launcher_style(runtime),
    ).ask()
    return int(value or default)


def _collect_fetch_options(runtime: LauncherRuntime, url: str) -> dict[str, Any]:
    """Collect quick-fetch options from launcher / 从首页菜单收集抓取参数"""
    questionary = runtime.get_questionary()

    limit: Optional[int] = None
    if "/question/" in url and "/answer/" not in url:
        limit = _input_positive_int(runtime, "问题页抓取多少条回答？", "10")

    selections = questionary.checkbox(
        "附加设置：",
        choices=[
            questionary.Choice("下载图片", value="images", checked=True),
        ],
        style=_launcher_style(runtime),
    ).ask() or []

    if "zhuanlan.zhihu.com" in url:
        rprint("[dim]ℹ️ 如果专栏普通抓取失败，程序会自动启用浏览器补救。[/dim]")

    return {
        "limit": limit,
        "no_images": "images" not in selections,
        "headless": runtime.get_default_browser_headless(),
    }


def _render_launcher_header(runtime: LauncherRuntime) -> None:
    """Print compact launcher banner / 打印精简首页横幅"""
    cfg = runtime.get_cfg()
    default_output_dir = runtime.get_default_output_dir()
    from core.cookie_manager import has_available_cookie_sources

    cookie_status = "已就绪" if has_available_cookie_sources(cfg.zhihu.cookies_file, cfg.zhihu.cookies_pool_dir) else "需要 Cookie"
    browser_status = "后台运行" if cfg.zhihu.browser.headless else "显示窗口"
    content = Text.assemble(
        ("知乎归档", "bold cyan"),
        ("  ·  首页 launcher\n", "white"),
        ("输出目录: ", "bold magenta"),
        (f"{default_output_dir}", "white"),
        ("  |  登录状态: ", "bold magenta"),
        (cookie_status, "white"),
        ("  |  浏览器补救: ", "bold magenta"),
        (browser_status, "white"),
        ("\n主路径: ", "bold magenta"),
        ("首页 launcher -> Textual TUI（推荐）", "white"),
    )
    runtime.console.print(Panel(content, border_style="cyan", expand=False))


def run_onboard_flow(runtime: LauncherRuntime, *, from_command: bool = False) -> None:
    """Minimal onboarding flow inspired by guided CLIs / 最小 onboarding 引导"""
    questionary = runtime.get_questionary()
    from core.cookie_manager import has_available_cookie_sources, resolve_cookie_file_path

    cfg = runtime.get_cfg()
    configured_cookie_path = runtime.resolve_project_path(cfg.zhihu.cookies_file)
    active_cookie_path = resolve_cookie_file_path(cfg.zhihu.cookies_file)
    runtime.console.print(Panel(
        Text(
            "首次使用向导\n\n"
            "1. 先运行 ./install.sh 安装环境\n"
            f"2. 在 {configured_cookie_path} 中填入自己的 Cookie\n"
            "3. 执行一次环境检查\n"
            "4. `zhihu` 会打开首页 launcher\n"
            "5. `zhihu interactive` 会直达推荐的 Textual TUI\n"
            "6. `zhihu interactive --legacy` 仅用于兼容回退",
            justify="left",
        ),
        border_style="magenta",
        title="🚀 首次使用向导",
        expand=False,
    ))

    cookie_ready = has_available_cookie_sources(cfg.zhihu.cookies_file, cfg.zhihu.cookies_pool_dir)
    rprint(f"📄 配置文件: [cyan]{Path(__file__).parent.parent / 'config.yaml'}[/]")
    rprint(f"🍪 Cookie 文件: [cyan]{configured_cookie_path}[/] {'✅' if cookie_ready else '⚠️'}")
    if active_cookie_path != configured_cookie_path:
        rprint(f"↩️ 兼容旧路径: [cyan]{active_cookie_path}[/]")
    rprint("🧰 安装入口: [cyan]./install.sh[/]")
    rprint("🔁 重建环境: [cyan]./install.sh --recreate[/]")

    should_check = questionary.confirm(
        "现在执行环境检查吗？",
        default=True,
        style=_launcher_style(runtime),
    ).ask()
    if should_check:
        runtime.commands.check()

    should_open_home = questionary.confirm(
        "现在进入首页菜单吗？",
        default=not from_command,
        style=_launcher_style(runtime),
    ).ask()
    if should_open_home:
        run_launcher(runtime)


def run_launcher(runtime: LauncherRuntime) -> None:
    """Default home launcher / 默认首页 launcher"""
    questionary = runtime.get_questionary()
    default_output_dir = runtime.get_default_output_dir()
    default_headless = runtime.get_default_browser_headless()

    def run_action(func, **kwargs) -> None:
        try:
            func(**kwargs)
        except SystemExit:
            return

    _render_launcher_header(runtime)

    while True:
        choice = questionary.select(
            "请选择操作：",
            choices=[
                questionary.Choice("快速抓取", value="fetch"),
                questionary.Choice("作者抓取", value="creator"),
                questionary.Choice("批量抓取", value="batch"),
                questionary.Choice("收藏夹监控", value="monitor"),
                questionary.Choice("搜索本地数据库", value="query"),
                questionary.Choice("Textual TUI 归档工作台（推荐）", value="interactive"),
                questionary.Choice("首次使用向导", value="onboard"),
                questionary.Choice("环境检查", value="check"),
                questionary.Choice("查看说明书", value="manual"),
                questionary.Choice("退出", value="exit"),
            ],
            use_shortcuts=False,
            style=_launcher_style(runtime),
        ).ask()

        if not choice or choice == "exit":
            return

        if choice == "fetch":
            url = questionary.text(
                "输入知乎链接或一段包含链接的文字：",
                style=_launcher_style(runtime),
            ).ask()
            if not url:
                continue
            options = _collect_fetch_options(runtime, url)
            run_action(
                runtime.commands.fetch,
                url=url,
                output=default_output_dir,
                limit=options["limit"],
                no_images=options["no_images"],
                headless=options["headless"],
            )
            continue

        if choice == "creator":
            creator_input = questionary.text(
                "输入作者主页 URL 或 url_token：",
                style=_launcher_style(runtime),
            ).ask()
            if not creator_input:
                continue
            answers = _input_non_negative_int(runtime, "抓多少条回答？", "10")
            articles = _input_non_negative_int(runtime, "抓多少篇专栏？", "5")
            selections = questionary.checkbox(
                "附加设置：",
                choices=[
                    questionary.Choice("下载图片", value="images", checked=True),
                ],
                style=_launcher_style(runtime),
            ).ask() or []
            run_action(
                runtime.commands.creator,
                creator=creator_input,
                output=default_output_dir,
                answers=answers,
                articles=articles,
                no_images="images" not in selections,
            )
            continue

        if choice == "batch":
            input_file = questionary.path(
                "输入 URL 列表文件路径：",
                only_files=True,
                style=_launcher_style(runtime),
            ).ask()
            if not input_file:
                continue
            concurrency = _input_positive_int(runtime, "并发数：", "4")
            selections = questionary.checkbox(
                "附加设置：",
                choices=[
                    questionary.Choice("下载图片", value="images", checked=True),
                ],
                style=_launcher_style(runtime),
            ).ask() or []
            run_action(
                runtime.commands.batch,
                input_file=Path(input_file),
                output=default_output_dir,
                concurrency=concurrency,
                no_images="images" not in selections,
                headless=default_headless,
            )
            continue

        if choice == "monitor":
            collection_id = questionary.text(
                "输入收藏夹 ID：",
                style=_launcher_style(runtime),
            ).ask()
            if not collection_id:
                continue
            concurrency = _input_positive_int(runtime, "并发数：", "4")
            selections = questionary.checkbox(
                "附加设置：",
                choices=[
                    questionary.Choice("下载图片", value="images", checked=True),
                ],
                style=_launcher_style(runtime),
            ).ask() or []
            run_action(
                runtime.commands.monitor,
                collection_id=collection_id.strip(),
                output=default_output_dir,
                concurrency=concurrency,
                no_images="images" not in selections,
                headless=default_headless,
            )
            continue

        if choice == "query":
            keyword = questionary.text(
                "输入搜索关键词：",
                style=_launcher_style(runtime),
            ).ask()
            if not keyword:
                continue
            limit = _input_positive_int(runtime, "结果数量：", "10")
            run_action(runtime.commands.query, keyword=keyword, limit=limit, data_dir=str(default_output_dir))
            continue

        if choice == "interactive":
            run_action(runtime.commands.interactive)
            continue

        if choice == "onboard":
            run_onboard_flow(runtime)
            continue

        if choice == "check":
            run_action(runtime.commands.check)
            continue

        if choice == "manual":
            run_action(runtime.commands.manual)
            continue
