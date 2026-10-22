"""Shared server-directed retry timing for authenticated requests and media."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping
from datetime import UTC
from email.utils import parsedate_to_datetime


class RetryWaitError(RuntimeError):
    """Stop when retry timing cannot be honored within a bounded wait.

    This is deliberately not a transport or HTTP failure eligible for browser
    fallback, which would bypass the server's requested waiting period.
    """


class RetryBudget:
    """Honor server delays and account for all waits before issuing another request."""

    def __init__(
        self, *, sleep: Callable[[float], None], clock: Callable[[], float] = time.time
    ) -> None:
        self._sleep = sleep
        self._clock = clock
        self._waited = 0.0

    def wait(self, delay: float) -> None:
        if not math.isfinite(delay) or delay < 0 or delay > 60.0 - self._waited:
            raise RetryWaitError(
                "Retry would exceed the 60-second total waiting budget; "
                "no early retry was sent, try again later."
            )
        self._sleep(delay)
        self._waited += delay

    def retry(self, headers: Mapping[str, str], retry_number: int) -> None:
        self.wait(_retry_delay(headers, retry_number, now=self._clock()))


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
                    "Server returned an invalid Retry-After value; "
                    "no retry was sent, try again later."
                ) from None
        if not math.isfinite(delay) or delay < 0:
            raise RetryWaitError(
                "Server returned an invalid Retry-After value; no retry was sent, try again later."
            )
        return delay
    return min(float(2**retry_number), 8.0)
