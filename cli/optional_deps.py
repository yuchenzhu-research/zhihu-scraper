"""
optional_deps.py - Optional CLI dependency loaders

Keeps user-facing guidance for optional terminal dependencies out of cli/app.py
so automated tests and non-interactive runs can stay quieter.
"""

from __future__ import annotations

import importlib
import sys
from typing import Optional

import typer
from rich import print as rprint


QUESTIONARY_GUIDANCE_LINES = (
    "[bold yellow]⚠️ Missing optional TTY dependency / 缺少交互式终端依赖：questionary[/bold yellow]",
    "请重新同步当前分支依赖，例如：",
    "[cyan]pip install -e .[/cyan]  或  [cyan]./install.sh --recreate[/cyan]",
)


def _should_emit_guidance(explicit: Optional[bool]) -> bool:
    """Decide whether optional dependency guidance should be printed."""
    if explicit is not None:
        return explicit
    return bool(getattr(sys.stderr, "isatty", lambda: False)())


def get_questionary(*, emit_guidance: Optional[bool] = None):
    """
    Import questionary lazily with actionable guidance.
    延迟导入 questionary，并只在交互式终端中输出提示。
    """
    try:
        return importlib.import_module("questionary")
    except ModuleNotFoundError as exc:
        if _should_emit_guidance(emit_guidance):
            for line in QUESTIONARY_GUIDANCE_LINES:
                rprint(line)
        raise typer.Exit(code=1) from exc
