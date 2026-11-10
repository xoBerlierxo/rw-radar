"""ATS adapters. Each module exposes ``fetch(client, token) -> list[Job]`` (raises ``FetchError``),
a pure ``normalize(...)`` used by the fixture tests, and ``endpoint(token)``.
"""

from __future__ import annotations

from typing import Callable

from ..http import HttpClient
from ..models import Job
from . import ashby, greenhouse, lever

ATS_TYPES: tuple[str, ...] = ("greenhouse", "lever", "ashby")

_FETCHERS: dict[str, Callable[[HttpClient, str], list[Job]]] = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
}

_ENDPOINTS: dict[str, Callable[[str], str]] = {
    "greenhouse": greenhouse.endpoint,
    "lever": lever.endpoint,
    "ashby": ashby.endpoint,
}


def fetch_jobs(client: HttpClient, ats_type: str, token: str) -> list[Job]:
    try:
        fetcher = _FETCHERS[ats_type]
    except KeyError:
        raise ValueError(f"unknown ATS type {ats_type!r}") from None
    return fetcher(client, token)


def endpoint(ats_type: str, token: str) -> str:
    return _ENDPOINTS[ats_type](token)
