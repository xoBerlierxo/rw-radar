"""Jobs sync: one run over the registry (PLAN §4.4; D1, D2, D6, D7, D10).

Per company:
1. Fetch the ATS. On failure: log it, skip the company, leave ``missCount`` alone (D7).
2. Read ``companies/{id}`` (1 read). Its ``jobIndex`` replaces reading every job doc (D1).
3. Diff fetched jobs against ``jobIndex``:
   - new (not in the index): write the full job doc, ``status: open``, ``firstSeenAt = now``.
   - in the index, hash changed: rewrite the content fields.
   - in the index, same hash: only the index entry changes (``seen``, ``miss = 0``) (D2).
   - in the index, not fetched: ``miss += 1``; at 2 -> ``status: closed`` (spec M3).
   - closed (``miss >= 2``) and fetched again: reopen it, no push.
4. Merge into ``companies/{id}``: registry fields, ``jobIndex``, ``openCount``, ``newThisWeek``,
   ``lastPolledAt`` (+ ``seededAt``, ``lastJobPushAt``). Job docs + company doc in one batch.
5. Push: on the seeding run (``seededAt`` unset) nothing is pushed (D6). Otherwise one push per
   family with new jobs, unless ``lastJobPushAt[family]`` is < 6 h old (then ``throttled``) (D10).
6. Record each pushed job's ``postedAt -> push`` delay in minutes (90-minute metric).

After all companies: patch ``directory/v1`` if a summary field changed (D3), write ``pollerRuns``.

``jobIndex`` entry (CLAUDE.md §4.2): ``{h: content hash, miss: int, seen: Timestamp}`` plus
``f: Timestamp`` (the job's firstSeenAt), which lets ``newThisWeek`` be computed without reading
job docs. Closed entries stay in the index (so a reappearing job is reopened, not re-pushed) until
unseen for 30 days, then they are pruned.

Seeding detail: on the seeding run, ``firstSeenAt`` is the job's ``postedAt`` (capped at now) when
known, so the Openings order and ``newThisWeek`` reflect real posting dates instead of making every
existing job "new this week".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from . import ats, config, directory, location_filter
from .http import FetchError, HttpClient
from .models import Company, Job, utcnow
from .push import PushMessage, Pusher, job_push
from .runlog import RunLog
from .store import JobWrite, Store

log = logging.getLogger(__name__)

Fetcher = Callable[[HttpClient, str, str], list[Job]]
Clock = Callable[[], datetime]


@dataclass
class DiffResult:
    job_writes: list[JobWrite] = field(default_factory=list)
    index: dict[str, dict[str, Any]] = field(default_factory=dict)
    new_jobs: dict[str, list[Job]] = field(default_factory=dict)  # family -> new jobs
    new: int = 0
    changed: int = 0
    closed: int = 0
    reopened: int = 0
    open_count: int = 0
    new_this_week: int = 0


def _is_closed(entry: dict[str, Any]) -> bool:
    return int(entry.get("miss", 0)) >= config.MISSES_TO_CLOSE


def diff_jobs(fetched: list[Job], index: dict[str, dict[str, Any]], now: datetime, seeding: bool) -> DiffResult:
    """Pure diff of a successful fetch against the company's ``jobIndex``."""
    result = DiffResult()
    by_id: dict[str, Job] = {}
    for job in fetched:
        by_id.setdefault(job.doc_id, job)  # ATS payloads occasionally repeat a posting

    for job_id, job in by_id.items():
        h = job.content_hash()
        entry = index.get(job_id)
        if entry is None:
            first_seen = now
            if seeding and job.posted_at is not None:
                first_seen = min(job.posted_at, now)
            result.job_writes.append(
                JobWrite(job_id, {**job.content_fields(), "firstSeenAt": first_seen, "status": "open"}, merge=False)
            )
            result.index[job_id] = {"h": h, "miss": 0, "seen": now, "f": first_seen}
            result.new_jobs.setdefault(job.family, []).append(job)
            result.new += 1
            continue
        new_entry = {**entry, "h": h, "miss": 0, "seen": now}
        if _is_closed(entry):
            result.job_writes.append(JobWrite(job_id, {**job.content_fields(), "status": "open"}, merge=True))
            result.reopened += 1
        elif entry.get("h") != h:
            result.job_writes.append(JobWrite(job_id, {**job.content_fields(), "status": "open"}, merge=True))
            result.changed += 1
        result.index[job_id] = new_entry

    for job_id, entry in index.items():
        if job_id in by_id:
            continue
        if _is_closed(entry):
            seen = entry.get("seen")
            if isinstance(seen, datetime) and now - seen > config.CLOSED_INDEX_RETENTION:
                continue  # prune long-closed entries
            result.index[job_id] = dict(entry)
            continue
        miss = int(entry.get("miss", 0)) + 1
        result.index[job_id] = {**entry, "miss": miss}
        if miss >= config.MISSES_TO_CLOSE:
            result.job_writes.append(JobWrite(job_id, {"status": "closed"}, merge=True))
            result.closed += 1

    week_ago = now - config.NEW_THIS_WEEK_WINDOW
    for entry in result.index.values():
        if _is_closed(entry):
            continue
        result.open_count += 1
        first = entry.get("f")
        if isinstance(first, datetime) and first >= week_ago:
            result.new_this_week += 1
    return result


@dataclass
class PlannedPush:
    message: PushMessage
    jobs: list[Job]


