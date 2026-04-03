"""
healthcheck.py - Environment check helpers for the CLI

Moves environment probing and diagnostic summarization out of cli/app.py so the
command layer stays thinner and user-facing diagnostics remain controlled.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from rich import print as rprint
from rich.text import Text

from core.config import get_config


@dataclass(frozen=True)
class CheckItem:
    label: str
    status: str
    detail: str
    hint: Optional[str] = None


def _status_icon(status: str) -> str:
    return {
        "ok": "✅",
        "warn": "⚠️",
        "error": "❌",
    }.get(status, "•")


def _shorten_single_line(text: str, max_length: int = 180) -> str:
    single_line = " ".join(part.strip() for part in text.replace("\r", "\n").splitlines() if part.strip())
    if len(single_line) <= max_length:
        return single_line
    return single_line[: max_length - 3].rstrip() + "..."


def summarize_playwright_failure(exc: Exception) -> tuple[str, Optional[str]]:
    """
    Convert noisy Playwright/browser startup exceptions into concise diagnostics.
    将冗长的 Playwright/浏览器启动异常收敛成简短诊断。
    """
    raw = str(exc)

    if "Executable doesn't exist" in raw:
        return (
            "Playwright 浏览器未安装完整。 / Playwright browser binaries are missing.",
            "运行 `python -m playwright install chromium` 或 `./install.sh --recreate`。",
        )

    if "Permission denied (1100)" in raw or "bootstrap_check_in" in raw:
        return (
            "Chromium 启动后被当前环境拒绝。 / Chromium launch was denied by the current environment.",
            "常见于受限沙箱、无桌面会话或本机权限限制。请改到正常桌面终端重试，必要时先仅使用 API 路径。",
        )

    if "Target page, context or browser has been closed" in raw:
        return (
            "Chromium 启动后立即退出。 / Chromium launched and exited immediately.",
            "通常和本机浏览器权限、沙箱限制或 Playwright 安装异常有关。先执行 `./install.sh --recreate`，再重试 `zhihu check`。",
        )

    return (
        f"Playwright 检查失败 / Browser check failed: {_shorten_single_line(raw)}",
        "可先继续使用协议层抓取；如需浏览器回退，请先修复本机 Playwright 环境。",
    )


async def _probe_playwright() -> None:
    from playwright.async_api import async_playwright

    from core.browser_fallback import _launch_browser_with_fallback

    cfg = get_config()
    async with async_playwright() as pw:
        browser = await _launch_browser_with_fallback(
            pw,
            cfg.zhihu.browser,
            headless=cfg.zhihu.browser.headless,
            report_launch_failures=False,
        )
        await browser.close()


def collect_environment_checks() -> list[CheckItem]:
    cfg = get_config()
    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "config.yaml"

    items: list[CheckItem] = []
    items.append(
        CheckItem(
            label="config.yaml / 配置文件",
            status="ok" if config_path.exists() else "error",
            detail=str(config_path) if config_path.exists() else "未找到 config.yaml / config.yaml is missing",
        )
    )

    from core.cookie_manager import (
        count_available_cookie_sources,
        has_real_cookie_values,
        resolve_cookie_file_path,
        resolve_cookie_pool_dir,
    )

    cookies_path = resolve_cookie_file_path(cfg.zhihu.cookies_file)
    cookie_pool_dir = resolve_cookie_pool_dir(cfg.zhihu.cookies_pool_dir)
    primary_cookie_ready = has_real_cookie_values(cookies_path)
    available_sources = count_available_cookie_sources(cfg.zhihu.cookies_file, cfg.zhihu.cookies_pool_dir)

    items.append(
        CheckItem(
            label="主 Cookie 文件 / Primary cookie",
            status="ok" if primary_cookie_ready else "warn",
            detail=str(cookies_path),
            hint=None if primary_cookie_ready else "当前主 Cookie 仍未就绪；游客模式可运行，但结果范围和稳定性更弱。",
        )
    )
    items.append(
        CheckItem(
            label="可用号源数 / Available sessions",
            status="ok" if available_sources else "warn",
            detail=f"{available_sources} (pool: {cookie_pool_dir})",
            hint=None if available_sources else "建议补上 `.local/cookie_pool/` 或至少一组有效登录态。",
        )
    )

    try:
        asyncio.run(_probe_playwright())
        items.append(
            CheckItem(
                label="Playwright 浏览器 / Browser fallback",
                status="ok",
                detail="可启动 / Available",
            )
        )
    except ModuleNotFoundError:
        items.append(
            CheckItem(
                label="Playwright 浏览器 / Browser fallback",
                status="warn",
                detail="未安装 Python 包 / Python package is missing",
                hint="执行 `pip install -e .` 或 `./install.sh --recreate`。",
            )
        )
    except Exception as exc:
        detail, hint = summarize_playwright_failure(exc)
        items.append(
            CheckItem(
                label="Playwright 浏览器 / Browser fallback",
                status="warn",
                detail=detail,
                hint=hint,
            )
        )

    return items


def render_environment_check(items: Optional[Iterable[CheckItem]] = None) -> None:
    rprint("🔍 System check... / 系统检查...\n")
    for item in items or collect_environment_checks():
        rprint(f"{_status_icon(item.status)} {item.label}: {item.detail}")
        if item.hint:
            rprint(Text(f"   💡 {item.hint}", justify="left"))
