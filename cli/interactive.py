"""
interactive.py - Interactive TUI launcher

Routes the `zhihu interactive` command to the new full-screen terminal app.

================================================================================
interactive.py — 交互式 TUI 启动入口

把 `zhihu interactive` 命令转发到新的全屏终端应用。
================================================================================
"""

from cli.tui.app import launch_tui


def run_interactive() -> None:
    """Launch the new interactive TUI shell."""
    launch_tui()
