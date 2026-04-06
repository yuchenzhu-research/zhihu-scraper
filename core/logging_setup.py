"""
logging_setup.py - Structured logging configuration helpers.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Union

from .config_schema import Config, LoggingConfig
from .project_paths import resolve_project_path
from .structlog_compat import STRUCTLOG_AVAILABLE, setup_fallback_logging, structlog

_SENSITIVE_KEY_MARKERS = (
    "cookie",
    "token",
    "secret",
    "authorization",
    "set-cookie",
    "credential",
    "session",
)

_CONTENT_KEY_MARKERS = (
    "html",
    "content",
    "body",
    "response_preview",
    "response_text",
    "page_preview",
    "page_text",
)

_COOKIE_PAIR_RE = re.compile(r"(?i)\b(z_c0|d_c0)\s*=\s*([^;,\s]+)")
_COOKIE_JSON_RE = re.compile(r'(?i)"(z_c0|d_c0)"\s*:\s*"([^"]+)"')
_AUTHORIZATION_RE = re.compile(
    r"(?i)\bauthorization\b(?:\s*[:=]\s*|\s+)(?:bearer\s+)?([A-Za-z0-9._~+/=-]+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._~+/=-]+)")

_SILENT_CONSOLE = False


def set_silent_console(enabled: bool) -> None:
    """Toggle console logging. Useful for TUI modes. / 切换控制台日志开关，适用于 TUI 模式。"""
    global _SILENT_CONSOLE
    _SILENT_CONSOLE = enabled


def summarize_text_for_logs(value: str, *, kind: str = "text") -> str:
    normalized = value or ""
    digest = hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"<{kind}_redacted len={len(normalized)} sha256={digest}>"


def _mask_inline_secrets(value: str) -> str:
    masked = _COOKIE_PAIR_RE.sub(lambda m: f"{m.group(1)}=<redacted>", value)
    masked = _COOKIE_JSON_RE.sub(lambda m: f'"{m.group(1)}":"<redacted>"', masked)
    masked = _AUTHORIZATION_RE.sub("authorization=<redacted>", masked)
    masked = _BEARER_RE.sub("Bearer <redacted>", masked)
    return masked


def _looks_like_html(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ("<!doctype", "<html", "<body", "</div>", "</script>", "<meta "))


def _sanitize_log_value(key: str, value: Any) -> Any:
    normalized_key = key.lower()

    if isinstance(value, dict):
        return {sub_key: _sanitize_log_value(str(sub_key), sub_value) for sub_key, sub_value in value.items()}

    if isinstance(value, (list, tuple)):
        return [_sanitize_log_value(normalized_key, item) for item in value]

    if not isinstance(value, str):
        return value

    if value.startswith("<") and "_redacted len=" in value and " sha256=" in value and value.endswith(">"):
        return value

    masked = _mask_inline_secrets(value)

    if any(marker in normalized_key for marker in _SENSITIVE_KEY_MARKERS):
        return summarize_text_for_logs(masked, kind=normalized_key.replace("-", "_") or "secret")

    if any(marker in normalized_key for marker in _CONTENT_KEY_MARKERS) or _looks_like_html(masked):
        kind = "html" if _looks_like_html(masked) else "content"
        return summarize_text_for_logs(masked, kind=kind)

    if len(masked) > 300:
        return masked[:300] + f"... <truncated len={len(masked)}>"

    return masked


def sanitize_event_dict(_: Any, __: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _sanitize_log_value(str(key), value) for key, value in event_dict.items()}


def setup_logging(config: Union[Config, LoggingConfig]) -> None:
    """Initialize structured logging system / 初始化结构化日志系统"""
    if isinstance(config, Config):
        log_config = config.logging
    else:
        log_config = config

    import logging

    log_level = getattr(logging, log_config.level.upper(), logging.INFO)
    log_path = resolve_project_path(log_config.file) if log_config.file else None

    if not STRUCTLOG_AVAILABLE:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
        setup_fallback_logging(log_config.level, log_file=str(log_path) if log_path else None)
        return

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        sanitize_event_dict,
    ]

    renderer = structlog.processors.JSONRenderer() if log_config.format == "json" else structlog.dev.ConsoleRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handlers = []
    if not _SILENT_CONSOLE:
        handlers.append(logging.StreamHandler())

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        handler.close()
        root_logger.removeHandler(handler)
    root_logger.setLevel(log_level)

    for handler in handlers:
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
