"""Small, strict user settings for the rebuilt archive workflow.

The public configuration file deliberately contains paths and behavior switches
only.  Authentication values belong in the separate cookie file referenced by
``network.cookie_file``.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class SettingsError(ValueError):
    """A settings problem that can be shown directly to a Chinese-speaking user."""


class BrowserFallback(StrEnum):
    """When the persistent browser is allowed to participate in fetching."""

    AUTO = "auto"
    NEVER = "never"
    ALWAYS = "always"


@dataclass(frozen=True, slots=True)
class ArchiveSettings:
    """Validated settings shared by the CLI and orchestration layer."""

    output_dir: Path = Path("知乎归档")
    markdown: bool = True
    html: bool = False
    pdf: bool = False
    comments: bool = False
    comment_roots: int = 10
    comment_replies: int = 10
    media_download: bool = True

    cookie_file: Path | None = None
    proxy: str | None = None
    timeout: float = 30.0
    request_interval: float = 0.5
    request_jitter: float = 0.5
    retries: int = 3
    page_size: int = 20

    browser_fallback: BrowserFallback = BrowserFallback.AUTO
    headless: bool = False
    cdp_url: str | None = None

    def __post_init__(self) -> None:
        output_dir = _path_value(self.output_dir, "archive.output_dir")
        cookie_file = (
            None
            if self.cookie_file is None
            else _path_value(self.cookie_file, "network.cookie_file")
        )
        proxy = _proxy_url(self.proxy)
        fallback = _browser_fallback(self.browser_fallback)
        cdp_url = _optional_nonempty_string(self.cdp_url, "browser.cdp_url")

        object.__setattr__(self, "output_dir", output_dir)
        object.__setattr__(self, "cookie_file", cookie_file)
        object.__setattr__(self, "proxy", proxy)
        object.__setattr__(self, "browser_fallback", fallback)
        object.__setattr__(self, "cdp_url", cdp_url)
        object.__setattr__(
            self,
            "timeout",
            _number_in_range(
                self.timeout,
                "network.timeout",
                minimum=0,
                maximum=300,
                range_description="大于 0 且不超过 300 秒",
            ),
        )
        for name in ("request_interval", "request_jitter"):
            object.__setattr__(
                self,
                name,
                _number_in_range(
                    getattr(self, name),
                    f"network.{name}",
                    minimum=0,
                    maximum=60,
                    include_minimum=True,
                    range_description="在 0 到 60 秒之间",
                ),
            )

        for field_name in (
            "markdown",
            "html",
            "pdf",
            "comments",
            "media_download",
            "headless",
        ):
            section = "browser" if field_name == "headless" else "archive"
            _boolean(getattr(self, field_name), f"{section}.{field_name}")

        _integer_in_range(
            self.comment_roots,
            "archive.comment_roots",
            minimum=1,
            maximum=100,
        )
        _integer_in_range(
            self.comment_replies,
            "archive.comment_replies",
            minimum=1,
            maximum=100,
        )
        _integer_in_range(self.retries, "network.retries", minimum=0, maximum=10)
        _integer_in_range(self.page_size, "network.page_size", minimum=1, maximum=100)

    @classmethod
    def from_toml(cls, path: str | Path) -> ArchiveSettings:
        """Load a strict TOML file without touching any configured target path."""

        settings_path = Path(path).expanduser()
        try:
            with settings_path.open("rb") as settings_file:
                document = tomllib.load(settings_file)
        except FileNotFoundError as error:
            raise SettingsError(f"找不到设置文件：{settings_path}") from error
        except PermissionError as error:
            raise SettingsError(f"没有权限读取设置文件：{settings_path}") from error
        except tomllib.TOMLDecodeError as error:
            raise SettingsError(f"设置文件 TOML 格式有误：{settings_path.name}") from error
        except OSError as error:
            raise SettingsError(f"无法读取设置文件：{settings_path}") from error

        return cls.from_mapping(document)

    @classmethod
    def from_mapping(cls, document: Mapping[str, Any]) -> ArchiveSettings:
        """Build settings from already parsed data using the same strict schema."""

        allowed_sections = {"archive", "network", "browser"}
        unknown_sections = set(document) - allowed_sections
        if unknown_sections:
            section = sorted(unknown_sections)[0]
            if section in _COOKIE_VALUE_FIELDS:
                raise _cookie_value_error(section)
            raise SettingsError(f"不支持配置分区 {section}，请检查拼写")

        archive = _table(document, "archive")
        network = _table(document, "network")
        browser = _table(document, "browser")

        _reject_unknown_fields(
            archive,
            "archive",
            {
                "output_dir",
                "markdown",
                "html",
                "pdf",
                "comments",
                "comment_roots",
                "comment_replies",
                "media_download",
            },
        )
        _reject_unknown_fields(
            network,
            "network",
            {
                "cookie_file",
                "proxy",
                "timeout",
                "retries",
                "page_size",
                "request_interval",
                "request_jitter",
            },
        )
        _reject_unknown_fields(
            browser,
            "browser",
            {"fallback", "headless", "cdp_url"},
        )

        defaults = cls()
        return cls(
            output_dir=_path_from_table(
                archive,
                "output_dir",
                "archive.output_dir",
                defaults.output_dir,
            ),
            markdown=_value(archive, "markdown", defaults.markdown),
            html=_value(archive, "html", defaults.html),
            pdf=_value(archive, "pdf", defaults.pdf),
            comments=_value(archive, "comments", defaults.comments),
            comment_roots=_value(
                archive,
                "comment_roots",
                defaults.comment_roots,
            ),
            comment_replies=_value(
                archive,
                "comment_replies",
                defaults.comment_replies,
            ),
            media_download=_value(
                archive,
                "media_download",
                defaults.media_download,
            ),
            cookie_file=_optional_path_from_table(
                network,
                "cookie_file",
                "network.cookie_file",
            ),
            proxy=_value(network, "proxy", defaults.proxy),
            timeout=_value(network, "timeout", defaults.timeout),
            request_interval=_value(network, "request_interval", defaults.request_interval),
            request_jitter=_value(network, "request_jitter", defaults.request_jitter),
            retries=_value(network, "retries", defaults.retries),
            page_size=_value(network, "page_size", defaults.page_size),
            browser_fallback=_value(
                browser,
                "fallback",
                defaults.browser_fallback,
            ),
            headless=_value(browser, "headless", defaults.headless),
            cdp_url=_value(browser, "cdp_url", defaults.cdp_url),
        )

    def to_safe_summary(self) -> dict[str, object]:
        """Return diagnostics without exposing proxy credentials or cookie paths."""

        return {
            "archive": {
                "output_dir": str(self.output_dir),
                "markdown": self.markdown,
                "html": self.html,
                "pdf": self.pdf,
                "comments": self.comments,
                "comment_roots": self.comment_roots,
                "comment_replies": self.comment_replies,
                "media_download": self.media_download,
            },
            "network": {
                "cookie_file_configured": self.cookie_file is not None,
                "proxy_configured": self.proxy is not None,
                "timeout": self.timeout,
                "request_interval": self.request_interval,
                "request_jitter": self.request_jitter,
                "retries": self.retries,
                "page_size": self.page_size,
            },
            "browser": {
                "fallback": self.browser_fallback.value,
                "headless": self.headless,
                "cdp_configured": self.cdp_url is not None,
            },
        }


DEFAULT_SETTINGS_TOML = """\
# 知乎本地归档设置。未写出的选项会使用安全默认值。

