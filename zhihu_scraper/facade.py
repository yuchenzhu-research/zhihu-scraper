"""Small public API for agents, scripts, and the command-line entry point."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .application import ArchiveReport, ArchiveSink, ArchiveWorkflow, BrowserReader
from .archive import LocalArchive
from .browser import BrowserFallback
from .http import (
    CookieDiagnostic,
    LoginStatus,
    ZhihuHttpClient,
    diagnose_cookies,
    load_cookies,
    save_cookies,
)
from .settings import ArchiveSettings
from .settings import BrowserFallback as BrowserFallbackMode
from .source import ZhihuSource


@dataclass(frozen=True, slots=True)
class SessionReport:
    cookie_diagnostic: CookieDiagnostic
    login_status: LoginStatus | None


@dataclass(frozen=True, slots=True)
class LoginReport:
    cookie_file: Path
    authenticated: bool


class LoginTimeoutError(TimeoutError):
    """No verified login became available within the interactive time limit."""


def login_session(
    settings: ArchiveSettings | None = None,
    *,
    timeout: float = 180.0,
    poll_interval: float = 2.0,
    browser_factory: Callable[[], BrowserFallback] | None = None,
    client_factory: Callable[[Mapping[str, str], float], ZhihuHttpClient] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> LoginReport:
    """Let the user log in, then save only cookies verified by Zhihu's identity endpoint."""

    for name, value in (("timeout", timeout), ("poll_interval", poll_interval)):
        if isinstance(value, bool) or not math.isfinite(value) or not 0 < value <= 600:
            raise ValueError(f"{name} must be between 0 and 600 seconds.")
    effective_settings = settings or ArchiveSettings()
    cookie_file = effective_settings.cookie_file or Path(".local/cookies.json")
    deadline = monotonic() + timeout

    def configured_browser() -> BrowserFallback:
        return BrowserFallback(
            cdp_url=effective_settings.cdp_url,
            headless=False,
            proxy=effective_settings.proxy,
            timeout_ms=max(1, int(min(effective_settings.timeout, timeout) * 1000)),
        )

    def configured_client(cookies: Mapping[str, str], remaining: float) -> ZhihuHttpClient:
        return ZhihuHttpClient(
            cookies=cookies,
            proxy=effective_settings.proxy,
            timeout=remaining,
            max_retries=0,
            request_interval=effective_settings.request_interval,
            request_jitter=effective_settings.request_jitter,
        )

    create_browser = browser_factory or configured_browser
    create_client = client_factory or configured_client
    with create_browser() as browser:
        browser.open_login_page()
        while monotonic() < deadline:
            cookies = browser.cookie_dict()
            remaining = deadline - monotonic()
            # curl uses integer milliseconds; a sub-millisecond timeout would
            # round down to zero and disable its request deadline.
            if remaining < 0.001:
                break
            if cookies.get("z_c0"):
                client = create_client(
                    cookies, min(max(0.001, effective_settings.timeout), remaining)
                )
                try:
                    status = client.check_login()
                finally:
                    client.close()
                if status.authenticated and monotonic() < deadline:
                    saved_path = save_cookies(cookie_file, cookies)
                    return LoginReport(cookie_file=saved_path, authenticated=True)
            remaining = deadline - monotonic()
            if remaining > 0:
                sleep(min(poll_interval, remaining))
    raise LoginTimeoutError("等待知乎登录超时；原有 Cookie 文件未改动，请重新运行 zhihu login。")


def archive_url(
    raw_url: str,
    settings: ArchiveSettings | None = None,
) -> ArchiveReport:
    """Archive one supported Zhihu URL using validated local settings."""

    effective_settings = settings or ArchiveSettings()
    workflow = build_workflow(effective_settings)
    try:
        return workflow.run(raw_url)
    finally:
        workflow.close()


def build_workflow(
    settings: ArchiveSettings,
    *,
    client: ZhihuHttpClient | None = None,
    sink: ArchiveSink | None = None,
    browser_factory: Callable[[], BrowserReader] | None = None,
    cookies: Mapping[str, str] | None = None,
) -> ArchiveWorkflow:
    """Compose the public workflow while keeping every boundary injectable."""

    archive_sink = sink if sink is not None else LocalArchive.from_settings(settings)
    configured_cookies = dict(cookies) if cookies is not None else _configured_cookies(settings)
    http_client = client or ZhihuHttpClient(
        cookies=configured_cookies,
        proxy=settings.proxy,
        max_retries=settings.retries,
        timeout=settings.timeout,
        request_interval=settings.request_interval,
        request_jitter=settings.request_jitter,
    )
    if browser_factory is None and settings.browser_fallback is not BrowserFallbackMode.NEVER:

        def configured_browser() -> BrowserFallback:
            return BrowserFallback(
                cdp_url=settings.cdp_url,
                headless=settings.headless,
                proxy=settings.proxy,
                timeout_ms=max(1, int(settings.timeout * 1000)),
            )

        browser_factory = configured_browser
    return ArchiveWorkflow(
        source=ZhihuSource(http_client),
        sink=archive_sink,
        settings=settings,
        comment_client=http_client,
        embedded_video_fetcher=http_client.get_json,
        browser_factory=browser_factory,
        browser_cookies=configured_cookies,
        browser_cookie_sink=getattr(http_client, "update_cookies", None),
        resource_closer=http_client.close if client is None else None,
    )


def check_session(settings: ArchiveSettings | None = None) -> SessionReport:
    """Check Cookie names and the real Zhihu identity endpoint without disclosure."""

    effective_settings = settings or ArchiveSettings()
    cookies = _configured_cookies(effective_settings)
    diagnostic = diagnose_cookies(cookies)
    if not cookies:
        return SessionReport(
            cookie_diagnostic=diagnostic,
            login_status=None,
        )
    client = ZhihuHttpClient(
        cookies=cookies,
        proxy=effective_settings.proxy,
        max_retries=effective_settings.retries,
        timeout=effective_settings.timeout,
        request_interval=effective_settings.request_interval,
        request_jitter=effective_settings.request_jitter,
    )
    try:
        return SessionReport(
            cookie_diagnostic=diagnostic,
            login_status=client.check_login(),
        )
    finally:
        client.close()


def _configured_cookies(settings: ArchiveSettings) -> dict[str, str]:
    if settings.cookie_file is None:
        return {}
    return load_cookies(settings.cookie_file)


__all__ = [
    "ArchiveReport",
    "ArchiveSettings",
    "SessionReport",
    "LoginReport",
    "LoginTimeoutError",
    "archive_url",
    "build_workflow",
    "check_session",
    "login_session",
]
