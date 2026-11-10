"""Lever Postings API: ``GET api.lever.co/v0/postings/{company}?mode=json``.

The response is a JSON array of postings (Day-1 spike). There is no pagination when ``limit`` is
not set (paytm returned all 201 postings). Each posting carries its full description HTML, so
responses are large (paytm: 3.1 MB) and no parameter drops it.

Mapping: title=``text``; location=``categories.location``; dept=``categories.department`` else
``categories.team``; remote=``workplaceType == "remote"`` (values seen: onsite, remote, hybrid) or
"remote" in the location text; postedAt=``createdAt`` (epoch ms); url=``hostedUrl``; id=``id``
(uuid).
"""

from __future__ import annotations

from typing import Any

from ..classify import classify
from ..http import FetchError, HttpClient
from ..models import Job, from_epoch_ms
from ._util import clean, looks_remote

BASE = "https://api.lever.co/v0/postings"


def endpoint(token: str) -> str:
    return f"{BASE}/{token}?mode=json"


def fetch(client: HttpClient, token: str) -> list[Job]:
    url = endpoint(token)
    return normalize(client.get_json(url), url=url)


def normalize(payload: Any, url: str = "") -> list[Job]:
    if not isinstance(payload, list):
        raise FetchError("invalid Lever payload", url=url)
    jobs: list[Job] = []
    for raw in payload:
        if not isinstance(raw, dict) or not raw.get("id") or not raw.get("text"):
            continue
        cats = raw.get("categories") or {}
        title = clean(raw.get("text"))
        location = clean(cats.get("location"))
        dept = clean(cats.get("department")) or clean(cats.get("team"))
        workplace = clean(raw.get("workplaceType")).lower()
        jobs.append(
            Job(
                ats_type="lever",
                ats_job_id=str(raw["id"]),
                title=title,
                location=location,
                dept=dept,
                remote=workplace == "remote" or looks_remote(location),
                url=clean(raw.get("hostedUrl")),
                posted_at=from_epoch_ms(raw.get("createdAt")),
                family=classify(title),
            )
        )
    return jobs
