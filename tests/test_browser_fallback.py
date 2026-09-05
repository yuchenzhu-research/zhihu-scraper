from __future__ import annotations

import builtins
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType

import pytest

from zhihu_scraper.browser import (
    BrowserCookieError,
    BrowserDependencyError,
    BrowserFallback,
    BrowserLaunchError,
    BrowserNavigationError,
)
from zhihu_scraper.platform import OperatingSystem, RuntimePlatform


class FakePage:
    def __init__(self, html: str = "<html><body>ready</body></html>") -> None:
        self.html = html
        self.goto_calls: list[tuple[str, str, int]] = []
        self.wait_calls: list[tuple[str, int]] = []
        self.closed = False

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append((url, wait_until, timeout))

    def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        self.wait_calls.append((state, timeout))

    def content(self) -> str:
        return self.html

    def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(
        self,
        page: FakePage | None = None,
        cookies: list[dict[str, object]] | None = None,
    ) -> None:
        self.page = page or FakePage()
        self.cookie_records = cookies or []
        self.closed = False
        self.close_count = 0
        self.added_cookies: list[dict[str, object]] = []
        self.init_scripts: list[str] = []
        self.cleared_cookie_names: list[str] = []

    def new_page(self) -> FakePage:
        return self.page

    def cookies(self) -> list[dict[str, object]]:
        return self.cookie_records

    def add_cookies(self, cookies: list[dict[str, object]]) -> None:
        self.added_cookies.extend(cookies)

    def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)

    def clear_cookies(self, *, name: str | None = None) -> None:
        if name is not None:
            self.cleared_cookie_names.append(name)

    def close(self) -> None:
        self.closed = True
        self.close_count += 1


class FakeExecutor:
    def __init__(self, context: FakeContext | None = None) -> None:
        self.context = context or FakeContext()
        self.launches: list[tuple[Path, bool, Path | None, str | None]] = []
        self.closed = False
        self.close_count = 0

    def launch_persistent_context(
        self,
        profile_dir: Path,
        *,
        headless: bool,
        executable_path: Path | None,
        proxy: str | None,
    ) -> FakeContext:
        self.launches.append((profile_dir, headless, executable_path, proxy))
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


def test_fetch_html_uses_a_persistent_headed_profile_and_waits_for_dom(tmp_path: Path) -> None:
    executor = FakeExecutor()
    browser = BrowserFallback(
        executor=executor,
        runtime_platform=runtime_for(tmp_path),
    )

    html = browser.fetch_html("https://www.zhihu.com/question/1")

    assert html == "<html><body>ready</body></html>"
    assert executor.launches == [(tmp_path / "app-data" / "browser-profile-v4", False, None, None)]
    assert (tmp_path / "app-data" / "browser-profile-v4").is_dir()
    assert executor.context.page.goto_calls == [
        ("https://www.zhihu.com/question/1", "domcontentloaded", 30_000)
    ]
    assert executor.context.page.wait_calls == [("domcontentloaded", 30_000)]
    assert executor.context.page.closed is True
    assert len(executor.context.init_scripts) == 1
    assert "webdriver" in executor.context.init_scripts[0]
    assert executor.context.cleared_cookie_names == ["BEC", "__zse_ck"]


def test_login_page_stays_open_until_the_managed_browser_is_closed(tmp_path: Path) -> None:
    executor = FakeExecutor()
    browser = BrowserFallback(executor=executor, runtime_platform=runtime_for(tmp_path))

    browser.open_login_page()
    browser.open_login_page()

    assert executor.context.page.goto_calls == [
        ("https://www.zhihu.com/signin", "domcontentloaded", 30_000)
    ]
    assert executor.context.page.closed is False
    assert executor.launches[0][1] is False
    browser.close()
    assert executor.context.page.closed is True
    assert executor.context.closed is True