def plan_job_pushes(
    company: Company,
    new_jobs: dict[str, list[Job]],
    last_push: dict[str, datetime],
    now: datetime,
    since: datetime,
    seeding: bool,
) -> tuple[list[PlannedPush], list[str]]:
    """Returns (pushes to send, families throttled). Seeding sends nothing (D6)."""
    if seeding:
        return [], []
    pushes: list[PlannedPush] = []
    throttled: list[str] = []
    since_ms = int(since.timestamp() * 1000)
    for family in config.FAMILY_KEYS:
        jobs = new_jobs.get(family)
        if not jobs:
            continue
        last = last_push.get(family)
        if isinstance(last, datetime) and now - last < config.JOB_PUSH_THROTTLE:
            throttled.append(family)
            continue
        pushes.append(PlannedPush(job_push(company.id, company.name, family, len(jobs), since_ms), jobs))
    return pushes, throttled


@dataclass
class CompanySummary:
    open_count: int
    new_this_week: int
    last_funding_at: Any


def sync_company(
    company: Company,
    *,
    store: Store,
    client: HttpClient,
    pusher: Pusher,
    run: RunLog,
    clock: Clock,
    fetch: Fetcher = ats.fetch_jobs,
) -> CompanySummary | None:
    """Sync one company. Returns its directory summary, or ``None`` if the fetch failed."""
    try:
        jobs = fetch(client, company.ats_type, company.ats_token)
    except FetchError as exc:
        run.inc("failedFetches")
        run.error(f"{company.ats_type} fetch failed: {exc}", company_id=company.id, status=exc.status)
        log.warning("%s: fetch failed: %s", company.id, exc)
        # D7: no jobIndex/missCount change. Only make sure the company doc exists for the app.
        if store.get_company(company.id) is None:
            store.merge_company_fields(company.id, company.registry_fields())
        return None
    run.inc("fetched")
    if config.india_only():
        jobs = location_filter.filter_jobs(jobs)

    doc = store.get_company(company.id) or {}
    now = clock()
    seeding = doc.get("seededAt") is None
    diff = diff_jobs(jobs, dict(doc.get("jobIndex") or {}), now, seeding)

    last_push: dict[str, datetime] = dict(doc.get("lastJobPushAt") or {})
    pushes, throttled = plan_job_pushes(company, diff.new_jobs, last_push, now, run.started_at, seeding)
    if pusher.active:
        for p in pushes:
            last_push[p.message.data["family"]] = now

    fields: dict[str, Any] = {
        **company.registry_fields(),
        "openCount": diff.open_count,
        "newThisWeek": diff.new_this_week,
        "lastPolledAt": now,
        "jobIndex": diff.index,
    }
    if seeding:
        fields["seededAt"] = now
    if pusher.active and pushes:
        fields["lastJobPushAt"] = last_push

    store.commit_company(company.id, fields, diff.job_writes)
    run.inc("new", diff.new)
    run.inc("changed", diff.changed)
    run.inc("closed", diff.closed)
    run.inc("reopened", diff.reopened)
    run.inc("throttled", len(throttled))
    log.info(
        "%s: %d fetched, %d new, %d changed, %d closed, %d reopened%s",
        company.id, len(jobs), diff.new, diff.changed, diff.closed, diff.reopened, " (seeding)" if seeding else "",
    )

    # Push after the commit, so the job docs exist when the notification is tapped.
    for p in pushes:
        try:
            pusher.send(p.message)
        except Exception as exc:  # noqa: BLE001 - a failed push must not stop the run
            run.error(f"push failed for {p.message.topic}: {exc}", company_id=company.id)
            continue
        if not pusher.active:
            continue
        run.inc("pushed")
        sent_at = clock()
        for job in p.jobs:
            if job.posted_at is not None:
                run.add_delay(max(0.0, (sent_at - job.posted_at).total_seconds() / 60.0))

    return CompanySummary(diff.open_count, diff.new_this_week, doc.get("lastFundingAt"))


def run_jobs(
    registry_all: list[Company],
    selected: list[Company],
    *,
    store: Store,
    client: HttpClient,
    pusher: Pusher,
    clock: Clock = utcnow,
    fetch: Fetcher = ats.fetch_jobs,
    run: RunLog | None = None,
) -> RunLog:
    """Run the jobs sync for ``selected`` companies; writes ``directory/v1`` and the run log."""
    run = run or RunLog("jobs", clock())
    patches: dict[str, dict[str, Any]] = {}
    defaults: dict[str, dict[str, Any]] = {}
    try:
        for company in selected:
            run.inc("companies")
            try:
                summary = sync_company(
                    company, store=store, client=client, pusher=pusher, run=run, clock=clock, fetch=fetch
                )
            except Exception as exc:  # noqa: BLE001 - one bad company must not stop the run
                log.exception("%s: sync failed", company.id)
                run.error(f"sync failed: {type(exc).__name__}: {exc}", company_id=company.id)
                continue
            if summary is not None:
                patches[company.id] = {"openCount": summary.open_count, "newThisWeek": summary.new_this_week}
                defaults[company.id] = {"lastFundingAt": summary.last_funding_at}
        try:
            store.update_directory(directory.make_mutator(registry_all, patches, clock(), defaults))
        except Exception as exc:  # noqa: BLE001
            log.exception("directory update failed")
            run.error(f"directory update failed: {type(exc).__name__}: {exc}")
    except BaseException as exc:
        run.error(f"run aborted: {type(exc).__name__}: {exc}")
        raise
    finally:
        try:
            store.write_run(run.run_id, run.to_doc(clock()))
        except Exception:  # noqa: BLE001
            log.exception("could not write run log")
    return run
