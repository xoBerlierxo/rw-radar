"""Greenhouse Job Board API.

Requests (Day-1 spike, see docs/spike-notes.md):
- ``GET boards-api.greenhouse.io/v1/boards/{token}/jobs``: the authoritative job list. Without
  ``?content=true`` it has no ``departments``.
- ``GET boards-api.greenhouse.io/v1/boards/{token}/departments``: departments with their jobs
  embedded (no HTML bodies), used to map job id -> department name. It omits jobs that have no
  department, so it cannot replace ``/jobs``.

Two light requests instead of ``?content=true``, which carries every job's HTML body
(rubrik: 2.0 MB vs 0.12 MB + 0.12 MB). Both must succeed: a missing department map would change
every content hash and rewrite every job doc. ``normalize`` also accepts ``content=true`` payloads,
where each job carries its own ``departments``.

Mapping: title=``title``; location=``location.name``; dept=department name; remote="remote" in
the location text; postedAt=``first_published`` (present on every spike job) else ``updated_at``;
url=``absolute_url``; id=``id`` (int).
"""

from __future__ import annotations

from typing import Any

from ..classify import classify
from ..http import FetchError, HttpClient
from ..models import Job, parse_iso
from ._util import clean, looks_remote

BASE = "https://boards-api.greenhouse.io/v1/boards"


def endpoint(token: str) -> str:
    return f"{BASE}/{token}/jobs"


def departments_endpoint(token: str) -> str:
    return f"{BASE}/{token}/departments"


def fetch(client: HttpClient, token: str) -> list[Job]:
    jobs_payload = client.get_json(endpoint(token))
    if isinstance(jobs_payload, dict) and jobs_payload.get("jobs") == []:
        return []  # empty board: no need for the department map
    departments_payload = client.get_json(departments_endpoint(token))
    return normalize(jobs_payload, departments_payload, url=endpoint(token))


def department_map(departments_payload: Any) -> dict[str, str]:
    """job id (str) -> department name, from the ``/departments`` payload."""
    if not isinstance(departments_payload, dict) or not isinstance(departments_payload.get("departments"), list):
        raise FetchError("invalid Greenhouse departments payload")
    out: dict[str, str] = {}
    for dept in departments_payload["departments"]:
        if not isinstance(dept, dict):
            continue
        name = clean(dept.get("name"))
        for job in dept.get("jobs") or []:
            if isinstance(job, dict) and job.get("id") is not None:
                out.setdefault(str(job["id"]), name)
    return out


def normalize(jobs_payload: Any, departments_payload: Any | None = None, url: str = "") -> list[Job]:
    if not isinstance(jobs_payload, dict) or not isinstance(jobs_payload.get("jobs"), list):
        raise FetchError("invalid Greenhouse jobs payload", url=url)
    depts = department_map(departments_payload) if departments_payload is not None else {}
    jobs: list[Job] = []
    for raw in jobs_payload["jobs"]:
        if not isinstance(raw, dict) or raw.get("id") is None or not raw.get("title"):
            continue
        job_id = str(raw["id"])
        title = clean(raw.get("title"))
        location = clean((raw.get("location") or {}).get("name"))
        own_depts = raw.get("departments")
        if isinstance(own_depts, list) and own_depts:  # content=true payload
            dept = clean((own_depts[0] or {}).get("name"))
        else:
            dept = depts.get(job_id, "")
        posted = parse_iso(raw.get("first_published")) or parse_iso(raw.get("updated_at"))
        jobs.append(
            Job(
                ats_type="greenhouse",
                ats_job_id=job_id,
                title=title,
                location=location,
                dept=dept,
                remote=looks_remote(location),
                url=clean(raw.get("absolute_url")),
                posted_at=posted,
                family=classify(title),
            )
        )
    return jobs
