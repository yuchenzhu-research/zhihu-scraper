"""
config_view.py - Presentation helpers for CLI config inspection.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from rich.panel import Panel
from rich.text import Text

from core.config import Config
from core.cookie_manager import RuntimePathResolution


PathResolver = Callable[[str], Path]
CookiePathDescriber = Callable[[str], RuntimePathResolution]


@dataclass(frozen=True)
class ConfigDisplaySnapshot:
    """Resolved values shown by `zhihu config --show`."""

    config_path: Path
    output_directory: str
    configured_cookie_path: Path
    active_cookie_path: Path
    configured_pool_dir: Path
    active_pool_dir: Path
    cookie_file_legacy_fallback: bool
    cookie_pool_legacy_fallback: bool
    log_path: str
    log_level: str
    browser_mode: str
    retry_attempts: int
    image_concurrency: int
    cookie_rotation: str


def build_config_snapshot(
    *,
    cfg: Config,
    config_path: Path,
    resolve_project_path: PathResolver,
    describe_cookie_file_path: CookiePathDescriber,
    describe_cookie_pool_dir: CookiePathDescriber,
) -> ConfigDisplaySnapshot:
    """Build a normalized config snapshot for CLI rendering."""
    cookie_file = describe_cookie_file_path(cfg.zhihu.cookies_file)
    cookie_pool = describe_cookie_pool_dir(cfg.zhihu.cookies_pool_dir)
    return ConfigDisplaySnapshot(
        config_path=config_path,
        output_directory=cfg.output.directory,
        configured_cookie_path=cookie_file.configured_path,
        active_cookie_path=cookie_file.active_path,
        configured_pool_dir=cookie_pool.configured_path,
        active_pool_dir=cookie_pool.active_path,
        cookie_file_legacy_fallback=cookie_file.used_legacy_fallback,
        cookie_pool_legacy_fallback=cookie_pool.used_legacy_fallback,
        log_path=str(resolve_project_path(cfg.logging.file)) if cfg.logging.file else "disabled / 已关闭",
        log_level=cfg.logging.level,
        browser_mode="Headless / 无头" if cfg.zhihu.browser.headless else "Visible / 有头",
        retry_attempts=cfg.crawler.retry.max_attempts,
        image_concurrency=cfg.crawler.images.concurrency,
        cookie_rotation="Enabled / 启用" if cfg.zhihu.cookies_required else "Disabled / 禁用",
    )


def render_config_panel(snapshot: ConfigDisplaySnapshot) -> Panel:
    """Render the Rich config panel from a normalized snapshot."""
    cookie_path_status = "Canonical .local runtime paths / 使用推荐的 .local 运行目录"
    if snapshot.cookie_file_legacy_fallback and snapshot.cookie_pool_legacy_fallback:
        cookie_path_status = "Legacy repo-root fallback active (cookie file + pool) / 当前命中仓库根目录旧 Cookie 文件与号源池"
    elif snapshot.cookie_file_legacy_fallback:
        cookie_path_status = "Legacy repo-root fallback active (cookie file) / 当前命中仓库根目录旧 Cookie 文件"
    elif snapshot.cookie_pool_legacy_fallback:
        cookie_path_status = "Legacy repo-root fallback active (cookie pool) / 当前命中仓库根目录旧 Cookie 池"

    body = Text(
        f"""
[b]配置路径 (Config Path):[/] {snapshot.config_path}

[b]输出目录 (Output Directory):[/] {snapshot.output_directory}
[b]Cookie文件 (Configured Cookie File):[/] {snapshot.configured_cookie_path}
[b]当前生效Cookie (Active Cookie):[/] {snapshot.active_cookie_path}
[b]Cookie池目录 (Configured Cookie Pool):[/] {snapshot.configured_pool_dir}
[b]当前生效Cookie池 (Active Cookie Pool):[/] {snapshot.active_pool_dir}
[b]Cookie路径状态 (Cookie Path Status):[/] {cookie_path_status}
[b]日志文件 (Log File):[/] {snapshot.log_path}
[b]日志级别 (Log Level):[/] {snapshot.log_level}
[b]浏览器 (Browser):[/] {snapshot.browser_mode}
[b]重试次数 (Retry Attempts):[/] {snapshot.retry_attempts}
[b]图片并发 (Image Concurrency):[/] {snapshot.image_concurrency}
[b]Cookie轮换 (Cookie Rotation):[/] {snapshot.cookie_rotation}
        """.strip(),
        justify="left",
    )
    return Panel(
        body,
        title="🛠️ Current Configuration / 当前配置",
        border_style="cyan",
    )
