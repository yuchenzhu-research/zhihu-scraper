"""Authenticated Zhihu HTTP access with safe cookie diagnostics."""

from __future__ import annotations

import json
import math
import os
import random
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, Self, cast
from urllib.parse import urljoin, urlparse

from curl_cffi import requests

from .platform import RuntimePlatform


@dataclass(frozen=True, slots=True)
class CookieDiagnostic:
    missing: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.missing

    @property
    def message(self) -> str:
        if self.is_complete:
            return "Cookie fields z_c0 and d_c0 are available."
        return f"Cookie fields missing: {', '.join(self.missing)}."


@dataclass(frozen=True, slots=True)
class LoginStatus:
    authenticated: bool
    member_id: str | None = None
    name: str | None = None
    reason: str | None = None


class _HttpResponse(Protocol):
    status_code: int
    text: str
    headers: Mapping[str, str]

    def json(self) -> object: ...


class _HttpSession(Protocol):
    def get(self, url: str, **kwargs: Any) -> _HttpResponse: ...


class ZhihuHttpError(RuntimeError):
    """Base class for sanitized, user-facing Zhihu HTTP failures."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(ZhihuHttpError):
    """The configured Zhihu login session is missing or expired."""


class AccessDeniedError(ZhihuHttpError):
    """Zhihu refused access for the current session."""


class RateLimitError(ZhihuHttpError):
    """Zhihu rate limiting persisted after the configured retries."""


class ServerError(ZhihuHttpError):
    """Zhihu returned a server-side failure after limited retries."""


class TransportError(RuntimeError):
    """The HTTP transport failed without exposing its potentially sensitive details."""


class InvalidResponseError(RuntimeError):
    """Zhihu returned a response that could not be decoded safely."""


class RetryWaitError(RuntimeError):
    """Stop when retry timing cannot be honored within a bounded wait.

    This is deliberately not a transport or HTTP failure eligible for browser
    fallback, which would bypass the server's requested waiting period.
    """


class CookieFileError(ValueError):
    """A Cookie file could not be loaded safely."""


class UnsafeZhihuUrlError(ValueError):
    """A request target was outside the trusted Zhihu origins."""


class ZhihuHttpClient:
    """Small authenticated interface over one reusable curl_cffi session."""

    def __init__(
        self,
        *,
        cookies: Mapping[str, str] | None = None,
        proxy: str | None = None,
        session: _HttpSession | None = None,
        max_retries: int = 2,
        timeout: float = 20.0,
        request_interval: float = 0.0,
        request_jitter: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.monotonic,
        random: Callable[[], float] = random.random,
    ) -> None:
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a finite positive number of seconds.")
        for name, value in (
            ("request_interval", request_interval),
            ("request_jitter", request_jitter),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 <= value <= 60
            ):
                raise ValueError(f"{name} must be a finite number between 0 and 60 seconds.")
        self._cookies = dict(cookies or {})
        self._proxy = proxy
        self._session = session or cast(
            _HttpSession,
            requests.Session(impersonate="chrome"),
        )
        self._max_retries = max_retries
        # curl truncates timeout to milliseconds; zero would disable its deadline.
        self._timeout = max(0.001, timeout)
        self._sleep = sleep
        self._clock = clock
        self._request_interval = float(request_interval)
        self._request_jitter = float(request_jitter)
        self._monotonic = monotonic
        self._random = random
        self._next_request_at: float | None = None
        self._closed = False

    def update_cookies(self, cookies: Mapping[str, str]) -> None:
        """Merge browser-exported Cookie values into future HTTP requests."""

        for name, value in cookies.items():
            if not isinstance(name, str) or not isinstance(value, str):
                continue
            normalized_name = name.strip()
            normalized_value = value.strip()
            if normalized_name and normalized_value:
                self._cookies[normalized_name] = normalized_value

    def close(self) -> None:
        """Release the underlying connection pool exactly once."""

        if self._closed:
            return
        self._closed = True
        close_session = getattr(self._session, "close", None)
        if not callable(close_session):
            return
        try:
            close_session()
        except Exception:
            raise TransportError("Zhihu HTTP resources could not be closed cleanly.") from None

    def __enter__(self) -> Self:
        if self._closed:
            raise TransportError("Zhihu HTTP client is closed.")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.close()
        except TransportError:
            if exc_value is None:
                raise

    def get_json(self, url_or_path: str) -> object:
        response = self._get(url_or_path, accept="application/json, text/plain, */*")
        try:
            return response.json()
        except Exception:
            raise InvalidResponseError(
                "Zhihu returned a response that was not valid JSON."
            ) from None

    def get_html(self, url_or_path: str) -> str:
        response = self._get(
            url_or_path,
            accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )
        return response.text

    def check_login(self) -> LoginStatus:
        try:
            payload = self.get_json("/api/v4/me")
        except (AuthenticationError, AccessDeniedError):
            return LoginStatus(
                authenticated=False,
                reason="authentication_rejected",
            )
        if not isinstance(payload, Mapping):
            return LoginStatus(authenticated=False, reason="invalid_response")

        raw_member_id = payload.get("id")
        raw_url_token = payload.get("url_token")
        member_id = raw_member_id if isinstance(raw_member_id, str) else None
        url_token = raw_url_token if isinstance(raw_url_token, str) else None
        authenticated = bool(member_id or url_token)
        raw_name = payload.get("name")
        name = raw_name if isinstance(raw_name, str) else None
        return LoginStatus(
            authenticated=authenticated,
            member_id=member_id,
            name=name,
            reason=None if authenticated else "identity_missing",
        )

    def _get(self, url_or_path: str, *, accept: str) -> _HttpResponse:
        if self._closed:
            raise TransportError("Zhihu HTTP client is closed.")
        url = _absolute_zhihu_url(url_or_path)
        request_options: dict[str, object] = {
            "headers": {
                "Accept": accept,
                "Referer": "https://www.zhihu.com/",
            },
            "cookies": self._cookies,
            "timeout": self._timeout,
            "allow_redirects": False,
        }
        if self._proxy:
            request_options["proxy"] = self._proxy

        waited = 0.0

        def wait_before_retry(delay: float) -> None:
            nonlocal waited
            if delay > 60.0 - waited:
                raise RetryWaitError(
                    "Zhihu retry would exceed the 60-second total waiting budget; "
                    "no early retry was sent, try again later."
                ) from None
            self._sleep(delay)
            waited += delay

        for retry_number in range(self._max_retries + 1):
            if self._next_request_at is not None:
                remaining = self._next_request_at - self._monotonic()
                if remaining > 0:
                    if retry_number:
                        wait_before_retry(remaining)
                    else:
                        self._sleep(remaining)
            jitter = self._random() * self._request_jitter if self._request_jitter else 0.0
            self._next_request_at = self._monotonic() + self._request_interval + jitter
            try:
                response = self._session.get(url, **request_options)
            except Exception:
                if retry_number < self._max_retries:
                    wait_before_retry(_retry_delay({}, retry_number, now=self._clock()))
                    continue
                raise TransportError(
                    "Zhihu request failed after limited retries; check the network or proxy."
                ) from None
            should_retry = response.status_code == 429 or 500 <= response.status_code <= 599
            if should_retry and retry_number < self._max_retries:
                wait_before_retry(_retry_delay(response.headers, retry_number, now=self._clock()))
                continue
            if response.status_code == 401:
                raise AuthenticationError(
                    401,
                    "Zhihu returned HTTP 401; authentication is missing or expired. "
                    "Check the z_c0 and d_c0 Cookie fields.",
                )
            if response.status_code == 403:
                raise AccessDeniedError(
                    403,
                    "Zhihu returned HTTP 403; access was denied. "
                    "Refresh the z_c0 and d_c0 Cookie fields or use browser fallback.",
                )
            if response.status_code == 429:
                raise RateLimitError(
                    429,
                    "Zhihu returned HTTP 429 after limited retries; "
                    "reduce request frequency and try again later.",
                )
            if 500 <= response.status_code <= 599:
                raise ServerError(
                    response.status_code,
                    f"Zhihu returned HTTP {response.status_code} after limited retries; "
                    "the server is temporarily unavailable.",
                )
            if 300 <= response.status_code <= 399:
                raise InvalidResponseError(
                    "Zhihu returned an unexpected redirect; authenticated requests "
                    "are never forwarded to another origin."
                )
            return response

        raise AssertionError("retry loop must return or raise")


def save_cookies(path: Path, cookies: Mapping[str, str]) -> Path:
    """Atomically save validated Zhihu cookies with private file permissions."""

    cookie_path = Path(path).expanduser()
    if not cookies or any(
        not isinstance(name, str) or not name.strip() or not isinstance(value, str) or not value
        for name, value in cookies.items()
    ):
        raise CookieFileError("Cannot save empty or invalid Zhihu cookies.")
    temporary_path: Path | None = None
    try:
        cookie_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{cookie_path.name}.",
            suffix=".tmp",
            dir=cookie_path.parent,
        )
        temporary_path = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as cookie_file:
            RuntimePlatform.detect().secure_private_file(temporary_path)
            json.dump(dict(cookies), cookie_file, ensure_ascii=False, indent=2)
            cookie_file.write("\n")
            cookie_file.flush()
            os.fsync(cookie_file.fileno())
        os.replace(temporary_path, cookie_path)
        return cookie_path
    except OSError:
        raise CookieFileError(
            f"Could not safely save Cookie file {cookie_path.name}; the previous file was preserved."
        ) from None
    finally:
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)


def load_cookies(path: Path) -> dict[str, str]:
    """Load non-empty name/value pairs from a browser cookie export."""

    cookie_path = Path(path)
    try:
        payload = json.loads(cookie_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise CookieFileError(f"Could not safely load Cookie file {cookie_path.name}.") from None

    cookies: dict[str, str] = {}
    pairs: Iterable[tuple[object, object]]
    if isinstance(payload, dict):
        pairs = payload.items()
    elif isinstance(payload, list):
        pairs = (
            (item.get("name"), item.get("value"))
            for item in payload
            if isinstance(item, dict) and _is_zhihu_cookie_domain(item.get("domain"))
        )
    else:
        raise CookieFileError(
            f"Cookie file {cookie_path.name} must contain a name/value list or object."
        )

    for name, value in pairs:
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        normalized_name = name.strip()
        normalized_value = value.strip()
        if not normalized_name or not normalized_value:
            continue
        if normalized_value.startswith("YOUR_") and normalized_value.endswith("_HERE"):
            continue
        cookies[normalized_name] = normalized_value
    return cookies


def _is_zhihu_cookie_domain(value: object) -> bool:
    """Limit full browser exports to cookies scoped to Zhihu origins."""

    if not isinstance(value, str):
        return False
    domain = value.strip().lstrip(".").casefold()
    return domain == "zhihu.com" or domain.endswith(".zhihu.com")


def diagnose_cookies(cookies: dict[str, str]) -> CookieDiagnostic:
    """Report missing core Cookie names without exposing any values."""

    missing = tuple(name for name in ("z_c0", "d_c0") if not cookies.get(name))
    return CookieDiagnostic(missing=missing)


def _absolute_zhihu_url(url_or_path: str) -> str:
    url = urljoin("https://www.zhihu.com/", url_or_path)
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    trusted_host = hostname == "zhihu.com" or hostname.endswith(".zhihu.com")
    if parsed.scheme != "https" or not trusted_host or parsed.username or parsed.password:
        raise UnsafeZhihuUrlError(
            "Refusing to send authenticated Zhihu request outside trusted HTTPS origins."
        )
    return url


def _retry_delay(headers: Mapping[str, str], retry_number: int, *, now: float) -> float:
    retry_after = next(
        (value for name, value in headers.items() if name.casefold() == "retry-after"),
        None,
    )
    if retry_after is not None:
        try:
            delay = float(retry_after)
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                delay = max(0.0, retry_at.timestamp() - now)
            except (TypeError, ValueError, OverflowError, OSError):
                raise RetryWaitError(
                    "Zhihu returned an invalid Retry-After value; "
                    "no retry was sent, try again later."
                ) from None
        if not math.isfinite(delay) or delay < 0:
            raise RetryWaitError(
                "Zhihu returned an invalid Retry-After value; no retry was sent, try again later."
            )
        return delay
    return min(float(2**retry_number), 8.0)
