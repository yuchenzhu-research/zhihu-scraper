"""Download and select media assets without third-party dependencies."""

from __future__ import annotations

import hashlib
import os
import re
import time
from collections.abc import Callable, Iterable, Mapping
from configparser import ConfigParser
from configparser import Error as ConfigError
from contextlib import AbstractContextManager
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from http.client import IncompleteRead
from ipaddress import ip_address
from pathlib import Path
from socket import SOCK_STREAM, getaddrinfo
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


@dataclass(frozen=True, slots=True)
class MediaCandidate:
    """One downloadable rendition of the same media asset."""

    source_url: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class MediaDownloadReceipt:
    """Observable result of a completed media download."""

    source_url: str
    destination: Path
    resumed_from: int
    bytes_total: int


class MediaDownloadError(RuntimeError):
    """Raised when a response cannot safely produce a complete media file."""


class _RetryableMediaError(MediaDownloadError):
    """Internal signal for a bounded retry."""


class _SafeMediaRedirectHandler(HTTPRedirectHandler):
    """Validate every redirect target immediately before urllib follows it."""

    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> Request | None:
        redirect_url = urljoin(request.full_url, new_url)
        _validate_media_url(redirect_url)
        _resolve_media_host(redirect_url)
        return cast(
            Request | None,
            super().redirect_request(
                request,
                file_pointer,
                code,
                message,
                headers,
                redirect_url,
            ),
        )


class _HttpResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    def __enter__(self) -> _HttpResponse: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> object: ...

    def read(self, size: int = -1) -> bytes: ...


HttpTransport = Callable[[Request], AbstractContextManager[_HttpResponse]]


@dataclass(frozen=True, slots=True)
class _ResumeState:
    resource: str
    validator_header: str
    validator: str
    total: int | None


@dataclass(frozen=True, slots=True)
class _ResponsePlan:
    offset: int
    total: int | None
    length: int | None


def media_source_identity(source_url: str) -> str:
    """Identify a resource independently of Zhihu's expiring URL signatures."""

    parsed = urlsplit(source_url)
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in {"pkey", "expiration"}
        ]
    )
    return parsed._replace(query=query, fragment="").geturl()


def select_highest_resolution(candidates: Iterable[MediaCandidate]) -> MediaCandidate:
    """Return the largest rendition, keeping input order for exact ties."""

    available = tuple(candidates)
    if not available:
        raise ValueError("at least one media candidate is required")
    return max(available, key=lambda candidate: candidate.width * candidate.height)