def test_explicit_profile_headless_mode_and_browser_context_are_reused(tmp_path: Path) -> None:
    installed_browser = tmp_path / "chromium"
    installed_browser.touch()
    runtime = RuntimePlatform(
        operating_system=OperatingSystem.LINUX,
        user_data_directory=PurePosixPath(tmp_path / "ignored"),
        browser_candidates=(
            PurePosixPath(tmp_path / "missing-browser"),
            PurePosixPath(installed_browser),
        ),
    )
    executor = FakeExecutor()
    explicit_profile = tmp_path / "my-profile"
    browser = BrowserFallback(
        profile_dir=explicit_profile,
        headless=True,
        executor=executor,
        runtime_platform=runtime,
    )

    browser.fetch_html("https://www.zhihu.com/question/1")
    browser.fetch_html("https://www.zhihu.com/question/2")

    assert executor.launches == [(explicit_profile, True, installed_browser, None)]
    assert explicit_profile.is_dir()
    assert executor.context.cleared_cookie_names == [
        "BEC",
        "__zse_ck",
        "BEC",
        "__zse_ck",
    ]


def test_managed_chromium_is_retried_when_discovered_system_chrome_cannot_launch(
    tmp_path: Path,
) -> None:
    installed_browser = tmp_path / "chrome"
    installed_browser.touch()
    runtime = RuntimePlatform(
        operating_system=OperatingSystem.LINUX,
        user_data_directory=PurePosixPath(tmp_path / "app-data"),
        browser_candidates=(PurePosixPath(installed_browser),),
    )

    class SystemChromeFailure(FakeExecutor):
        def launch_persistent_context(
            self,
            profile_dir: Path,
            *,
            headless: bool,
            executable_path: Path | None,
            proxy: str | None,
        ) -> FakeContext:
            self.launches.append((profile_dir, headless, executable_path, proxy))
            if executable_path is not None:
                raise BrowserLaunchError("system chrome policy rejected launch")
            return self.context

    executor = SystemChromeFailure()
    browser = BrowserFallback(executor=executor, runtime_platform=runtime)

    assert browser.fetch_html("https://zhuanlan.zhihu.com/p/1") == (
        "<html><body>ready</body></html>"
    )
    assert executor.launches == [
        (
            tmp_path / "app-data" / "browser-profile-v4",
            False,
            installed_browser,
            None,
        ),
        (
            tmp_path / "app-data" / "browser-profile-v4",
            False,
            None,
            None,
        ),
    ]


def test_content_read_retries_when_zhihu_is_still_navigating(tmp_path: Path) -> None:
    class NavigatingPage(FakePage):
        def __init__(self) -> None:
            super().__init__("<html><body>settled</body></html>")
            self.content_calls = 0

        def content(self) -> str:
            self.content_calls += 1
            if self.content_calls == 1:
                raise RuntimeError("page is navigating and changing the content")
            return self.html

    page = NavigatingPage()
    sleeps: list[float] = []
    browser = BrowserFallback(
        executor=FakeExecutor(FakeContext(page=page)),
        runtime_platform=runtime_for(tmp_path),
        sleep=sleeps.append,
    )

    assert browser.fetch_html("https://zhuanlan.zhihu.com/p/1") == (
        "<html><body>settled</body></html>"
    )
    assert page.content_calls == 2
    assert sleeps == [0.25]


def test_playwright_adapter_applies_authenticated_proxy_to_managed_browser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = FakeContext()

    class FakeChromium:
        def __init__(self) -> None:
            self.launches: list[tuple[str, dict[str, object]]] = []

        def launch_persistent_context(
            self,
            profile_dir: str,
            **options: object,
        ) -> FakeContext:
            self.launches.append((profile_dir, options))
            return context

    chromium = FakeChromium()

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = chromium

        def stop(self) -> None:
            return None

    class FakePlaywrightStarter:
        def start(self) -> FakePlaywright:
            return FakePlaywright()

    sync_api = ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: FakePlaywrightStarter()  # type: ignore[attr-defined]
    package = ModuleType("playwright")
    package.sync_api = sync_api  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    browser = BrowserFallback(
        proxy="http://account:password@127.0.0.1:7890",
        runtime_platform=runtime_for(tmp_path),
    )
    browser.fetch_html("https://zhuanlan.zhihu.com/p/1")
    browser.close()

    assert chromium.launches == [
        (
            str(tmp_path / "app-data" / "browser-profile-v4"),
            {
                "headless": False,
                "args": ["--disable-blink-features=AutomationControlled"],
                "proxy": {
                    "server": "http://127.0.0.1:7890",
                    "username": "account",
                    "password": "password",
                },
            },
        )
    ]


