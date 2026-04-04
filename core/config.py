"""
config.py - Facade for runtime config, logging, and humanization helpers.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from random import uniform
from typing import Optional

from .config_runtime import ConfigLoader, get_config
from .config_schema import Config, HumanizeConfig, LoggingConfig
from .logging_setup import sanitize_event_dict, setup_logging, summarize_text_for_logs
from .project_paths import get_project_root, resolve_project_path
from .structlog_compat import BoundLoggerBase, structlog


def get_logger(name: str = "zhihu-scraper") -> BoundLoggerBase:
    """
    Get structured logger.
    获取结构化日志记录器。
    """
    return structlog.get_logger(name)


__all__ = [
    "Config",
    "ConfigLoader",
    "LoggingConfig",
    "get_config",
    "get_logger",
    "get_project_root",
    "resolve_project_path",
    "sanitize_event_dict",
    "setup_logging",
    "summarize_text_for_logs",
]
