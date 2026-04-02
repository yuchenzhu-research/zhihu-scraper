"""
state.py - Stage 2 home snapshot for the interactive TUI

Builds a lightweight, serializable view model for the Textual home screen.
"""

from dataclasses import dataclass

from core.config import get_config
from core.cookie_manager import has_available_cookie_sources


@dataclass(frozen=True)
class StatusItem:
    """Single status pill shown on the TUI home screen."""

    label: str
    value: str
    tone: str


@dataclass(frozen=True)
class HomeSnapshot:
    """Static stage-2 home screen snapshot."""

    eyebrow: str
    title: str
    subtitle: str
    statuses: tuple[StatusItem, ...]
    notes: tuple[str, ...]


def build_home_snapshot() -> HomeSnapshot:
    """Build the current home snapshot from runtime configuration."""
    cfg = get_config()
    cookie_ready = has_available_cookie_sources(
        cfg.zhihu.cookies_file,
        cfg.zhihu.cookies_pool_dir,
    )

    browser_mode = "无头" if cfg.zhihu.browser.headless else "显示窗口"
    return HomeSnapshot(
        eyebrow="ZHIHU ARCHIVE",
        title="知乎归档台",
        subtitle="一个围绕抓取、归档与后续检索而设计的全屏终端工作台",
        statuses=(
            StatusItem("Cookie", "已就绪" if cookie_ready else "未检测到", "success" if cookie_ready else "warn"),
            StatusItem("浏览器", browser_mode, "accent" if not cfg.zhihu.browser.headless else "muted"),
            StatusItem("旧版回退", "--legacy", "muted"),
        ),
        notes=(
            "这一阶段专注于稳定的全屏首页布局、居中结构和缩放重排。",
            "旧版 Rich / questionary 流程仍然可用：zhihu interactive --legacy",
            "下一阶段会接入输入栏、任务状态和最小抓取闭环。",
        ),
    )