def test_cookie_dict_contains_only_zhihu_cookies(tmp_path: Path) -> None:
    context = FakeContext(
        cookies=[
            {"name": "z_c0", "value": "secret-z", "domain": ".zhihu.com"},
            {"name": "d_c0", "value": "secret-d", "domain": "www.zhihu.com"},
            {"name": "theme", "value": "dark", "domain": "zhuanlan.zhihu.com"},
            {"name": "foreign", "value": "nope", "domain": ".example.com"},
            {"name": "", "value": "invalid", "domain": ".zhihu.com"},
            {"name": "missing-value", "domain": ".zhihu.com"},
        ]
    )
    browser = BrowserFallback(
        executor=FakeExecutor(context),
        runtime_platform=runtime_for(tmp_path),
    )

    cookies = browser.cookie_dict()

    assert cookies == {
        "z_c0": "secret-z",
        "d_c0": "secret-d",
        "theme": "dark",
    }


def test_cookie_import_is_scoped_to_zhihu_and_never_requires_logging_values(
    tmp_path: Path,
) -> None:
    context = FakeContext()
    browser = BrowserFallback(
        executor=FakeExecutor(context),
        runtime_platform=runtime_for(tmp_path),
    )

    browser.set_cookie_dict(
        {
            "z_c0": "secret-z",
            "d_c0": "secret-d",
            "": "ignored",
        }
    )

    assert context.added_cookies == [
        {
            "name": "z_c0",
            "value": "secret-z",
            "domain": ".zhihu.com",
            "path": "/",
            "secure": True,
        },
        {
            "name": "d_c0",
            "value": "secret-d",
            "domain": ".zhihu.com",
            "path": "/",
            "secure": True,
        },
    ]


def test_context_manager_closes_context_and_executor_once(tmp_path: Path) -> None:
    executor = FakeExecutor()

    with BrowserFallback(
        executor=executor,
        runtime_platform=runtime_for(tmp_path),
    ) as browser:
        browser.fetch_html("https://www.zhihu.com/question/1")

    browser.close()

    assert executor.context.closed is True
    assert executor.closed is True
    assert executor.context.close_count == 1
    assert executor.close_count == 1


def test_missing_playwright_has_an_actionable_secret_free_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def import_without_playwright(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name.startswith("playwright"):
            raise ModuleNotFoundError("z_c0=must-not-leak")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_playwright)
    browser = BrowserFallback(runtime_platform=runtime_for(tmp_path))

    with pytest.raises(BrowserDependencyError) as caught:
        browser.fetch_html("https://www.zhihu.com/question/1")

    message = str(caught.value)
    assert "Playwright runtime" in message
    assert "playwright install chromium" in message
    assert "zhihu-scraper[full]" not in message
    assert "must-not-leak" not in message


def test_browser_failures_never_copy_cookie_values_into_exceptions(tmp_path: Path) -> None:
    class FailingPage(FakePage):
        def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
            raise RuntimeError("request failed with z_c0=navigation-secret")

    class FailingCookieContext(FakeContext):
        def cookies(self) -> list[dict[str, object]]:
            raise RuntimeError("d_c0=cookie-secret")

    navigation_browser = BrowserFallback(
        executor=FakeExecutor(FakeContext(page=FailingPage())),
        runtime_platform=runtime_for(tmp_path),
    )
    with pytest.raises(BrowserNavigationError) as navigation_error:
        navigation_browser.fetch_html("https://www.zhihu.com/question/1")

    cookie_browser = BrowserFallback(
        executor=FakeExecutor(FailingCookieContext()),
        runtime_platform=runtime_for(tmp_path),
    )
    with pytest.raises(BrowserCookieError) as cookie_error:
        cookie_browser.cookie_dict()

    assert "navigation-secret" not in str(navigation_error.value)
    assert "cookie-secret" not in str(cookie_error.value)


def test_browser_refuses_external_or_credential_bearing_urls(tmp_path: Path) -> None:
    executor = FakeExecutor()
    browser = BrowserFallback(
        executor=executor,
        runtime_platform=runtime_for(tmp_path),
    )

    for url in (
        "https://example.com/",
        "http://www.zhihu.com/question/1",
        "https://user:password@www.zhihu.com/question/1",
        "https://www.zhihu.com.example.org/question/1",
    ):
        with pytest.raises(BrowserNavigationError):
            browser.fetch_html(url)

    assert executor.launches == []
