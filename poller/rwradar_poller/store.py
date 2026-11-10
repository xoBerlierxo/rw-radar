"""Firestore access. This is the only module that imports firebase-admin, and only lazily, so
tests and ``--dry-run`` without credentials never need it.

Implementations of :class:`Store`:
- :class:`FirestoreStore`: the real thing, initialized from ``FIREBASE_SERVICE_ACCOUNT`` (the JSON
  contents). It also provides the FCM transport used by ``push.FcmPusher``.
- :class:`InMemoryStore`: the fake used by the tests (and by ``--dry-run`` without credentials).
- :class:`DryRunStore`: wraps another store; reads go through, writes are printed and dropped.

Write semantics (CLAUDE.md §4.4): ``companies/{id}`` is never fully overwritten. Every company write
is a ``set(..., merge=[top-level keys])``: the given top-level fields are replaced as a whole
(so ``jobIndex`` entries removed by the poller really disappear) and every other field is left
alone (the jobs and news workflows write different fields). The fake implements the same rule.
"""

from __future__ import annotations

import copy
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from . import config

log = logging.getLogger(__name__)

DirectoryMutator = Callable[[dict[str, Any] | None], dict[str, Any] | None]

COMPANIES = "companies"
JOBS = "jobs"
DIRECTORY_DOC = ("directory", "v1")
NEWS = "news"
NEWS_INDEX_DOC = ("meta", "newsIndex")
RUNS = "pollerRuns"


@dataclass(frozen=True)
class JobWrite:
    """A write to ``companies/{cid}/jobs/{job_id}``.

    ``merge=False`` writes the full doc (new jobs); ``merge=True`` replaces only the given fields
    (changed, closed or reopened jobs).
    """

    job_id: str
    data: dict[str, Any]
    merge: bool


