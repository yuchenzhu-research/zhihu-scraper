"""
cookie_manager.py - Multi-Account Cookie Pool Manager

Responsible for loading, validating, and rotating multiple sets of Zhihu cookies.
Supports cookies.json and cookie_pool/*.json formats.
Supports automatic random switching when encountering API 403 (rate limiting),
greatly improving survival rate for batch tasks.

================================================================================
cookie_manager.py — 多账号 Cookie 轮询池

负责加载、验证和轮换多组知乎 Cookies。支持 `cookies.json` 和 `cookie_pool/*.json`。
支持在遇到 API 403 (风控) 时随机切换号源池，大幅提升批量任务的存活率。
================================================================================
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Optional

from .config import get_config, get_logger, resolve_project_path


PLACEHOLDER_COOKIE_VALUES = {
    "YOUR_COOKIE_HERE",
    "YOUR_Z_C0_HERE",
    "YOUR_D_C0_HERE",
}


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


class CookieManager:
    """
    Chinese: 知乎多账号防风控 Cookie 管理器
    English: Zhihu anti-rate-limiting multi-account Cookie manager
    """

    def __init__(self, base_cookies_path: Optional[str] = None, pool_dir: Optional[str] = None):
        cfg = get_config()
        self.log = get_logger()
        self.base_path = resolve_project_path(base_cookies_path or cfg.zhihu.cookies_file)
        self.pool_dir = resolve_project_path(pool_dir or "cookie_pool")
        self.sessions: List[Dict[str, str]] = []
        self._current_index = -1

        self.reload_sessions()

    def reload_sessions(self) -> None:
        """
        Reload all cookie templates from filesystem
        从文件系统重新加载所有 Cookie 模板
        """
        self.sessions.clear()

        # 1. Load default cookies.json
        # 加载默认 cookies.json
        base_session = self._parse_json_file(self.base_path)
        if base_session and self._is_valid_session(base_session):
            self.sessions.append(base_session)

        # 2. Load cookie_pool/**/*.json
        # 加载 cookie_pool/**/*.json
        if self.pool_dir.exists() and self.pool_dir.is_dir():
            for filepath in self.pool_dir.glob("*.json"):
                session = self._parse_json_file(filepath)
                if session and self._is_valid_session(session) and session not in self.sessions:
                    self.sessions.append(session)

        self.log.info("cookie_manager_loaded", total_sessions=len(self.sessions))

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


# Global singleton instance (used in scenarios not involving threaded concurrency isolation)
# 全局单例实例化 (通常用在不涉及多线程并发隔离的场景)
cookie_manager = CookieManager()
