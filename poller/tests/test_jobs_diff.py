"""Jobs sync diff logic (PLAN §4.4, §8; D1, D2, D6, D7, D10) against the in-memory store."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from rwradar_poller import config
from rwradar_poller.http import FetchError
from rwradar_poller.jobs_sync import diff_jobs, run_jobs
from rwradar_poller.models import Company, Job
from rwradar_poller.push import DisabledPusher, DryRunPusher, FcmPusher, PushMessage
from rwradar_poller.runlog import COUNT_KEYS, RunLog
from rwradar_poller.store import DryRunStore, InMemoryStore

from .conftest import FakeClock

GROWW = Company("groww", "Groww", ("Nextbillion Technology",), "Fintech", "https://groww.in", "greenhouse", "groww")
ZETA = Company("zeta", "Zeta", (), "Fintech", "https://zeta.tech", "lever", "zeta")
REGISTRY = [GROWW, ZETA]
T0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def job(n: int, title: str = "Backend Engineer", family: str = "eng", posted: datetime | None = None, **kw: Any) -> Job:
    base = dict(
        ats_type="greenhouse", ats_job_id=str(n), title=title, location="Bengaluru, India", dept="Engineering",
        remote=False, url=f"https://boards.greenhouse.io/groww/jobs/{n}", posted_at=posted or T0 - timedelta(days=30),
        family=family,
    )
    base.update(kw)
    return Job(**base)


class Board:
    """Fake ATS: returns whatever ``jobs[company_id]`` holds, or raises if it holds an exception."""

    def __init__(self) -> None:
        self.jobs: dict[str, Any] = {"groww": [], "zeta": []}
        self.calls = 0

    def __call__(self, client: Any, ats_type: str, token: str) -> list[Job]:
        self.calls += 1
        value = self.jobs[token]
        if isinstance(value, Exception):
            raise value
        return list(value)


class Harness:
    def __init__(self) -> None:
        self.store = InMemoryStore()
        self.board = Board()
        self.clock = FakeClock(T0)
        self.sent: list[PushMessage] = []
        self.pusher = FcmPusher(transport=self._transport)

    def _transport(self, msg: PushMessage) -> str:
        self.sent.append(msg)
        return "projects/x/messages/1"

    def run(self, companies: list[Company] | None = None, pusher: Any = None, store: Any = None) -> RunLog:
        return run_jobs(
            REGISTRY, companies or [GROWW], store=store or self.store, client=None,  # type: ignore[arg-type]
            pusher=pusher or self.pusher, clock=self.clock, fetch=self.board,
        )

    def company(self, cid: str = "groww") -> dict[str, Any]:
        return self.store.companies[cid]

    def job_doc(self, job_id: str, cid: str = "groww") -> dict[str, Any]:
        return self.store.jobs[cid][job_id]


@pytest.fixture
def h() -> Harness:
    return Harness()


def seed(h: Harness, jobs: list[Job]) -> RunLog:
    h.board.jobs["groww"] = jobs
    run = h.run()
    h.clock.advance(hours=1)
    return run


# --- seeding (D6) ------------------------------------------------------------------------------


def test_seeding_run_records_jobs_without_push(h: Harness) -> None:
    run = seed(h, [job(1), job(2, "Product Designer", "design")])
    assert h.sent == []
    assert run.counts["new"] == 2 and run.counts["pushed"] == 0
    doc = h.company()
    assert doc["seededAt"] == T0
    assert "lastJobPushAt" not in doc
    assert doc["openCount"] == 2
    j = h.job_doc("greenhouse_1")
    assert j["status"] == "open"
    assert set(j) == {"title", "family", "location", "remote", "dept", "url", "postedAt", "firstSeenAt", "status"}
    # Seeded jobs take firstSeenAt from postedAt, so they are not all "new this week".
    assert j["firstSeenAt"] == T0 - timedelta(days=30)
    assert doc["newThisWeek"] == 0


def test_seeding_job_without_posted_date_uses_now(h: Harness) -> None:
    seed(h, [job(1, posted_at=None)])  # type: ignore[arg-type]
    assert h.job_doc("greenhouse_1")["firstSeenAt"] == T0


def test_seeding_job_posted_in_future_is_capped_at_now(h: Harness) -> None:
    seed(h, [job(1, posted=T0 + timedelta(hours=2))])
    assert h.job_doc("greenhouse_1")["firstSeenAt"] == T0


# --- new / changed / unchanged -----------------------------------------------------------------


def test_new_job_after_seeding_is_pushed(h: Harness) -> None:
    seed(h, [job(1)])
    posted = h.clock.now - timedelta(minutes=50)
    h.board.jobs["groww"] = [job(1), job(2, posted=posted)]
    run = h.run()
    assert run.counts["new"] == 1 and run.counts["pushed"] == 1
    [msg] = h.sent
    assert msg.topic == "c_groww_eng"
    assert msg.title == "Groww"
    assert msg.body == "1 new Engineering role at Groww"
    assert msg.data == {"type": "jobs", "companyId": "groww", "family": "eng",
                        "since": str(int(run.started_at.timestamp() * 1000))}
    assert msg.channel_id == "new_openings" and msg.analytics_label == "jobs_eng"
    assert h.job_doc("greenhouse_2")["firstSeenAt"] == h.clock.now
    assert h.job_doc("greenhouse_2")["firstSeenAt"].timestamp() * 1000 >= int(msg.data["since"])
    assert h.company()["lastJobPushAt"] == {"eng": h.clock.now}
    assert run.delays == [50.0]
    assert h.company()["newThisWeek"] == 1


def test_one_grouped_push_per_family(h: Harness) -> None:
    seed(h, [job(1)])
    h.board.jobs["groww"] = [job(1), job(2), job(3), job(4), job(5, "UX Designer", "design")]
    run = h.run()
    assert run.counts["pushed"] == 2
    bodies = {m.topic: m.body for m in h.sent}
    assert bodies == {"c_groww_eng": "3 new Engineering roles at Groww", "c_groww_design": "1 new Design role at Groww"}
    assert len(run.delays) == 4


def test_changed_job_is_rewritten_without_push(h: Harness) -> None:
    seed(h, [job(1)])
    h.board.jobs["groww"] = [job(1, title="Senior Backend Engineer")]
    run = h.run()
    assert run.counts["changed"] == 1 and run.counts["new"] == 0 and h.sent == []
    doc = h.job_doc("greenhouse_1")
    assert doc["title"] == "Senior Backend Engineer"
    assert doc["firstSeenAt"] == T0 - timedelta(days=30)  # kept from the first write


def test_unchanged_jobs_write_only_the_company_doc(h: Harness) -> None:
    seed(h, [job(1), job(2)])
    before = h.store.writes
    run = h.run()
    assert h.store.commits[-1] == ("groww", 0)  # D2: no job doc writes
    assert run.counts["new"] == run.counts["changed"] == run.counts["closed"] == 0
    assert h.company()["jobIndex"]["greenhouse_1"]["seen"] == h.clock.now
    # company doc + run log; directory unchanged -> not rewritten
    assert h.store.writes - before == 2


# --- missing / closed / reopened (spec M3) ----------------------------------------------------


def test_missing_once_then_twice_closes(h: Harness) -> None:
    seed(h, [job(1), job(2)])
    h.board.jobs["groww"] = [job(1)]
    run = h.run()
    assert run.counts["closed"] == 0
    assert h.company()["jobIndex"]["greenhouse_2"]["miss"] == 1
    assert h.job_doc("greenhouse_2")["status"] == "open"
    assert h.company()["openCount"] == 2  # still open after one miss
    assert h.store.commits[-1] == ("groww", 0)

    h.clock.advance(hours=1)
    run = h.run()
    assert run.counts["closed"] == 1
    assert h.company()["jobIndex"]["greenhouse_2"]["miss"] == 2
    assert h.job_doc("greenhouse_2")["status"] == "closed"
    assert h.company()["openCount"] == 1

    h.clock.advance(hours=1)
    run = h.run()  # stays closed, no further writes
    assert run.counts["closed"] == 0 and h.store.commits[-1] == ("groww", 0)


def test_missing_once_then_back_resets_miss(h: Harness) -> None:
    seed(h, [job(1)])
    h.board.jobs["groww"] = []
    h.run()
    h.clock.advance(hours=1)
    h.board.jobs["groww"] = [job(1)]
    run = h.run()
    assert h.company()["jobIndex"]["greenhouse_1"]["miss"] == 0
    assert run.counts["reopened"] == 0 and run.counts["new"] == 0


def test_closed_job_reappears_is_reopened_without_push(h: Harness) -> None:
    seed(h, [job(1), job(2)])
    h.board.jobs["groww"] = [job(1)]
    h.run()
    h.clock.advance(hours=1)
    h.run()
    assert h.job_doc("greenhouse_2")["status"] == "closed"
    h.clock.advance(hours=1)
    h.board.jobs["groww"] = [job(1), job(2)]
    run = h.run()
    assert run.counts["reopened"] == 1 and run.counts["new"] == 0 and run.counts["pushed"] == 0
    assert h.sent == []
    assert h.job_doc("greenhouse_2")["status"] == "open"
    assert h.job_doc("greenhouse_2")["firstSeenAt"] == T0 - timedelta(days=30)
    assert h.company()["openCount"] == 2


def test_long_closed_entries_are_pruned_from_the_index(h: Harness) -> None:
    seed(h, [job(1), job(2)])
    h.board.jobs["groww"] = [job(1)]
    h.run()
    h.clock.advance(hours=1)
    h.run()
    assert "greenhouse_2" in h.company()["jobIndex"]
    h.clock.advance(days=31)
    h.run()
    assert "greenhouse_2" not in h.company()["jobIndex"]  # removed: the merge replaces the whole map


# --- fetch failures (D7) -----------------------------------------------------------------------


def test_fetch_failure_leaves_miss_count_alone(h: Harness) -> None:
    seed(h, [job(1), job(2)])
    h.board.jobs["groww"] = [job(1)]
    h.run()
    index_before = h.company()["jobIndex"]
    for _ in range(3):
        h.clock.advance(hours=1)
        h.board.jobs["groww"] = FetchError("server error", status=503)
        run = h.run()
        assert run.counts["failedFetches"] == 1 and run.counts["fetched"] == 0
        assert run.errors[0]["companyId"] == "groww" and run.errors[0]["status"] == 503
    assert h.company()["jobIndex"] == index_before
    assert h.job_doc("greenhouse_2")["status"] == "open"
    assert h.company()["lastPolledAt"] == T0 + timedelta(hours=1)


def test_fetch_failure_before_first_success_creates_registry_doc_only(h: Harness) -> None:
    h.board.jobs["groww"] = FetchError("HTTP error", status=404)
    run = h.run()
    assert run.counts["failedFetches"] == 1
    doc = h.company()
    assert doc["name"] == "Groww" and doc["ats"] == {"type": "greenhouse", "token": "groww"}
    assert "seededAt" not in doc and "jobIndex" not in doc
    # The next successful poll is still the seeding poll: no push.
    h.board.jobs["groww"] = [job(1)]
    h.clock.advance(hours=1)
    h.run()
    assert h.sent == [] and h.company()["seededAt"] == h.clock.now


def test_one_company_failing_does_not_stop_others(h: Harness) -> None:
    h.board.jobs["groww"] = RuntimeError("boom")  # unexpected error, not a FetchError
    h.board.jobs["zeta"] = [job(9, ats_type="lever")]
    run = h.run([GROWW, ZETA])
    assert run.counts["companies"] == 2 and run.counts["fetched"] == 1
    assert "zeta" in h.store.companies
    assert any("sync failed" in e["message"] for e in run.errors)


# --- throttles (D10) ---------------------------------------------------------------------------


def test_six_hour_throttle_per_family(h: Harness) -> None:
    seed(h, [job(1)])
    h.board.jobs["groww"] = [job(1), job(2)]
    h.run()
    assert len(h.sent) == 1
    first_push = h.clock.now

    h.clock.advance(hours=3)
    h.board.jobs["groww"] = [job(1), job(2), job(3), job(4, "Data Analyst", "data")]
    run = h.run()
    assert run.counts["throttled"] == 1  # eng held back
    assert run.counts["pushed"] == 1  # data is a different family
    assert [m.topic for m in h.sent] == ["c_groww_eng", "c_groww_data"]
    assert h.company()["lastJobPushAt"]["eng"] == first_push

    h.clock.advance(hours=3, minutes=1)  # 6 h 1 min after the first eng push
    h.board.jobs["groww"] = [job(1), job(2), job(3), job(4, "Data Analyst", "data"), job(5)]
    run = h.run()
    assert run.counts["pushed"] == 1 and h.sent[-1].body == "1 new Engineering role at Groww"
    assert h.company()["lastJobPushAt"]["eng"] == h.clock.now


def test_throttle_edge_exactly_six_hours_pushes(h: Harness) -> None:
    seed(h, [job(1)])
    h.board.jobs["groww"] = [job(1), job(2)]
    h.run()
    h.clock.advance(hours=6)
    h.board.jobs["groww"] = [job(1), job(2), job(3)]
    assert h.run().counts["pushed"] == 1


# --- flags ---------------------------------------------------------------------------------------


def test_no_push_flag_does_not_stamp_throttle(h: Harness) -> None:
    seed(h, [job(1)])
    h.board.jobs["groww"] = [job(1), job(2)]
    run = h.run(pusher=DisabledPusher())
    assert run.counts["pushed"] == 0 and run.counts["new"] == 1
    assert "lastJobPushAt" not in h.company()
    assert h.sent == []


def test_dry_run_writes_nothing(h: Harness, capsys: pytest.CaptureFixture[str]) -> None:
    seed(h, [job(1)])
    snapshot = (dict(h.store.companies), h.store.writes)
    h.board.jobs["groww"] = [job(1), job(2)]
    pusher = DryRunPusher()
    run = h.run(pusher=pusher, store=DryRunStore(h.store))
    assert (dict(h.store.companies), h.store.writes) == snapshot
    assert run.counts["pushed"] == 1 and h.sent == [] and len(pusher.sent) == 1
    out = capsys.readouterr().out
    assert "[dry-run] PUSH topic=c_groww_eng" in out and "[dry-run] MERGE companies/groww" in out


def test_debug_all_copy(h: Harness) -> None:
    seed(h, [job(1)])
    h.pusher.debug_all = True
    h.board.jobs["groww"] = [job(1), job(2)]
    run = h.run()
    assert [m.topic for m in h.sent] == ["c_groww_eng", "debug_all"]
    assert h.sent[0].body == h.sent[1].body
    assert run.counts["pushed"] == 1


def test_push_failure_is_logged_not_fatal(h: Harness) -> None:
    seed(h, [job(1)])

    def broken(msg: PushMessage) -> str:
        raise RuntimeError("FCM unavailable")

    h.board.jobs["groww"] = [job(1), job(2)]
    run = h.run(pusher=FcmPusher(transport=broken))
    assert run.counts["pushed"] == 0
    assert any("push failed" in e["message"] for e in run.errors)
    assert "greenhouse_2" in h.company()["jobIndex"]


# --- company doc merge, directory, run log -----------------------------------------------------


def test_company_doc_merge_keeps_news_fields(h: Harness) -> None:
    funded = T0 - timedelta(days=2)
    h.store.merge_company_fields("groww", {"lastFundingAt": funded, "lastSignalPushAt": funded})
    seed(h, [job(1)])
    doc = h.company()
    assert doc["lastFundingAt"] == funded and doc["lastSignalPushAt"] == funded
    assert doc["id"] == "groww" and doc["aliases"] == ["Nextbillion Technology"] and doc["logoUrl"] == ""


def test_directory_rows_and_rebuild_only_on_change(h: Harness) -> None:
    funded = T0 - timedelta(days=2)
    h.store.merge_company_fields("groww", {"lastFundingAt": funded})
    seed(h, [job(1), job(2)])
    d = h.store.directory
    assert d is not None and d["updatedAt"] == T0
    rows = {r["id"]: r for r in d["companies"]}
    assert set(rows) == {"groww", "zeta"}  # every registry company has a row
    assert rows["groww"] == {"id": "groww", "name": "Groww", "aliases": ["Nextbillion Technology"], "sector": "Fintech",
                             "openCount": 2, "newThisWeek": 0, "lastFundingAt": funded, "logoUrl": ""}
    assert rows["zeta"]["openCount"] == 0

    h.run()  # nothing changed
    assert h.store.directory["updatedAt"] == T0

    h.clock.advance(hours=1)
    h.board.jobs["groww"] = [job(1), job(2), job(3)]
    h.run()
    assert h.store.directory["updatedAt"] == h.clock.now
    assert {r["id"]: r for r in h.store.directory["companies"]}["groww"]["openCount"] == 3


def test_directory_keeps_lastfundingat_written_by_news(h: Harness) -> None:
    seed(h, [job(1)])
    funded = T0 + timedelta(minutes=20)
    h.store.directory["companies"][0]["lastFundingAt"] = funded  # news run patched the row
    h.board.jobs["groww"] = [job(1), job(2)]
    h.run()
    row = next(r for r in h.store.directory["companies"] if r["id"] == "groww")
    assert row["lastFundingAt"] == funded and row["openCount"] == 2


def test_new_this_week_window(h: Harness) -> None:
    seed(h, [job(1, posted=T0 - timedelta(days=8)), job(2, posted=T0 - timedelta(days=2))])
    assert h.company()["newThisWeek"] == 1


def test_run_log_written(h: Harness) -> None:
    run = seed(h, [job(1)])
    doc = h.store.runs[run.run_id]
    assert doc["kind"] == "jobs"
    assert set(doc["counts"]) == set(COUNT_KEYS)
    assert doc["counts"]["companies"] == 1 and doc["counts"]["fetched"] == 1
    assert doc["startedAt"] == T0 and doc["finishedAt"] >= doc["startedAt"]
    assert isinstance(doc["durationMs"], int) and doc["errors"] == [] and doc["delays"] == []
    assert run.run_id.startswith("jobs-20261110T120000Z-")


def test_all_timestamps_are_utc_aware(h: Harness) -> None:
    seed(h, [job(1)])
    h.board.jobs["groww"] = [job(1), job(2)]
    h.run()

    def walk(value: Any) -> None:
        if isinstance(value, datetime):
            assert value.tzinfo is not None and value.utcoffset() == timedelta(0)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(h.store.companies)
    walk(h.store.jobs)
    walk(h.store.directory)


# --- pure diff ------------------------------------------------------------------------------------


def test_diff_dedupes_repeated_postings() -> None:
    result = diff_jobs([job(1), job(1)], {}, T0, seeding=False)
    assert result.new == 1 and len(result.job_writes) == 1


def test_diff_family_change_rewrites_doc() -> None:
    first = diff_jobs([job(1, family="other")], {}, T0, seeding=True)
    again = diff_jobs([job(1, family="eng")], first.index, T0 + timedelta(hours=1), seeding=False)
    assert again.changed == 1 and again.job_writes[0].data["family"] == "eng"


def test_constants_match_contract() -> None:
    assert config.MISSES_TO_CLOSE == 2
    assert config.JOB_PUSH_THROTTLE == timedelta(hours=6)
