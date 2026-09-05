from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath
from types import ModuleType

import pytest

from zhihu_scraper.browser import BrowserFallback, BrowserLaunchError
from zhihu_scraper.platform import OperatingSystem, RuntimePlatform


class FakePage:
    def __init__(self) -> None:
        self.closed = False

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        return None

    def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        return None

    def content(self) -> str:
        return "<html><body>connected</body></html>"

    def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self) -> None:
        self.pages: list[FakePage] = []
        self.closed = False
        self.added_cookies: list[dict[str, object]] = []
        self.init_scripts: list[str] = []
        self.cleared_cookie_names: list[str] = []

    def new_page(self) -> FakePage:
        page = FakePage()
        self.pages.append(page)
        return page

    def cookies(self) -> list[dict[str, object]]:
        return [
            {"name": "z_c0", "value": "secret", "domain": ".zhihu.com"},
        ]

    def add_cookies(self, cookies: list[dict[str, object]]) -> None:
        self.added_cookies.extend(cookies)

    def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)

    def clear_cookies(self, *, name: str | None = None) -> None:
        if name is not None:
            self.cleared_cookie_names.append(name)

    def close(self) -> None:
        self.closed = True


class FakeExecutor:
    def __init__(self) -> None:
        self.context = FakeContext()
        self.connections: list[str] = []
        self.launches = 0
        self.closed = False
        self.close_count = 0

    def connect_over_cdp(self, cdp_url: str) -> FakeContext:
        self.connections.append(cdp_url)
        return self.context

    def launch_persistent_context(
        self,
        profile_dir: Path,
        *,
        headless: bool,
        executable_path: Path | None,
        proxy: str | None,
    ) -> FakeContext:
        self.launches += 1
        return self.context

    def close(self) -> None:
        self.closed = True
        self.close_count += 1


def runtime_for(tmp_path: Path) -> RuntimePlatform:
    return RuntimePlatform(
        operating_system=OperatingSystem.LINUX,
        user_data_directory=PurePosixPath(tmp_path / "app-data"),
        browser_candidates=(),
    )


def test_cdp_connection_reuses_default_context_for_pages_and_cookies(
    tmp_path: Path,
) -> None:
    executor = FakeExecutor()
    browser = BrowserFallback(
        cdp_url="http://127.0.0.1:9222",
        executor=executor,
        runtime_platform=runtime_for(tmp_path),
    )

    assert browser.fetch_html("https://www.zhihu.com/question/1") == (
        "<html><body>connected</body></html>"
    )
    assert browser.fetch_html("https://www.zhihu.com/question/2") == (
        "<html><body>connected</body></html>"
    )
    assert browser.cookie_dict() == {"z_c0": "secret"}
    browser.set_cookie_dict({"d_c0": "imported"})

    assert executor.connections == ["http://127.0.0.1:9222"]
    assert executor.launches == 0
    assert len(executor.context.pages) == 2
    assert all(page.closed for page in executor.context.pages)
    assert len(executor.context.init_scripts) == 1
    assert executor.context.added_cookies == [
        {
            "name": "d_c0",
            "value": "imported",
            "domain": ".zhihu.com",
            "path": "/",
            "secure": True,
        }
    ]
    assert executor.context.cleared_cookie_names == []
    assert not (tmp_path / "app-data" / "browser-profile").exists()


def test_cdp_close_disconnects_driver_without_closing_the_external_context(
    tmp_path: Path,
) -> None:
    executor = FakeExecutor()
    browser = BrowserFallback(
        cdp_url="ws://localhost:9222/devtools/browser/browser-id",
        executor=executor,
        runtime_platform=runtime_for(tmp_path),
    )
    browser.fetch_html("https://www.zhihu.com/question/1")

    browser.close()
    browser.close()

    assert executor.context.closed is False
    assert executor.closed is True
    assert executor.close_count == 1


def test_cdp_login_only_reads_cookies_and_leaves_external_pages_and_context_untouched(
    tmp_path: Path,
) -> None:
    executor = FakeExecutor()
    with BrowserFallback(
        cdp_url="http://localhost:9222",
        executor=executor,
        runtime_platform=runtime_for(tmp_path),
    ) as browser:
        browser.open_login_page()
        assert browser.cookie_dict() == {"z_c0": "secret"}

    assert executor.connections == ["http://localhost:9222"]
    assert executor.context.pages == []
    assert executor.context.init_scripts == []
    assert executor.context.added_cookies == []
    assert executor.context.cleared_cookie_names == []
    assert executor.context.closed is False
    assert executor.closed is True


@pytest.mark.parametrize(
    "cdp_url",
    [
        "http://example.com:9222",
        "https://localhost:9222",
        "wss://localhost:9222/devtools/browser/id",
        "http://user:password@127.0.0.1:9222",
        "http://localhost.example.com:9222",
        "http://127.0.0.2:9222",
        "http://2130706433:9222",
    ],
)
def test_cdp_refuses_non_loopback_or_credential_bearing_urls(
    tmp_path: Path,
    cdp_url: str,
) -> None:
    executor = FakeExecutor()

    with pytest.raises(BrowserLaunchError) as caught:
        BrowserFallback(
            cdp_url=cdp_url,
            executor=executor,
            runtime_platform=runtime_for(tmp_path),
        )

    assert "loopback" in str(caught.value).casefold()
    assert executor.connections == []


def test_playwright_adapter_connects_to_the_existing_default_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = FakeContext()

    class FakeExternalBrowser:
        def __init__(self) -> None:
            self.contexts = [context]
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1

    external_browser = FakeExternalBrowser()

    class FakeChromium:
        def __init__(self) -> None:
            self.connections: list[str] = []

        def connect_over_cdp(self, cdp_url: str) -> FakeExternalBrowser:
            self.connections.append(cdp_url)
            return external_browser

    chromium = FakeChromium()

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = chromium
            self.stop_calls = 0

        def stop(self) -> None:
            self.stop_calls += 1

    playwright = FakePlaywright()

    class FakePlaywrightStarter:
        def start(self) -> FakePlaywright:
            return playwright

    sync_api = ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: FakePlaywrightStarter()  # type: ignore[attr-defined]
    package = ModuleType("playwright")
    package.sync_api = sync_api  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    browser = BrowserFallback(
        cdp_url="http://localhost:9222",
        runtime_platform=runtime_for(tmp_path),
    )
    assert browser.fetch_html("https://www.zhihu.com/question/1") == (
        "<html><body>connected</body></html>"
    )
    browser.close()

    assert chromium.connections == ["http://localhost:9222"]
    assert external_browser.close_calls == 0
    assert context.closed is False
    assert playwright.stop_calls == 1


def test_cdp_connection_errors_are_actionable_and_secret_free(tmp_path: Path) -> None:
    class FailingExecutor(FakeExecutor):
        def connect_over_cdp(self, cdp_url: str) -> FakeContext:
            raise RuntimeError(
                f"failed endpoint={cdp_url} z_c0=connection-secret d_c0=another-secret"
            )

    browser = BrowserFallback(
        cdp_url="ws://[::1]:9222/devtools/browser/url-secret",
        executor=FailingExecutor(),
        runtime_platform=runtime_for(tmp_path),
    )

    with pytest.raises(BrowserLaunchError) as caught:
        browser.fetch_html("https://www.zhihu.com/question/1")

    message = str(caught.value)
    assert "running Chrome" in message
    assert "connection-secret" not in message
    assert "another-secret" not in message
    assert "url-secret" not in message