class Store(ABC):
    # --- companies -------------------------------------------------------------------------
    @abstractmethod
    def get_company(self, company_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def commit_company(self, company_id: str, fields: dict[str, Any], job_writes: list[JobWrite]) -> None:
        """Write job docs and merge ``fields`` into ``companies/{id}`` (company doc last)."""

    @abstractmethod
    def merge_company_fields(self, company_id: str, fields: dict[str, Any]) -> None:
        """Merge-write top-level ``fields`` into ``companies/{id}`` (news workflow)."""

    # --- directory/v1 ----------------------------------------------------------------------
    @abstractmethod
    def get_directory(self) -> dict[str, Any] | None: ...

    @abstractmethod
    def update_directory(self, mutator: DirectoryMutator) -> bool:
        """Read-modify-write ``directory/v1`` atomically. ``mutator`` returns the new doc or
        ``None`` for "no change". Returns whether a write happened."""

    # --- news --------------------------------------------------------------------------------
    @abstractmethod
    def get_news_index(self) -> dict[str, Any] | None: ...

    @abstractmethod
    def set_news_index(self, doc: dict[str, Any]) -> None: ...

    @abstractmethod
    def write_news(self, docs: dict[str, dict[str, Any]]) -> None: ...

    # --- run log -----------------------------------------------------------------------------
    @abstractmethod
    def write_run(self, run_id: str, doc: dict[str, Any]) -> None: ...

    # --- FCM -------------------------------------------------------------------------------
    def push_transport(self) -> Callable[[Any], str] | None:
        """A callable that sends a ``push.PushMessage`` via FCM, or ``None`` if unavailable."""
        return None


def _merge_top_level(existing: dict[str, Any] | None, fields: dict[str, Any]) -> dict[str, Any]:
    doc = dict(existing or {})
    for key, value in fields.items():
        doc[key] = copy.deepcopy(value)
    return doc


class InMemoryStore(Store):
    """Dict-backed fake with Firestore's merge semantics (see module docstring)."""

    def __init__(self) -> None:
        self.companies: dict[str, dict[str, Any]] = {}
        self.jobs: dict[str, dict[str, dict[str, Any]]] = {}
        self.directory: dict[str, Any] | None = None
        self.news: dict[str, dict[str, Any]] = {}
        self.news_index: dict[str, Any] | None = None
        self.runs: dict[str, dict[str, Any]] = {}
        self.writes = 0  # document writes, for quota-style assertions
        self.commits: list[tuple[str, int]] = []  # (company id, job writes) per commit_company

    def get_company(self, company_id: str) -> dict[str, Any] | None:
        doc = self.companies.get(company_id)
        return copy.deepcopy(doc) if doc is not None else None

    def commit_company(self, company_id: str, fields: dict[str, Any], job_writes: list[JobWrite]) -> None:
        jobs = self.jobs.setdefault(company_id, {})
        for w in job_writes:
            jobs[w.job_id] = _merge_top_level(jobs.get(w.job_id) if w.merge else None, w.data)
        self.companies[company_id] = _merge_top_level(self.companies.get(company_id), fields)
        self.writes += len(job_writes) + 1
        self.commits.append((company_id, len(job_writes)))

    def merge_company_fields(self, company_id: str, fields: dict[str, Any]) -> None:
        self.companies[company_id] = _merge_top_level(self.companies.get(company_id), fields)
        self.writes += 1

    def get_directory(self) -> dict[str, Any] | None:
        return copy.deepcopy(self.directory)

    def update_directory(self, mutator: DirectoryMutator) -> bool:
        new = mutator(copy.deepcopy(self.directory))
        if new is None:
            return False
        self.directory = copy.deepcopy(new)
        self.writes += 1
        return True

    def get_news_index(self) -> dict[str, Any] | None:
        return copy.deepcopy(self.news_index)

    def set_news_index(self, doc: dict[str, Any]) -> None:
        self.news_index = copy.deepcopy(doc)
        self.writes += 1

    def write_news(self, docs: dict[str, dict[str, Any]]) -> None:
        for news_hash, doc in docs.items():
            self.news[news_hash] = copy.deepcopy(doc)
        self.writes += len(docs)

    def write_run(self, run_id: str, doc: dict[str, Any]) -> None:
        self.runs[run_id] = copy.deepcopy(doc)
        self.writes += 1


def _short(value: Any, limit: int = 160) -> str:
    text = json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "..."


class DryRunStore(Store):
    """Reads from ``base``; prints every write instead of performing it."""

    def __init__(self, base: Store, verbose_jobs: int = 3) -> None:
        self.base = base
        self.verbose_jobs = verbose_jobs
        self.planned_writes = 0

    def get_company(self, company_id: str) -> dict[str, Any] | None:
        return self.base.get_company(company_id)

    def commit_company(self, company_id: str, fields: dict[str, Any], job_writes: list[JobWrite]) -> None:
        self.planned_writes += len(job_writes) + 1
        summary = {k: (f"<{len(v)} entries>" if k == "jobIndex" else v) for k, v in fields.items()}
        print(f"[dry-run] MERGE companies/{company_id} {_short(summary, 400)}")
        if job_writes:
            new = sum(1 for w in job_writes if not w.merge)
            print(f"[dry-run]   {len(job_writes)} job doc writes ({new} new, {len(job_writes) - new} updates)")
            for w in job_writes[: self.verbose_jobs]:
                verb = "MERGE" if w.merge else "SET"
                print(f"[dry-run]   {verb} companies/{company_id}/jobs/{w.job_id} {_short(w.data)}")
            if len(job_writes) > self.verbose_jobs:
                print(f"[dry-run]   ... and {len(job_writes) - self.verbose_jobs} more")

    def merge_company_fields(self, company_id: str, fields: dict[str, Any]) -> None:
        self.planned_writes += 1
        print(f"[dry-run] MERGE companies/{company_id} {_short(fields)}")

    def get_directory(self) -> dict[str, Any] | None:
        return self.base.get_directory()

    def update_directory(self, mutator: DirectoryMutator) -> bool:
        new = mutator(self.base.get_directory())
        if new is None:
            print("[dry-run] directory/v1 unchanged")
            return False
        self.planned_writes += 1
        print(f"[dry-run] SET directory/v1 ({len(new.get('companies', []))} rows)")
        return True

    def get_news_index(self) -> dict[str, Any] | None:
        return self.base.get_news_index()

    def set_news_index(self, doc: dict[str, Any]) -> None:
        self.planned_writes += 1
        print(f"[dry-run] SET meta/newsIndex ({len(doc.get('hashes', {}))} hashes)")

    def write_news(self, docs: dict[str, dict[str, Any]]) -> None:
        self.planned_writes += len(docs)
        for news_hash, doc in docs.items():
            print(f"[dry-run] SET news/{news_hash[:12]}.. tag={doc['tag']} companies={doc['companyIds']} {doc['title'][:90]!r}")

    def write_run(self, run_id: str, doc: dict[str, Any]) -> None:
        print(f"[dry-run] SET pollerRuns/{run_id} counts={doc['counts']} errors={len(doc['errors'])}")


class FirestoreStore(Store):
    """firebase-admin backed store + FCM transport."""

    APP_NAME = "rwradar-poller"

    def __init__(self, service_account_json: str) -> None:
        import firebase_admin  # lazy: only real runs need it
        from firebase_admin import credentials, firestore

        try:
            info = json.loads(service_account_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT is not valid JSON") from exc
        try:
            self._app = firebase_admin.get_app(self.APP_NAME)
        except ValueError:
            self._app = firebase_admin.initialize_app(credentials.Certificate(info), name=self.APP_NAME)
        self._firestore = firestore
        self.db = firestore.client(app=self._app)

    def _company_ref(self, company_id: str) -> Any:
        return self.db.collection(COMPANIES).document(company_id)

    def get_company(self, company_id: str) -> dict[str, Any] | None:
        snap = self._company_ref(company_id).get()
        return snap.to_dict() if snap.exists else None

    def commit_company(self, company_id: str, fields: dict[str, Any], job_writes: list[JobWrite]) -> None:
        company_ref = self._company_ref(company_id)
        jobs_ref = company_ref.collection(JOBS)
        # Job docs first, the company doc (with jobIndex) in the last batch: if a batch fails, the
        # index is not advanced and the next run redoes the work.
        limit = config.FIRESTORE_BATCH_LIMIT
        chunks = [job_writes[i : i + limit] for i in range(0, len(job_writes), limit)] or [[]]
        for n, chunk in enumerate(chunks):
            batch = self.db.batch()
            for w in chunk:
                ref = jobs_ref.document(w.job_id)
                if w.merge:
                    batch.set(ref, w.data, merge=list(w.data))
                else:
                    batch.set(ref, w.data)
            if n == len(chunks) - 1:
                batch.set(company_ref, fields, merge=list(fields))
            batch.commit()

    def merge_company_fields(self, company_id: str, fields: dict[str, Any]) -> None:
        self._company_ref(company_id).set(fields, merge=list(fields))

    def get_directory(self) -> dict[str, Any] | None:
        snap = self.db.collection(DIRECTORY_DOC[0]).document(DIRECTORY_DOC[1]).get()
        return snap.to_dict() if snap.exists else None

    def update_directory(self, mutator: DirectoryMutator) -> bool:
        ref = self.db.collection(DIRECTORY_DOC[0]).document(DIRECTORY_DOC[1])

        @self._firestore.transactional
        def _txn(transaction: Any) -> bool:
            snap = ref.get(transaction=transaction)
            new = mutator(snap.to_dict() if snap.exists else None)
            if new is None:
                return False
            transaction.set(ref, new)
            return True

        return bool(_txn(self.db.transaction()))

    def get_news_index(self) -> dict[str, Any] | None:
        snap = self.db.collection(NEWS_INDEX_DOC[0]).document(NEWS_INDEX_DOC[1]).get()
        return snap.to_dict() if snap.exists else None

    def set_news_index(self, doc: dict[str, Any]) -> None:
        # meta/newsIndex is written only by the news workflow (one at a time), so a full set is safe.
        self.db.collection(NEWS_INDEX_DOC[0]).document(NEWS_INDEX_DOC[1]).set(doc)

    def write_news(self, docs: dict[str, dict[str, Any]]) -> None:
        items = list(docs.items())
        limit = config.FIRESTORE_BATCH_LIMIT
        for i in range(0, len(items), limit):
            batch = self.db.batch()
            for news_hash, doc in items[i : i + limit]:
                batch.set(self.db.collection(NEWS).document(news_hash), doc)
            batch.commit()

    def write_run(self, run_id: str, doc: dict[str, Any]) -> None:
        self.db.collection(RUNS).document(run_id).set(doc)

    def push_transport(self) -> Callable[[Any], str]:
        from firebase_admin import messaging

        app = self._app

        def send(msg: Any) -> str:
            message = messaging.Message(
                topic=msg.topic,
                notification=messaging.Notification(title=msg.title, body=msg.body),
                data=dict(msg.data),
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(channel_id=msg.channel_id),
                ),
                fcm_options=messaging.FCMOptions(analytics_label=msg.analytics_label),
            )
            return messaging.send(message, app=app)

        return send


def open_store(dry_run: bool) -> Store:
    """Real store from ``FIREBASE_SERVICE_ACCOUNT``; in dry-run, a read-only wrapper around it
    (or around an empty fake when there are no credentials)."""
    creds = config.service_account_json()
    if dry_run:
        if creds:
            log.info("dry-run: reading from Firestore (read-only), no writes")
            return DryRunStore(FirestoreStore(creds))
        log.info("dry-run: no FIREBASE_SERVICE_ACCOUNT, diffing against an empty store")
        return DryRunStore(InMemoryStore())
    if not creds:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT is not set (use --dry-run to run without Firestore)")
    return FirestoreStore(creds)