[archive]
output_dir = "知乎归档"
markdown = true
html = false
pdf = false
comments = false
comment_roots = 10
comment_replies = 10
media_download = true

[network]
# Cookie 值不要写进本文件；需要登录态时只填写导出的 Cookie 文件路径。
# cookie_file = "~/.config/zhihu-scraper/cookies.json"
# proxy = "http://127.0.0.1:7890"
timeout = 30.0
# 相邻 HTTP 请求的启动间隔：固定秒数 + 0 到 request_jitter 的随机秒数。
request_interval = 0.5
request_jitter = 0.5
retries = 3
page_size = 20

[browser]
fallback = "auto"
headless = false
# cdp_url = "http://127.0.0.1:9222"
"""


def load_settings(path: str | Path | None = None) -> ArchiveSettings:
    """Return defaults, or load and validate the supplied TOML file."""

    if path is None:
        return ArchiveSettings()
    return ArchiveSettings.from_toml(path)


def generate_default_settings(path: str | Path) -> bool:
    """Create a default TOML file once.

    ``True`` means a new file was created. ``False`` means an existing file was
    intentionally left byte-for-byte untouched.
    """

    settings_path = Path(path).expanduser()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with settings_path.open("x", encoding="utf-8", newline="\n") as settings_file:
            settings_file.write(DEFAULT_SETTINGS_TOML)
    except FileExistsError:
        return False
    except PermissionError as error:
        raise SettingsError(f"没有权限创建设置文件：{settings_path}") from error
    except OSError as error:
        raise SettingsError(f"无法创建设置文件：{settings_path}") from error
    return True


_COOKIE_VALUE_FIELDS = {"cookie", "cookies", "z_c0", "d_c0"}


def _table(document: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = document.get(name, {})
    if not isinstance(value, Mapping):
        raise SettingsError(f"配置分区 {name} 必须写成 [{name}] 表格")
    return value


def _reject_unknown_fields(
    table: Mapping[str, Any],
    section: str,
    allowed_fields: set[str],
) -> None:
    unknown_fields = set(table) - allowed_fields
    if not unknown_fields:
        return
    field = sorted(unknown_fields)[0]
    qualified_name = f"{section}.{field}"
    if field in _COOKIE_VALUE_FIELDS:
        raise _cookie_value_error(qualified_name)
    raise SettingsError(f"不支持配置项 {qualified_name}，请检查拼写")


def _cookie_value_error(field_name: str) -> SettingsError:
    return SettingsError(
        f"配置项 {field_name} 可能包含 Cookie 值；"
        "请勿把 Cookie 值写进 settings.toml，只设置 network.cookie_file 路径"
    )


def _value(table: Mapping[str, Any], name: str, default: Any) -> Any:
    return table[name] if name in table else default


def _path_from_table(
    table: Mapping[str, Any],
    name: str,
    field_name: str,
    default: Path,
) -> Path:
    if name not in table:
        return default
    return _path_value(table[name], field_name)


def _optional_path_from_table(
    table: Mapping[str, Any],
    name: str,
    field_name: str,
) -> Path | None:
    if name not in table:
        return None
    return _path_value(table[name], field_name)


def _path_value(value: object, field_name: str) -> Path:
    if isinstance(value, Path):
        path = value
    elif isinstance(value, str):
        if not value.strip():
            raise SettingsError(f"配置项 {field_name} 不能为空")
        path = Path(value.strip())
    else:
        raise SettingsError(f"配置项 {field_name} 必须是路径字符串")
    return path.expanduser()


def _optional_nonempty_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SettingsError(f"配置项 {field_name} 必须是字符串")
    normalized = value.strip()
    if not normalized:
        raise SettingsError(f"配置项 {field_name} 不能为空；不使用时请删除这一项")
    return normalized


def _proxy_url(value: object) -> str | None:
    normalized = _optional_nonempty_string(value, "network.proxy")
    if normalized is None:
        return None
    try:
        parsed = urlparse(normalized)
        parsed.port
    except ValueError:
        raise SettingsError("配置项 network.proxy 必须是有效的 HTTP 或 HTTPS 代理地址") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise SettingsError("配置项 network.proxy 必须是有效的 HTTP 或 HTTPS 代理地址")
    return normalized


def _boolean(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise SettingsError(f"配置项 {field_name} 必须是布尔值 true 或 false")
    return value


def _integer_in_range(
    value: object,
    field_name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int:
        raise SettingsError(f"配置项 {field_name} 必须是整数")
    if not minimum <= value <= maximum:
        raise SettingsError(f"配置项 {field_name} 必须在 {minimum} 到 {maximum} 之间")
    return value


def _number_in_range(
    value: object,
    field_name: str,
    *,
    minimum: float,
    maximum: float,
    range_description: str,
    include_minimum: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SettingsError(f"配置项 {field_name} 必须是数字")
    in_range = minimum <= value <= maximum if include_minimum else minimum < value <= maximum
    if not in_range:
        raise SettingsError(f"配置项 {field_name} 必须{range_description}")
    return float(value)


def _browser_fallback(value: object) -> BrowserFallback:
    if isinstance(value, BrowserFallback):
        return value
    if not isinstance(value, str):
        raise SettingsError("配置项 browser.fallback 必须是 auto、never 或 always 之一")
    try:
        return BrowserFallback(value)
    except ValueError as error:
        raise SettingsError("配置项 browser.fallback 必须是 auto、never 或 always 之一") from error


__all__ = [
    "ArchiveSettings",
    "BrowserFallback",
    "DEFAULT_SETTINGS_TOML",
    "SettingsError",
    "generate_default_settings",
    "load_settings",
]
