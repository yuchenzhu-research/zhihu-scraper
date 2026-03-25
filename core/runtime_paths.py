"""
runtime_paths.py - Runtime Path Conventions

Defines the canonical local-only runtime layout used by the project while
keeping compatibility with older repository-root locations.

================================================================================
runtime_paths.py — 运行时路径约定

定义项目推荐使用的本地运行目录布局，同时兼容历史上的仓库根目录路径。
================================================================================
"""

from pathlib import Path


LOCAL_RUNTIME_DIR = Path(".local")

DEFAULT_COOKIE_FILE = LOCAL_RUNTIME_DIR / "cookies.json"
DEFAULT_COOKIE_POOL_DIR = LOCAL_RUNTIME_DIR / "cookie_pool"
DEFAULT_LOG_DIR = LOCAL_RUNTIME_DIR / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "scraper.log"

LEGACY_COOKIE_FILE = Path("cookies.json")
LEGACY_COOKIE_POOL_DIR = Path("cookie_pool")