def download_media(
    source_url: str,
    destination: Path,
    *,
    transport: HttpTransport | None = None,
    proxy: str | None = None,
    timeout: float = 30.0,
    max_retries: int = 2,
    sleep: Callable[[float], None] = time.sleep,
    chunk_size: int = 1024 * 1024,
    expected_size: int | None = None,
) -> MediaDownloadReceipt:
    """Download media, validating known sizes and resuming only with a validator.

    A positive ``expected_size`` checks existing files without a network request.
    Without it, an existing nonempty file is reused without remote verification.
    Partial files need a matching resource and a persisted strong validator;
    otherwise the next GET restarts the download. Resume state is temporary.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if expected_size is not None and (
        not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size <= 0
    ):
        raise ValueError("expected_size must be a positive integer")
    if (
        not isinstance(max_retries, int)
        or isinstance(max_retries, bool)
        or not 0 <= max_retries <= 10
    ):
        raise ValueError("max_retries must be an integer from 0 to 10")
    _validate_media_url(source_url)

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial_path = destination.with_name(f"{destination.name}.part")
    state_path = destination.with_name(f"{destination.name}.part.resume")
    existing_size = destination.stat().st_size if destination.is_file() else 0
    if existing_size > 0 and (expected_size is None or existing_size == expected_size):
        state_path.unlink(missing_ok=True)
        return MediaDownloadReceipt(
            source_url=source_url,
            destination=destination,
            resumed_from=0,
            bytes_total=existing_size,
        )

    resource = hashlib.sha256(media_source_identity(source_url).encode()).hexdigest()
    opener = None
    if transport is None:
        handlers: list[Any] = []
        if proxy is not None:
            handlers.append(ProxyHandler({"http": proxy, "https": proxy}))
        handlers.append(_SafeMediaRedirectHandler())
        opener = build_opener(*handlers)

    for retry_number in range(max_retries + 1):
        partial_size = partial_path.stat().st_size if partial_path.is_file() else 0
        state = _read_resume_state(state_path, resource=resource)
        if (
            state is None
            or not partial_size
            or (state.total is not None and partial_size >= state.total)
            or (expected_size is not None and partial_size >= expected_size)
            or (expected_size is not None and state.total not in {None, expected_size})
        ):
            state = None
            partial_size = 0
        headers = {
            "Referer": "https://www.zhihu.com/",
            "User-Agent": "zhihu-scraper/4",
            "Accept-Encoding": "identity",
        }
        if state is not None:
            headers["Range"] = f"bytes={partial_size}-"
            headers["If-Range"] = state.validator
        request = Request(source_url, headers=headers, method="GET")

        try:
            # Keep the DNS check adjacent to the actual open. urllib does not
            # expose a supported way to pin an HTTPS connection to this result,
            # so every retry and every redirect is resolved and checked again.
            _resolve_media_host(source_url)
            with _open_response(
                request,
                transport=transport,
                opener=opener,
                timeout=timeout,
            ) as response:
                status = _response_status(response)
                redirect_location = _header(response.headers, "Location")
                if 300 <= status <= 399 and redirect_location is not None:
                    redirect_url = urljoin(source_url, redirect_location)
                    _validate_media_url(redirect_url)
                    _resolve_media_host(redirect_url)
                    raise MediaDownloadError(
                        "the media transport returned an unhandled HTTP redirect"
                    )
                if status == 429 or 500 <= status <= 599:
                    raise _RetryableMediaError(f"temporary HTTP {status}")
                plan = _response_plan(
                    status=status,
                    headers=response.headers,
                    partial_size=partial_size,
                )
                if state is not None and plan.offset:
                    validator = _header(response.headers, state.validator_header)
                    if validator is not None and validator != state.validator:
                        state_path.unlink(missing_ok=True)
                        raise MediaDownloadError("partial response changed the resource validator")
                    if state.total is not None and plan.total not in {None, state.total}:
                        raise MediaDownloadError("partial response changed the resource length")
                expected_total = plan.total or (state.total if state and plan.offset else None)
                if expected_size is not None:
                    if expected_total not in {None, expected_size}:
                        raise MediaDownloadError("response length does not match the expected size")
                    expected_total = expected_size
                if plan.offset and expected_total is None:
                    raise MediaDownloadError(
                        "partial response did not establish the complete length"
                    )
                resumed_from = plan.offset
                mode = "ab" if resumed_from else "wb"
                with partial_path.open(mode) as output:
                    _write_resume_state(
                        state_path,
                        _response_resume_state(
                            response.headers, resource=resource, total=expected_total
                        )
                        or (state if resumed_from else None),
                    )
                    while True:
                        try:
                            chunk = response.read(chunk_size)
                        except IncompleteRead as error:
                            if error.partial:
                                output.write(error.partial)
                            raise _RetryableMediaError("media response interrupted") from None
                        except OSError:
                            raise _RetryableMediaError("media response interrupted") from None
                        if not chunk:
                            break
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())

            bytes_total = partial_path.stat().st_size
            received_length = bytes_total - resumed_from
            if plan.length is not None and received_length != plan.length:
                if received_length > plan.length:
                    state_path.unlink(missing_ok=True)
                raise _RetryableMediaError(
                    "media response body did not match its advertised length"
                )
            if expected_total is not None and bytes_total != expected_total:
                if bytes_total > expected_total:
                    state_path.unlink(missing_ok=True)
                raise _RetryableMediaError("the response ended before the advertised length")

            os.replace(partial_path, destination)
            state_path.unlink(missing_ok=True)
            return MediaDownloadReceipt(
                source_url=source_url,
                destination=destination,
                resumed_from=resumed_from,
                bytes_total=bytes_total,
            )
        except HTTPError as error:
            if error.code != 429 and not 500 <= error.code <= 599:
                raise MediaDownloadError(f"unexpected HTTP status {error.code}") from None
            retry_error: BaseException = error
        except _RetryableMediaError as error:
            retry_error = error
        except (ConnectionError, TimeoutError, URLError) as error:
            retry_error = error

        if retry_number < max_retries:
            sleep(min(float(2**retry_number), 8.0))
            continue
        if isinstance(retry_error, _RetryableMediaError):
            raise MediaDownloadError(str(retry_error)) from None
        raise MediaDownloadError("media request failed after limited retries") from None

    raise AssertionError("media retry loop must return or raise")


def _open_response(
    request: Request,
    *,
    transport: HttpTransport | None,
    opener: Any | None,
    timeout: float,
) -> AbstractContextManager[_HttpResponse]:
    if transport is not None:
        return transport(request)
    if opener is not None:
        return cast(
            AbstractContextManager[_HttpResponse],
            opener.open(request, timeout=timeout),
        )
    raise AssertionError("a default urllib opener must be configured")


def _response_status(response: _HttpResponse) -> int:
    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        status = getcode() if getcode is not None else None
    if status is None:
        raise MediaDownloadError("HTTP response did not expose a status code")
    return int(status)


def _response_plan(
    *,
    status: int,
    headers: Mapping[str, str],
    partial_size: int,
) -> _ResponsePlan:
    content_length = _header(headers, "Content-Length")
    if content_length is not None and not re.fullmatch(r"\d+", content_length):
        raise MediaDownloadError("response did not include a valid Content-Length")
    length = int(content_length) if content_length is not None else None
    if status == 200:
        return _ResponsePlan(0, length, length)

    if status != 206:
        raise MediaDownloadError(f"unexpected HTTP status {status}")
    if not partial_size:
        raise MediaDownloadError("unsolicited partial response cannot complete the download")

    content_range = _header(headers, "Content-Range")
    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", content_range or "")
    if match is None:
        raise MediaDownloadError("partial response did not include a valid Content-Range")

    start, end, total = match.groups()
    start_offset = int(start)
    end_offset = int(end)
    total_size = None if total == "*" else int(total)
    if start_offset != partial_size:
        raise MediaDownloadError(
            f"partial response started at byte {start_offset}, expected {partial_size}"
        )
    if end_offset < start_offset or (total_size is not None and end_offset >= total_size):
        raise MediaDownloadError("partial response included an inconsistent Content-Range")
    range_length = end_offset - start_offset + 1
    if length is not None and length != range_length:
        raise MediaDownloadError("partial response Content-Length did not match Content-Range")
    return _ResponsePlan(partial_size, total_size, range_length)


def _response_resume_state(
    headers: Mapping[str, str], *, resource: str, total: int | None
) -> _ResumeState | None:
    etag = _header(headers, "ETag")
    if etag is not None:
        if _is_strong_etag(etag):
            return _ResumeState(resource, "ETag", etag, total)
        return None
    modified = _header(headers, "Last-Modified")
    response_date = _header(headers, "Date")
    if modified is not None and response_date is not None:
        try:
            modified_at = parsedate_to_datetime(modified)
            response_at = parsedate_to_datetime(response_date)
            if modified_at.tzinfo is None or response_at.tzinfo is None:
                return None
            elapsed = (response_at - modified_at).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
        if elapsed >= 60 and "\n" not in modified and "\r" not in modified:
            return _ResumeState(resource, "Last-Modified", modified, total)
    return None


def _is_strong_etag(value: str) -> bool:
    return re.fullmatch(r'"[^"\x00-\x20\x7f]*"', value) is not None


def _read_resume_state(path: Path, *, resource: str) -> _ResumeState | None:
    try:
        if path.stat().st_size > 8192:
            return None
        config = ConfigParser(interpolation=None)
        config.read_string(path.read_text(encoding="utf-8"))
        saved = config["resume"]
        validator_header = saved["validator_header"]
        validator = saved["validator"]
        total = int(saved["total"]) if saved["total"] else None
        if saved["resource"] != resource or (total is not None and total <= 0):
            return None
        if validator_header == "ETag":
            if not _is_strong_etag(validator):
                return None
        elif validator_header == "Last-Modified":
            if parsedate_to_datetime(validator).tzinfo is None:
                return None
            if "\n" in validator or "\r" in validator:
                return None
        else:
            return None
        return _ResumeState(resource, validator_header, validator, total)
    except (OSError, UnicodeError, ConfigError, KeyError, ValueError, TypeError, OverflowError):
        return None


def _write_resume_state(path: Path, state: _ResumeState | None) -> None:
    if state is None:
        path.unlink(missing_ok=True)
        return
    config = ConfigParser(interpolation=None)
    config["resume"] = {
        "resource": state.resource,
        "validator_header": state.validator_header,
        "validator": state.validator,
        "total": str(state.total) if state.total is not None else "",
    }
    temporary_path = path.with_name(f"{path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as output:
            config.write(output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _header(headers: Mapping[str, str], name: str) -> str | None:
    direct = headers.get(name)
    if direct is not None:
        return direct
    lowered_name = name.casefold()
    return next(
        (value for key, value in headers.items() if key.casefold() == lowered_name),
        None,
    )


def _validate_media_url(source_url: str) -> None:
    if any(character.isspace() or ord(character) < 32 for character in source_url):
        raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL")
    try:
        parsed = urlsplit(source_url)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        parsed.port
    except ValueError:
        raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or hostname == "localhost"
        or hostname.endswith(".localhost")
    ):
        raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL")
    try:
        address = ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL")


def _resolve_media_host(source_url: str) -> None:
    """Reject a hostname unless every address currently resolved for it is global."""

    parsed = urlsplit(source_url)
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    if _is_official_media_host(parsed.scheme, hostname):
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        resolved = getaddrinfo(hostname, port, type=SOCK_STREAM)
    except OSError:
        raise _RetryableMediaError("media host resolution failed") from None
    if not resolved:
        raise _RetryableMediaError("media host resolution returned no addresses")

    for _family, _socket_type, _protocol, _canonical_name, socket_address in resolved:
        try:
            address = ip_address(str(socket_address[0]).split("%", maxsplit=1)[0])
        except (IndexError, TypeError, ValueError):
            raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL") from None
        if not address.is_global:
            raise MediaDownloadError("media source must be a trusted HTTP or HTTPS URL")


def _is_official_media_host(scheme: str, hostname: str) -> bool:
    """Trust Zhihu's HTTPS CDNs even behind proxy fake-IP DNS."""

    if scheme != "https":
        return False
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ("zhimg.com", "vzuu.com")
    )
