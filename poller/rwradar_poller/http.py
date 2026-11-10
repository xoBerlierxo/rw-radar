"""Shared HTTP client: User-Agent, 1 req/s per host, 15 s timeout, retries on 5xx/timeouts.

Every request made by the poller goes through :class:`HttpClient`, so the rate limit holds across
adapters and feeds (spec §5: at most 1 request/second/host).

Retry policy (CLAUDE.md §4.4): up to 2 retries with exponential backoff on HTTP 5xx, timeouts and
connection errors. No retry on 4xx (including 429): the caller logs the failure and moves on.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

import requests

from . import config

log = logging.getLogger(__name__)


class FetchError(Exception):
    """A source could not be fetched or returned an unusable payload.

    ``status`` is the HTTP status when there was a response, else ``None`` (timeout, DNS, bad JSON).
    """

    def __init__(self, message: str, *, url: str = "", status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.url = url
        self.status = status

    def __str__(self) -> str:
        status = f" (HTTP {self.status})" if self.status is not None else ""
        return f"{self.message}{status}"


class HostRateLimiter:
    """Allows at most one request per ``min_interval`` seconds per host.

    ``clock`` and ``sleep`` are injectable so the limiter can be tested without real waiting.
    """

    def __init__(
        self,
        min_interval: float = config.HTTP_MIN_INTERVAL_PER_HOST_S,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> float:
        """Block until a request to ``host`` is allowed; returns the seconds slept."""
        host = host.lower()
        with self._lock:
            now = self._clock()
            last = self._last.get(host)
            delay = 0.0
            if last is not None:
                delay = max(0.0, last + self.min_interval - now)
            if delay > 0:
                self._sleep(delay)
                now = self._clock()
            # Record the slot we actually used (never earlier than the planned one).
            self._last[host] = max(now, (last + self.min_interval) if last is not None else now)
            return delay


class HttpClient:
    """Thin wrapper over ``requests.Session`` with the poller's politeness rules."""

    def __init__(
        self,
        session: requests.Session | None = None,
        limiter: HostRateLimiter | None = None,
        timeout: float = config.HTTP_TIMEOUT_S,
        retries: int = config.HTTP_RETRIES,
        backoff_base: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        user_agent: str | None = None,
    ) -> None:
        self.session = session if session is not None else requests.Session()
        self.session.headers["User-Agent"] = user_agent or config.user_agent()
        self.limiter = limiter if limiter is not None else HostRateLimiter()
        self.timeout = timeout
        self.retries = retries
        self.backoff_base = backoff_base
        self._sleep = sleep

    def get(self, url: str, params: Mapping[str, str] | None = None) -> requests.Response:
        """GET ``url``; returns the response only for HTTP 200, else raises :class:`FetchError`."""
        host = urlsplit(url).netloc
        attempts = self.retries + 1
        last_error: FetchError | None = None
        for attempt in range(attempts):
            if attempt:
                backoff = self.backoff_base * (2 ** (attempt - 1))
                log.info("retrying %s in %.0fs (attempt %d/%d)", url, backoff, attempt + 1, attempts)
                self._sleep(backoff)
            self.limiter.wait(host)
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.Timeout:
                last_error = FetchError("timeout", url=url)
                continue
            except requests.ConnectionError as exc:
                last_error = FetchError(f"connection error: {type(exc).__name__}", url=url)
                continue
            except requests.RequestException as exc:  # invalid URL etc.: not retryable
                raise FetchError(f"request failed: {type(exc).__name__}", url=url) from exc
            if resp.status_code == 200:
                return resp
            if 500 <= resp.status_code < 600:
                last_error = FetchError("server error", url=url, status=resp.status_code)
                continue
            raise FetchError("HTTP error", url=url, status=resp.status_code)
        assert last_error is not None
        raise last_error

    def get_json(self, url: str, params: Mapping[str, str] | None = None) -> Any:
        resp = self.get(url, params=params)
        try:
            return resp.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise FetchError("invalid JSON", url=url, status=resp.status_code) from exc

    def get_bytes(self, url: str, params: Mapping[str, str] | None = None) -> bytes:
        return self.get(url, params=params).content
