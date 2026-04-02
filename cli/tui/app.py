"""
app.py - Stage 1 Textual shell for zhihu interactive mode

This stage only provides a centered, resize-safe full-screen shell and a
clear fallback path to the legacy interactive workflow.
"""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static


class StatusPill(Static):
    """Compact status tile."""


class ZhihuInteractiveShell(App[None]):
    """Stage 1 shell for the rebuilt interactive experience."""

    CSS_PATH = "theme.tcss"
    TITLE = "zhihu interactive"
    SUB_TITLE = "Zhihu Archive"

    BINDINGS = [
        ("q", "quit", "退出"),
        ("escape", "quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("ZHIHU ARCHIVE", id="eyebrow"),
            Static("知乎归档台", id="title"),
            Static("把回答、问题与专栏保存为 Markdown 和本地索引", id="subtitle"),
            id="hero",
        )
        yield Horizontal(
            StatusPill("Cookie\n已就绪", classes="status-pill"),
            StatusPill("存储\nMarkdown / SQLite", classes="status-pill"),
            StatusPill("模式\n全屏 TUI", classes="status-pill"),
            id="status-row",
        )
        yield Vertical(
            Static("新交互工作台搭建中。当前阶段只验证全屏架构、居中布局和缩放重绘。", classes="callout"),
            Static("如需继续使用旧版流程，请执行：zhihu interactive --legacy", classes="callout dim"),
            Static("按 q 或 Esc 退出。", classes="callout dim"),
            id="hint",
        )


def launch_tui() -> None:
    """Run the stage-1 Textual shell."""
    ZhihuInteractiveShell().run()
