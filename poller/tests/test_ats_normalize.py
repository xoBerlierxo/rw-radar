"""Adapter normalization against saved real responses (PLAN §8, §4.2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rwradar_poller import config
from rwradar_poller.ats import ashby, greenhouse, lever
from rwradar_poller.http import FetchError
from rwradar_poller.models import Job

from .conftest import load_json


def _check_common(jobs: list[Job], ats_type: str) -> None:
    assert jobs, "fixture should produce jobs"
    ids = [j.doc_id for j in jobs]
    assert len(ids) == len(set(ids))
    for j in jobs:
        assert j.ats_type == ats_type
        assert j.doc_id == f"{ats_type}_{j.ats_job_id}"
        assert j.title and j.title == j.title.strip()
        assert j.url.startswith("https://")
        assert j.family in config.FAMILY_KEYS
        assert isinstance(j.remote, bool)
        assert j.posted_at is not None and j.posted_at.tzinfo is not None
        assert j.posted_at.utcoffset().total_seconds() == 0
        assert len(j.content_hash()) == 40


# --- Greenhouse --------------------------------------------------------------------------------


@pytest.mark.parametrize("token,count", [("groww", 9), ("druva", 27), ("rubrik", 30)])
def test_greenhouse_fixtures(token: str, count: int) -> None:
    jobs = greenhouse.normalize(load_json(f"greenhouse_{token}.json"), load_json(f"greenhouse_{token}_departments.json"))
    assert len(jobs) == count
    _check_common(jobs, "greenhouse")


def test_greenhouse_field_mapping() -> None:
    jobs = greenhouse.normalize(load_json("greenhouse_groww.json"), load_json("greenhouse_groww_departments.json"))
    job = jobs[0]
    assert job.doc_id == "greenhouse_4970739101"
    assert job.title == "Assistant Manager - Internal Audit"
    assert job.location == "Bengaluru-VTP, India"
    assert job.dept == "Internal Controls"  # from /departments
    assert job.remote is False
    assert job.url == "https://job-boards.eu.greenhouse.io/groww/jobs/4970739101"
    # first_published "2026-09-14T03:49:28-04:00" -> UTC
    assert job.posted_at == datetime(2026, 9, 14, 7, 49, 28, tzinfo=timezone.utc)
    assert job.family == "other"


def test_greenhouse_remote_and_missing_department() -> None:
    jobs = greenhouse.normalize(load_json("greenhouse_rubrik.json"), load_json("greenhouse_rubrik_departments.json"))
    remote = [j for j in jobs if j.remote]
    assert remote and all("remote" in j.location.lower() for j in remote)
    # One rubrik job has no department: /departments omits it, so dept is "".
    no_dept = [j for j in jobs if not j.dept]
    assert [j.doc_id for j in no_dept] == ["greenhouse_2333116"]


def test_greenhouse_content_true_payload_matches_department_map() -> None:
    plain = {
        j.doc_id: j
        for j in greenhouse.normalize(load_json("greenhouse_groww.json"), load_json("greenhouse_groww_departments.json"))
    }
    content = greenhouse.normalize(load_json("greenhouse_groww_content.json"))
    overlap = [j for j in content if j.doc_id in plain]
    assert overlap
    for j in overlap:
        assert j.dept == plain[j.doc_id].dept
        assert j.content_hash() == plain[j.doc_id].content_hash()


def test_greenhouse_posted_falls_back_to_updated_at() -> None:
    payload = {"jobs": [{"id": 1, "title": "SDE 2", "updated_at": "2026-01-02T03:04:05Z", "location": {"name": "Remote - India"},
                         "absolute_url": "https://x.test/1"}]}
    [job] = greenhouse.normalize(payload, {"departments": []})
    assert job.posted_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert job.remote is True
    assert job.family == "eng"


@pytest.mark.parametrize("payload", [None, [], {"error": "nope"}, {"jobs": "x"}])
def test_greenhouse_invalid_payload(payload: object) -> None:
    with pytest.raises(FetchError):
        greenhouse.normalize(payload, {"departments": []})


def test_greenhouse_invalid_departments_payload() -> None:
    with pytest.raises(FetchError):
        greenhouse.normalize(load_json("greenhouse_groww.json"), {"status": 404})


# --- Lever -------------------------------------------------------------------------------------


@pytest.mark.parametrize("token,count", [("cred", 14), ("zeta", 28), ("paytm", 30), ("meesho", 30)])
def test_lever_fixtures(token: str, count: int) -> None:
    jobs = lever.normalize(load_json(f"lever_{token}.json"))
    assert len(jobs) == count
    _check_common(jobs, "lever")
    assert all(j.dept for j in jobs)


def test_lever_field_mapping() -> None:
    job = lever.normalize(load_json("lever_cred.json"))[0]
    assert job.doc_id == "lever_aa98a938-af3a-45f5-851d-966b2b5bad33"
    assert job.title == "accounts payable manager"
    assert job.location == "hyderabad"
    assert job.dept == "Prefr"  # categories.department
    assert job.remote is False
    assert job.url == "https://jobs.lever.co/cred/aa98a938-af3a-45f5-851d-966b2b5bad33"
    assert job.posted_at == datetime(2026, 9, 28, 5, 39, 42, 21000, tzinfo=timezone.utc)  # createdAt ms


def test_lever_workplace_type_remote() -> None:
    raw = load_json("lever_zeta.json")
    jobs = {j.ats_job_id: j for j in lever.normalize(raw)}
    for posting in raw:
        expected = posting["workplaceType"] == "remote"
        assert jobs[posting["id"]].remote is expected
    assert sum(j.remote for j in jobs.values()) == 3


def test_lever_hybrid_is_not_remote() -> None:
    raw = load_json("lever_paytm.json")
    hybrid = {p["id"] for p in raw if p["workplaceType"] == "hybrid"}
    assert hybrid
    jobs = {j.ats_job_id: j for j in lever.normalize(raw)}
    assert not any(jobs[i].remote for i in hybrid)


def test_lever_dept_falls_back_to_team() -> None:
    [job] = lever.normalize([{"id": "u1", "text": "Backend Engineer", "categories": {"team": "Platform", "location": "Pune"},
                              "createdAt": 1790573982021, "hostedUrl": "https://jobs.lever.co/x/u1"}])
    assert job.dept == "Platform"


def test_lever_invalid_payload() -> None:
    with pytest.raises(FetchError):
        lever.normalize({"ok": False, "error": "Document not found"})


# --- Ashby -------------------------------------------------------------------------------------


@pytest.mark.parametrize("token,count", [("sarvam", 30), ("atlan", 7)])
def test_ashby_fixtures(token: str, count: int) -> None:
    jobs = ashby.normalize(load_json(f"ashby_{token}.json"))
    assert len(jobs) == count
    _check_common(jobs, "ashby")


def test_ashby_field_mapping() -> None:
    job = ashby.normalize(load_json("ashby_sarvam.json"))[0]
    assert job.doc_id == "ashby_c0406fe0-c8c0-44aa-aa3e-b879f2bf1049"
    assert job.title == "Engagement Manager, Chanakya"
    assert job.location == "Delhi"
    assert job.dept == "Business Development"
    assert job.remote is False
    assert job.url == "https://jobs.ashbyhq.com/sarvam/c0406fe0-c8c0-44aa-aa3e-b879f2bf1049"
    assert job.posted_at == datetime(2026, 4, 17, 11, 46, 39, 214000, tzinfo=timezone.utc)


def test_ashby_remote_flags() -> None:
    raw = load_json("ashby_atlan.json")
    jobs = {j.ats_job_id: j for j in ashby.normalize(raw)}
    for posting in raw["jobs"]:
        expected = posting["isRemote"] is True or posting["workplaceType"] == "Remote"
        assert jobs[posting["id"]].remote is expected
    # The fixture has a posting with isRemote = null / workplaceType = null: not remote.
    assert any(p["isRemote"] is None for p in raw["jobs"])


def test_ashby_skips_unlisted() -> None:
    payload = {"jobs": [
        {"id": "a", "title": "Designer", "isListed": False, "jobUrl": "https://jobs.ashbyhq.com/x/a"},
        {"id": "b", "title": "Designer", "isListed": True, "jobUrl": "https://jobs.ashbyhq.com/x/b",
         "publishedAt": "2026-11-01T00:00:00.000+00:00"},
    ]}
    assert [j.ats_job_id for j in ashby.normalize(payload)] == ["b"]


def test_ashby_invalid_payload() -> None:
    with pytest.raises(FetchError):
        ashby.normalize({"apiVersion": "1"})


def test_content_hash_changes_with_shown_fields() -> None:
    job = lever.normalize(load_json("lever_cred.json"))[0]
    same = Job(**{**job.__dict__})
    moved = Job(**{**job.__dict__, "location": "Bengaluru"})
    assert job.content_hash() == same.content_hash()
    assert job.content_hash() != moved.content_hash()
