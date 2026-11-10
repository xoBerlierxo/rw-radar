"""http.py: per-host rate limiter, retries, User-Agent (PLAN §4.1, §11 "§5 User-Agent + 1 req/s/host")."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from rwradar_poller import config
from rwradar_poller.http import FetchError, HostRateLimiter, HttpClient


class FakeTime:
    def __init__(self) -> None:
        self.t = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


def test_limiter_spaces_requests_to_same_host() -> None:
    ft = FakeTime()
    lim = HostRateLimiter(1.0, clock=ft.clock, sleep=ft.sleep)
    times = []
    for _ in range(4):
        lim.wait("api.lever.co")
        times.append(ft.t)
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert all(g >= 1.0 - 1e-9 for g in gaps)
    assert times[0] == 1000.0  # first request is not delayed


def test_limiter_does_not_delay_other_hosts() -> None:
    ft = FakeTime()
    lim = HostRateLimiter(1.0, clock=ft.clock, sleep=ft.sleep)
    lim.wait("api.lever.co")
    assert lim.wait("api.ashbyhq.com") == 0.0
    assert lim.wait("boards-api.greenhouse.io") == 0.0
    assert ft.sleeps == []


def test_limiter_no_wait_after_interval_passed() -> None:
    ft = FakeTime()
    lim = HostRateLimiter(1.0, clock=ft.clock, sleep=ft.sleep)
    lim.wait("inc42.com")
    ft.t += 2.5
    assert lim.wait("inc42.com") == 0.0


def test_limiter_partial_wait_and_case_insensitive_host() -> None:
    ft = FakeTime()
    lim = HostRateLimiter(1.0, clock=ft.clock, sleep=ft.sleep)
    lim.wait("News.Google.com")
    ft.t += 0.4
    assert lim.wait("news.google.com") == pytest.approx(0.6)


class FakeResponse:
    def __init__(self, status: int, body: Any = None) -> None:
        self.status_code = status
        self._body = body
        self.content = b"" if body is None else str(body).encode()

    def json(self) -> Any:
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, script: list[Any]) -> None:
        self.headers: dict[str, str] = {}
        self.script = list(script)
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, params: Any = None, timeout: float = 0) -> FakeResponse:
        self.calls.append((url, timeout))
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _client(script: list[Any]) -> tuple[HttpClient, FakeSession, FakeTime]:
    ft = FakeTime()
    session = FakeSession(script)
    client = HttpClient(
        session=session,  # type: ignore[arg-type]
        limiter=HostRateLimiter(1.0, clock=ft.clock, sleep=ft.sleep),
        sleep=ft.sleep,
        user_agent="RWRadarPoller/0.1 (+https://github.com/example/rw-radar)",
    )
    return client, session, ft


def test_retries_5xx_then_succeeds() -> None:
    client, session, ft = _client([FakeResponse(503), FakeResponse(502), FakeResponse(200, {"jobs": []})])
    assert client.get_json("https://api.ashbyhq.com/posting-api/job-board/x") == {"jobs": []}
    assert len(session.calls) == 3
    assert all(timeout == config.HTTP_TIMEOUT_S for _, timeout in session.calls)


def test_gives_up_after_two_retries() -> None:
    client, session, _ = _client([FakeResponse(500), FakeResponse(500), FakeResponse(500), FakeResponse(200)])
    with pytest.raises(FetchError) as info:
        client.get("https://api.lever.co/v0/postings/x?mode=json")
    assert info.value.status == 500
    assert len(session.calls) == 3


def test_no_retry_on_4xx() -> None:
    client, session, _ = _client([FakeResponse(404), FakeResponse(200)])
    with pytest.raises(FetchError) as info:
        client.get("https://boards-api.greenhouse.io/v1/boards/nope/jobs")
    assert info.value.status == 404
    assert len(session.calls) == 1


def test_no_retry_on_429() -> None:
    client, session, _ = _client([FakeResponse(429), FakeResponse(200)])
    with pytest.raises(FetchError):
        client.get("https://news.google.com/rss/search?q=x")
    assert len(session.calls) == 1


def test_retries_timeouts() -> None:
    client, session, _ = _client([requests.Timeout(), FakeResponse(200, {"ok": 1})])
    assert client.get_json("https://inc42.com/feed/") == {"ok": 1}
    assert len(session.calls) == 2


def test_timeout_every_attempt_raises_fetch_error_without_status() -> None:
    client, _, _ = _client([requests.Timeout(), requests.ConnectionError(), requests.Timeout()])
    with pytest.raises(FetchError) as info:
        client.get("https://entrackr.com/rss")
    assert info.value.status is None


def test_retries_respect_rate_limit_and_backoff() -> None:
    client, _, ft = _client([FakeResponse(503), FakeResponse(503), FakeResponse(200)])
    client.get("https://yourstory.com/feed")
    assert ft.sleeps[:2] == [2.0, 4.0]  # exponential backoff between attempts


def test_invalid_json_is_fetch_error() -> None:
    client, _, _ = _client([FakeResponse(200, ValueError("bad json"))])
    with pytest.raises(FetchError):
        client.get_json("https://api.lever.co/v0/postings/x?mode=json")


def test_user_agent_header() -> None:
    client, session, _ = _client([])
    assert session.headers["User-Agent"] == "RWRadarPoller/0.1 (+https://github.com/example/rw-radar)"


def test_user_agent_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RWRADAR_REPO_URL", raising=False)
    assert config.user_agent() == "RWRadarPoller/0.1"
    monkeypatch.setenv("RWRADAR_REPO_URL", "https://github.com/acme/rw-radar")
    assert config.user_agent() == "RWRadarPoller/0.1 (+https://github.com/acme/rw-radar)"
