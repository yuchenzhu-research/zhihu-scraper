"""Small public API for agents, scripts, and the command-line entry point."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .application import ArchiveReport, ArchiveSink, ArchiveWorkflow, BrowserReader
from .archive import LocalArchive
from .browser import BrowserFallback
from .http import (
    CookieDiagnostic,
    LoginStatus,
    ZhihuHttpClient,
    diagnose_cookies,
    load_cookies,
)
from .settings import ArchiveSettings
from .settings import BrowserFallback as BrowserFallbackMode
from .source import ZhihuSource


@dataclass(frozen=True, slots=True)
class SessionReport:
    cookie_diagnostic: CookieDiagnostic
    login_status: LoginStatus | None


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
    "archive_url",
    "build_workflow",
    "check_session",
]
