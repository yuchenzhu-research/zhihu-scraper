"""
humanizer.py - Human behavior simulator.

Random delays to simulate human operations to reduce blocking risk.
Extracted from config.py to enforce single responsibility.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from random import uniform
from typing import Optional

from .config_runtime import get_config
from .config_schema import HumanizeConfig


class Humanizer:
    """
    Human behavior simulator - random delays to simulate human operations.
    人类行为模拟器 - 随机延迟以模拟真人操作。
    """

    def __init__(self, config: Optional[HumanizeConfig] = None):
        self._config = config

    @property
    def config(self) -> HumanizeConfig:
        """
        Get configuration, singleton pattern to avoid repeated loading.
        获取配置，单例模式避免重复加载。
        """
        if self._config is None:
            try:
                cfg = get_config()
                self._config = cfg.crawler.humanize
            except Exception:
                self._config = HumanizeConfig()
        return self._config

    def random_delay(self, min_delay: Optional[float] = None, max_delay: Optional[float] = None) -> asyncio.sleep:
        """
        Random delay simulating human request interval.
        随机延迟，模拟人类请求间隔。
        """
        if not self.config.enabled:
            return

        min_d = min_delay if min_delay is not None else self.config.min_delay
        max_d = max_delay if max_delay is not None else self.config.max_delay

        delay = uniform(min_d, max_d)
        return asyncio.sleep(delay)

    async def page_load(self) -> None:
        """
        Wait after page load, simulating reading/rendering time.
        页面加载后等待，模拟阅读/渲染时间。
        """
        if not self.config.enabled:
            return

        await asyncio.sleep(self.config.page_load_delay)

    async def scroll(self) -> None:
        """
        Wait after scroll, simulating content loading.
        滚动后等待，模拟内容加载。
        """
        if not self.config.enabled:
            return

        await asyncio.sleep(self.config.scroll_delay)

    async def before_action(self, action: str = "request") -> None:
        """
        Wait before action.
        操作前等待。
        """
        if not self.config.enabled:
            return

        delays = {
            "request": (self.config.min_delay, self.config.max_delay),
            "click": (0.2, 0.5),
            "scroll": (self.config.scroll_delay, self.config.scroll_delay + 0.3),
            "type": (0.05, 0.15),
        }

        min_d, max_d = delays.get(action, delays["request"])
        await asyncio.sleep(uniform(min_d, max_d))


_humanizer: Optional[Humanizer] = None


def get_humanizer() -> Humanizer:
    """
    Get global Humanizer instance.
    获取全局 Humanizer 实例。
    """
    global _humanizer
    if _humanizer is None:
        try:
            cfg = get_config()
            _humanizer = Humanizer(cfg.crawler.humanize)
        except Exception:
            _humanizer = Humanizer()
    return _humanizer


@asynccontextmanager
async def humanize(action: str = "request"):
    """
    Context manager form of delay.
    上下文管理器形式的延迟。
    """
    h = get_humanizer()
    await h.before_action(action)
    yield
