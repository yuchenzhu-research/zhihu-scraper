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


PathResolver = Callable[[str], Path]


@dataclass(frozen=True)
class ConfigDisplaySnapshot:
    """Resolved values shown by `zhihu config --show`."""

    config_path: Path
    output_directory: str
    configured_cookie_path: Path
    active_cookie_path: Path
    active_pool_dir: Path
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
    resolve_cookie_file_path: Callable[[str], Path],
    resolve_cookie_pool_dir: Callable[[str], Path],
) -> ConfigDisplaySnapshot:
    """Build a normalized config snapshot for CLI rendering."""
    return ConfigDisplaySnapshot(
        config_path=config_path,
        output_directory=cfg.output.directory,
        configured_cookie_path=resolve_project_path(cfg.zhihu.cookies_file),
        active_cookie_path=resolve_cookie_file_path(cfg.zhihu.cookies_file),
        active_pool_dir=resolve_cookie_pool_dir(cfg.zhihu.cookies_pool_dir),
        log_path=str(resolve_project_path(cfg.logging.file)) if cfg.logging.file else "disabled / 已关闭",
        log_level=cfg.logging.level,
        browser_mode="Headless / 无头" if cfg.zhihu.browser.headless else "Visible / 有头",
        retry_attempts=cfg.crawler.retry.max_attempts,
        image_concurrency=cfg.crawler.images.concurrency,
        cookie_rotation="Enabled / 启用" if cfg.zhihu.cookies_required else "Disabled / 禁用",
    )


def render_config_panel(snapshot: ConfigDisplaySnapshot) -> Panel:
    """Render the Rich config panel from a normalized snapshot."""
    body = Text(
        f"""
[b]配置路径 (Config Path):[/] {snapshot.config_path}

[b]输出目录 (Output Directory):[/] {snapshot.output_directory}
[b]Cookie文件 (Cookie File):[/] {snapshot.configured_cookie_path}
[b]当前生效Cookie (Active Cookie):[/] {snapshot.active_cookie_path}
[b]Cookie池目录 (Cookie Pool):[/] {snapshot.active_pool_dir}
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
