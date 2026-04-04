"""
cookie_manager.py - Multi-Account Cookie Pool Manager

Responsible for loading, validating, and rotating multiple sets of Zhihu cookies.
Prefers .local/cookies.json and .local/cookie_pool/*.json while keeping backward
compatibility with legacy repository-root paths.
Supports automatic random switching when encountering API 403 (rate limiting),
greatly improving survival rate for batch tasks.

================================================================================
cookie_manager.py — 多账号 Cookie 轮询池

负责加载、验证和轮换多组知乎 Cookies。优先使用 `.local/cookies.json`
和 `.local/cookie_pool/*.json`，同时兼容历史的仓库根目录路径。
支持在遇到 API 403 (风控) 时随机切换号源池，大幅提升批量任务的存活率。
================================================================================
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional

from .config import get_config, get_logger, resolve_project_path
from .runtime_paths import (
    DEFAULT_COOKIE_FILE,
    DEFAULT_COOKIE_POOL_DIR,
    LEGACY_COOKIE_FILE,
    LEGACY_COOKIE_POOL_DIR,
)


PLACEHOLDER_COOKIE_VALUES = {
    "YOUR_COOKIE_HERE",
    "YOUR_Z_C0_HERE",
    "YOUR_D_C0_HERE",
}


@dataclass(frozen=True)
class RuntimePathResolution:
    """
    Resolved runtime path plus legacy-fallback diagnostics.
    运行时路径解析结果，以及旧路径兼容诊断。
    """

    configured_path: Path
    active_path: Path
    legacy_path: Path
    used_legacy_fallback: bool


def is_placeholder_cookie_value(value: Optional[str]) -> bool:
    """
    Check whether a cookie value is still a template placeholder
    检查 Cookie 值是否仍是模板占位符
    """
    if not value:
        return True

    value = value.strip()
    return value in PLACEHOLDER_COOKIE_VALUES or (value.startswith("YOUR_") and value.endswith("_HERE"))


def load_cookie_dict(path: Path) -> Dict[str, str]:
    """
    Parse a cookie file and return non-placeholder key/value pairs
    解析 Cookie 文件并返回过滤掉占位符后的键值对
    """
    cookies_dict: Dict[str, str] = {}
    if not path.exists():
        return cookies_dict

    with open(path, "r", encoding="utf-8") as f:
        cookies_list = json.load(f)
        if isinstance(cookies_list, list):
            for cookie in cookies_list:
                name = cookie.get("name")
                value = cookie.get("value")
                if name and not is_placeholder_cookie_value(value):
                    cookies_dict[name] = value.strip()
        elif isinstance(cookies_list, dict):
            for name, value in cookies_list.items():
                if name and not is_placeholder_cookie_value(value):
                    cookies_dict[name] = value.strip()

    return cookies_dict


def has_real_cookie_values(path: Path) -> bool:
    """
    Check whether a cookie file contains at least one real Zhihu session key
    检查 Cookie 文件是否至少包含一个真实的知乎会话键值
    """
    session = load_cookie_dict(path)
    return "z_c0" in session or "d_c0" in session


def count_available_cookie_sources(
    base_cookies_path: Optional[str] = None,
    pool_dir: Optional[str] = None,
) -> int:
    """
    Count valid cookie sources across the primary file and pool directory.
    统计主 Cookie 文件与 Cookie 池目录中的有效号源数量。
    """
    total = 0

    base_path = resolve_cookie_file_path(base_cookies_path)
    if has_real_cookie_values(base_path):
        total += 1

    pool_path = resolve_cookie_pool_dir(pool_dir)
    if pool_path.exists() and pool_path.is_dir():
        for filepath in pool_path.glob("*.json"):
            if has_real_cookie_values(filepath):
                total += 1

    return total


def has_available_cookie_sources(
    base_cookies_path: Optional[str] = None,
    pool_dir: Optional[str] = None,
) -> bool:
    """
    Check whether at least one valid cookie source is available.
    检查是否至少存在一个有效 Cookie 号源。
    """
    return count_available_cookie_sources(base_cookies_path, pool_dir) > 0


def _resolve_runtime_path(configured: Path, *, default_path: Path, legacy_path: Path) -> RuntimePathResolution:
    """
    Keep old repo-root paths working when users upgrade in place, while exposing
    whether the legacy fallback was actually used.
    在用户原地升级时继续兼容旧的仓库根目录路径，同时暴露是否真实命中了旧路径兼容。
    """
    default_abs = resolve_project_path(default_path)
    legacy_abs = resolve_project_path(legacy_path)

    use_legacy = configured == default_abs and not configured.exists() and legacy_abs.exists()
    return RuntimePathResolution(
        configured_path=configured,
        active_path=legacy_abs if use_legacy else configured,
        legacy_path=legacy_abs,
        used_legacy_fallback=use_legacy,
    )


def describe_cookie_file_path(configured_path: Optional[str] = None) -> RuntimePathResolution:
    """
    Resolve the cookie file path and report whether legacy fallback is active.
    解析 Cookie 文件路径，并报告是否命中了旧路径兼容。
    """
    cfg = get_config()
    configured = resolve_project_path(configured_path or cfg.zhihu.cookies_file)
    return _resolve_runtime_path(
        configured,
        default_path=DEFAULT_COOKIE_FILE,
        legacy_path=LEGACY_COOKIE_FILE,
    )


def describe_cookie_pool_dir(configured_path: Optional[str] = None) -> RuntimePathResolution:
    """
    Resolve the cookie pool directory and report whether legacy fallback is active.
    解析 Cookie 池目录，并报告是否命中了旧路径兼容。
    """
    cfg = get_config()
    configured = resolve_project_path(configured_path or cfg.zhihu.cookies_pool_dir)
    return _resolve_runtime_path(
        configured,
        default_path=DEFAULT_COOKIE_POOL_DIR,
        legacy_path=LEGACY_COOKIE_POOL_DIR,
    )


def resolve_cookie_file_path(configured_path: Optional[str] = None) -> Path:
    """
    Resolve the active cookie file path with legacy fallback.
    解析当前生效的 Cookie 文件路径，并兼容旧路径。
    """
    return describe_cookie_file_path(configured_path).active_path


def resolve_cookie_pool_dir(configured_path: Optional[str] = None) -> Path:
    """
    Resolve the active cookie pool directory with legacy fallback.
    解析当前生效的 Cookie 池目录，并兼容旧路径。
    """
    return describe_cookie_pool_dir(configured_path).active_path


class CookieManager:
    """
    Chinese: 知乎多账号防风控 Cookie 管理器
    English: Zhihu anti-rate-limiting multi-account Cookie manager
    """

    def __init__(self, base_cookies_path: Optional[str] = None, pool_dir: Optional[str] = None):
        self.log = get_logger()
        self.base_path = resolve_cookie_file_path(base_cookies_path)
        self.pool_dir = resolve_cookie_pool_dir(pool_dir)
        self.sessions: List[Dict[str, str]] = []
        self._current_index = -1

        self.reload_sessions()

    def reload_sessions(self) -> None:
        """
        Reload all cookie templates from filesystem
        从文件系统重新加载所有 Cookie 模板
        """
        self.sessions.clear()

        # 1. Load primary cookie file
        # 加载主 Cookie 文件
        base_session = self._parse_json_file(self.base_path)
        if base_session and self._is_valid_session(base_session):
            self.sessions.append(base_session)

        # 2. Load cookie pool directory
        # 加载 Cookie 池目录
        if self.pool_dir.exists() and self.pool_dir.is_dir():
            for filepath in self.pool_dir.glob("*.json"):
                session = self._parse_json_file(filepath)
                if session and self._is_valid_session(session) and session not in self.sessions:
                    self.sessions.append(session)

        self.log.info(
            "cookie_manager_loaded",
            total_sessions=len(self.sessions),
            cookie_file=str(self.base_path),
            cookie_pool_dir=str(self.pool_dir),
        )

        # Shuffle to avoid always using the same account
        # 打乱基础顺序，确保不要总是固定死号使用同一个号
        if self.sessions:
            random.shuffle(self.sessions)
            self._current_index = 0

    def _parse_json_file(self, path: Path) -> Dict[str, str]:
        """
        Convert JSON array (Name/Value) to dict, filter out useless placeholders
        将 JSON 数组 (Name/Value) 转换为 dict，过滤无用占位符
        """
        try:
            return load_cookie_dict(path)
        except Exception as e:
            self.log.warning("cookie_parse_failed", file=path.name, error=str(e))
            return {}

    def _is_valid_session(self, session: Dict[str, str]) -> bool:
        """
        Verify if this session has minimum required Zhihu core key-values
        验证此 session 是否拥有最低限度的知乎核心键值
        """
        # z_c0 is Zhihu's required identity token
        # z_c0 是知乎必须的身份令牌基础
        return "z_c0" in session or "d_c0" in session

    def get_current_session(self) -> Optional[Dict[str, str]]:
        """
        Get currently active Cookie Session
        获取当前正在使用的 Cookie Session
        """
        if not self.sessions:
            return None
        return self.sessions[self._current_index]

    def rotate_session(self) -> Optional[Dict[str, str]]:
        """
        Called when encountering 403/rate limiting, actively switch to next account
        当遇到 403/风控时调用，主动轮换到下一个账号
        """
        if not self.sessions:
            self.log.warning("cookie_rotation_failed", reason="池为空")
            return None

        old_index = self._current_index
        self._current_index = (self._current_index + 1) % len(self.sessions)

        # Only print warning when multiple accounts exist
        # 只在有多个账号时打印该警告
        if len(self.sessions) > 1:
            self.log.warning(
                "cookie_session_rotated",
                old_idx=old_index,
                new_idx=self._current_index,
                total=len(self.sessions)
            )

        return self.sessions[self._current_index]

    def has_sessions(self) -> bool:
        """
        Check if there are available accounts in pool
        池内是否有可用账号
        """
        return len(self.sessions) > 0


_cookie_manager: Optional[CookieManager] = None


def get_cookie_manager() -> CookieManager:
    """
    Lazily initialize the cookie manager.
    延迟初始化 Cookie 管理器。
    """
    global _cookie_manager
    if _cookie_manager is None:
        _cookie_manager = CookieManager()
    return _cookie_manager


class _LazyCookieManagerProxy:
    """
    Proxy access to the lazily initialized CookieManager.
    代理转发到延迟初始化的 CookieManager。
    """

    def __getattr__(self, item):
        return getattr(get_cookie_manager(), item)


# Global lazy proxy (used in scenarios not involving threaded concurrency isolation)
# 全局延迟代理实例 (通常用在不涉及多线程并发隔离的场景)
cookie_manager = _LazyCookieManagerProxy()
