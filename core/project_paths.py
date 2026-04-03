"""
project_paths.py - Project-root path helpers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union


def get_project_root() -> Path:
    """Get project root path / 获取项目根目录"""
    return Path(__file__).parent.parent


def resolve_project_path(path: Union[str, Path]) -> Path:
    """Resolve relative paths against project root / 将相对路径解析为项目根目录下的绝对路径"""
    path = Path(path)
    if path.is_absolute():
        return path
    return get_project_root() / path
