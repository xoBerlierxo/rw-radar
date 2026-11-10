"""Run log: one ``pollerRuns/{runId}`` doc per run, including failed runs (CLAUDE.md §4.2, D4).

Counts (all ints, all present on every run so dashboards can sum them):
- ``companies``: companies attempted this run (jobs) / companies in the registry (news)
- ``fetched``: successful fetches (ATS boards for jobs, feeds for news)
- ``new``, ``changed``, ``closed``, ``reopened``: job doc changes (jobs only)
- ``pushed``: pushes sent (or that would be sent, in ``--dry-run``); ``throttled``: pushes held back
- ``failedFetches``: boards/feeds that failed (logged in ``errors`` too)
- ``newsItems``: feed items read; ``newsMatched``: new items matched to >= 1 company (news only)

``delays`` holds minutes from ``postedAt`` to push for each new job in a pushed batch (jobs only).
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

COUNT_KEYS: tuple[str, ...] = (
    "companies",
    "fetched",
    "new",
    "changed",
    "closed",
    "reopened",
    "pushed",
    "throttled",
    "failedFetches",
    "newsItems",
    "newsMatched",
)
MAX_ERRORS = 200  # keep the run doc small even if every source fails


class RunLog:
    def __init__(self, kind: str, started_at: datetime) -> None:
        if kind not in ("jobs", "news"):
            raise ValueError(kind)
        self.kind = kind
        self.started_at = started_at
        self.run_id = f"{kind}-{started_at:%Y%m%dT%H%M%SZ}-{secrets.token_hex(2)}"
        self.counts: dict[str, int] = {key: 0 for key in COUNT_KEYS}
        self.errors: list[dict[str, Any]] = []
        self.delays: list[float] = []

    def inc(self, key: str, by: int = 1) -> None:
        self.counts[key] += by

    def error(
        self,
        message: str,
        *,
        company_id: str | None = None,
        source: str | None = None,
        status: int | None = None,
    ) -> None:
        if len(self.errors) >= MAX_ERRORS:
            return
        entry: dict[str, Any] = {"message": message[:500]}
        if company_id is not None:
            entry["companyId"] = company_id
        if source is not None:
            entry["source"] = source
        if status is not None:
            entry["status"] = status
        self.errors.append(entry)

    def add_delay(self, minutes: float) -> None:
        self.delays.append(round(float(minutes), 1))

    def to_doc(self, finished_at: datetime) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "startedAt": self.started_at,
            "finishedAt": finished_at,
            "durationMs": int((finished_at - self.started_at).total_seconds() * 1000),
            "counts": dict(self.counts),
            "errors": list(self.errors),
            "delays": list(self.delays),
        }
