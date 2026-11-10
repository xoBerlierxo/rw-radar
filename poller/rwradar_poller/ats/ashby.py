"""Ashby Job Posting API: ``GET api.ashbyhq.com/posting-api/job-board/{name}``.

Response: ``{"apiVersion": "1", "jobs": [...]}`` (Day-1 spike). Unknown boards return 404.

Mapping: title=``title``; location=``location``; dept=``department`` else ``team``;
remote=``isRemote is True`` or ``workplaceType == "Remote"`` (values seen: OnSite, Remote, null;
``isRemote`` can be null) or "remote" in the location text; postedAt=``publishedAt`` (ISO);
url=``jobUrl``; id=``id`` (uuid). Postings with ``isListed == false`` are skipped.
"""

from __future__ import annotations

from typing import Any

from ..classify import classify
from ..http import FetchError, HttpClient
from ..models import Job, parse_iso
from ._util import clean, looks_remote

BASE = "https://api.ashbyhq.com/posting-api/job-board"


def endpoint(token: str) -> str:
    return f"{BASE}/{token}"


def fetch(client: HttpClient, token: str) -> list[Job]:
    url = endpoint(token)
    return normalize(client.get_json(url), url=url)


def normalize(payload: Any, url: str = "") -> list[Job]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise FetchError("invalid Ashby payload", url=url)
    jobs: list[Job] = []
    for raw in payload["jobs"]:
        if not isinstance(raw, dict) or not raw.get("id") or not raw.get("title"):
            continue
        if raw.get("isListed") is False:
            continue
        title = clean(raw.get("title"))
        location = clean(raw.get("location"))
        workplace = clean(raw.get("workplaceType")).lower()
        jobs.append(
            Job(
                ats_type="ashby",
                ats_job_id=str(raw["id"]),
                title=title,
                location=location,
                dept=clean(raw.get("department")) or clean(raw.get("team")),
                remote=raw.get("isRemote") is True or workplace == "remote" or looks_remote(location),
                url=clean(raw.get("jobUrl")),
                posted_at=parse_iso(raw.get("publishedAt")),
                family=classify(title),
            )
        )
    return jobs
