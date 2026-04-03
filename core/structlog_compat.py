"""
structlog_compat.py - Optional structlog compatibility layer

Provides a tiny fallback logger when structlog isn't installed, so the CLI can
still start and print actionable install guidance instead of crashing at import
time.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

try:
    import structlog as _structlog  # type: ignore

    structlog = _structlog
    BoundLoggerBase = _structlog.BoundLoggerBase
    STRUCTLOG_AVAILABLE = True
except ModuleNotFoundError:
    STRUCTLOG_AVAILABLE = False

    class BoundLoggerBase:
        """Minimal stand-in for structlog's bound logger base."""

    class FallbackBoundLogger(BoundLoggerBase):
        """Compat logger that accepts structlog-style event + kwargs calls."""

        def __init__(self, name: str = "zhihu-scraper") -> None:
            self._logger = logging.getLogger(name)

        def bind(self, **_: Any) -> "FallbackBoundLogger":
            return self

        def debug(self, event: str, **kwargs: Any) -> None:
            self._log("debug", event, **kwargs)

        def info(self, event: str, **kwargs: Any) -> None:
            self._log("info", event, **kwargs)

        def warning(self, event: str, **kwargs: Any) -> None:
            self._log("warning", event, **kwargs)

        def error(self, event: str, **kwargs: Any) -> None:
            self._log("error", event, **kwargs)

        def exception(self, event: str, **kwargs: Any) -> None:
            self._log("exception", event, **kwargs)

        def _log(self, level: str, event: str, **kwargs: Any) -> None:
            message = event
            if kwargs:
                extras = " ".join(f"{key}={value!r}" for key, value in kwargs.items())
                message = f"{event} {extras}"
            getattr(self._logger, level)(message)

    class _StructlogShim:
        BoundLoggerBase = BoundLoggerBase

        @staticmethod
        def get_logger(name: str = "zhihu-scraper") -> FallbackBoundLogger:
            return FallbackBoundLogger(name)

        @staticmethod
        def configure(**_: Any) -> None:
            return None

    structlog = _StructlogShim()


def setup_fallback_logging(level_name: str, *, log_file: str | None = None) -> None:
    """Configure stdlib logging for environments without structlog."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    structlog.get_logger("zhihu-scraper").warning(
        "structlog_missing",
        message="structlog is not installed; falling back to stdlib logging. Run `pip install -e .` to restore full logging.",
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )
