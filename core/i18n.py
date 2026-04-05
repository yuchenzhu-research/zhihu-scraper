"""
i18n.py - 国际化服务层

提供基于 JSON 语言包的字符串翻译能力。
支持运行时切换语言、占位符替换和 key 缺失回退。

================================================================================
i18n.py — Internationalization Service

Provides locale-aware string translation backed by JSON locale files.
Supports runtime language switching, placeholder substitution, and fallback.
================================================================================
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LANG = "zh"

_current_lang: str = DEFAULT_LANG


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_language(lang: str) -> None:
    """Set the active UI language (e.g. 'zh', 'en', 'zh_hant')."""
    global _current_lang
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANG
    _current_lang = lang
    _load_locale.cache_clear()


def get_language() -> str:
    """Return the currently active language code."""
    return _current_lang


def t(key: str, **kwargs: Any) -> str:
    """Translate *key* using the active locale.

    Supports ``str.format`` style placeholders::

        t("draft.running.title", current=1, total=5)
        # → "正在归档 1/5"  (zh)
        # → "Archiving 1/5" (en)

    If *key* is missing from both the active locale and the fallback,
    the raw key string is returned unchanged.
    """
    locale = _load_locale(_current_lang)
    template = locale.get(key)
    if template is None:
        # Fallback to default language
        fallback = _load_locale(DEFAULT_LANG)
        template = fallback.get(key, key)
    return template.format(**kwargs) if kwargs else template


# ---------------------------------------------------------------------------
# Language metadata (used by the TUI language selector)
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: dict[str, str] = {
    "zh": "简体中文",
    "en": "English",
    "zh_hant": "繁體中文",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4)
def _load_locale(lang: str) -> dict[str, str]:
    """Load and cache a JSON locale file."""
    path = LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        path = LOCALES_DIR / f"{DEFAULT_LANG}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
