"""
core/cookie_manager.py — 多账号 Cookie 轮询池

负责加载、验证和轮换多组知乎 Cookies。支持 `cookies.json` 和 `cookie_pool/*.json`。
支持在遇到 API 403 (风控) 时随机切换号源池，大幅提升批量任务的存活率。
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Optional

from .config import get_logger

class CookieManager:
    """知乎多账号防风控 Cookie 管理器"""

    def __init__(self, base_cookies_path: str = "cookies.json", pool_dir: str = "cookie_pool"):
        self.log = get_logger()
        self.base_path = Path(base_cookies_path)
        self.pool_dir = Path(pool_dir)
        self.sessions: List[Dict[str, str]] = []
        self._current_index = -1
        
        self.reload_sessions()

    def reload_sessions(self) -> None:
        """从文件系统重新加载所有 Cookie 模板。"""
        self.sessions.clear()
        
        # 1. 加载默认 cookies.json
        base_session = self._parse_json_file(self.base_path)
        if base_session and self._is_valid_session(base_session):
            self.sessions.append(base_session)

        # 2. 加载 cookie_pool/**/*.json
        if self.pool_dir.exists() and self.pool_dir.is_dir():
            for filepath in self.pool_dir.glob("*.json"):
                session = self._parse_json_file(filepath)
                if session and self._is_valid_session(session) and session not in self.sessions:
                    self.sessions.append(session)

        self.log.info("cookie_manager_loaded", total_sessions=len(self.sessions))
        
        # 打乱基础顺序，确保不要总是固定死号使用同一个号
        if self.sessions:
            random.shuffle(self.sessions)
            self._current_index = 0

    def _parse_json_file(self, path: Path) -> Dict[str, str]:
        """将 JSON 数组 (Name/Value) 转换为 dict，过滤无用占位符。"""
        cookies_dict = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cookies_list = json.load(f)
                    if isinstance(cookies_list, list):
                        for c in cookies_list:
                            name = c.get("name")
                            val = c.get("value")
                            if name and val and val != "YOUR_COOKIE_HERE":
                                cookies_dict[name] = val
                    elif isinstance(cookies_list, dict):
                         # 直接 k:v 格式的支持
                         for k, v in cookies_list.items():
                             if v and v != "YOUR_COOKIE_HERE":
                                 cookies_dict[k] = v
            except Exception as e:
                self.log.warning("cookie_parse_failed", file=path.name, error=str(e))
        return cookies_dict

    def _is_valid_session(self, session: Dict[str, str]) -> bool:
        """验证此 session 是否拥有最低限度的知乎核心键值。"""
        # z_c0 是知乎必须的身份令牌基础
        return "z_c0" in session or "d_c0" in session

    def get_current_session(self) -> Optional[Dict[str, str]]:
        """获取当前正在使用的 Cookie Session。"""
        if not self.sessions:
            return None
        return self.sessions[self._current_index]

    def rotate_session(self) -> Optional[Dict[str, str]]:
        """当遇到 403/风控时调用，主动轮换到下一个账号。"""
        if not self.sessions:
            self.log.warning("cookie_rotation_failed", reason="池为空")
            return None
            
        old_index = self._current_index
        self._current_index = (self._current_index + 1) % len(self.sessions)
        
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
        """池内是否有可用账号。"""
        return len(self.sessions) > 0

# 全局单例实例化 (通常用在不涉及多线程并发隔离的场景)
cookie_manager = CookieManager()
