"""News sync: one run (PLAN §4.5; D6, D10).

Per feed item:
1. Normalize the URL (drop ``utm_*``/tracking params and the fragment); ``hash = sha1(url)``.
2. Skip it if the hash is in ``meta/newsIndex`` (1 read per run) or older than 30 days.
3. Tag it (``tagger``), then match companies (``matcher``, with the blocklist).
4. Write ``news/{hash}`` only if it matched at least one company. Every new hash is indexed.
5. Funding items: set ``companies/{id}.lastFundingAt`` (only ever moves forward). If the item was
   published in the last 48 h (D6) and ``lastSignalPushAt`` is >= 7 days old (D10), send the
   signal push (M7), else count it as ``throttled``.

Then ``meta/newsIndex`` is pruned to 30 days and written back, ``directory/v1`` gets the new
``lastFundingAt`` values, and the run log is written.

Google News runs on every 2nd run (~2 h). The decision uses ``meta/newsIndex.lastGoogleNewsAt``,
a poller-only field next to ``hashes``: Google runs when that time is unset or at least 105 min ago.
That holds up when GitHub cron fires late or skips a slot, unlike parity of the UTC hour. It costs no
extra reads because the doc is read anyway. ``--google-news always|never`` overrides it.

``--company X`` (debugging) only keeps matches for X and does *not* write ``meta/newsIndex``, so
items that belong to other companies are not marked as seen.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from .. import config, directory
from ..http import FetchError, HttpClient
from ..models import Company, NewsItem, utcnow
from ..push import PushMessage, Pusher, signal_push
from ..runlog import RunLog
from ..store import Store
from . import feeds
from .matcher import Matcher
from .tagger import tag

log = logging.getLogger(__name__)

FeedFetcher = Callable[[HttpClient, feeds.FeedSource], list[NewsItem]]
Clock = Callable[[], datetime]


def should_run_google(index_doc: dict[str, Any] | None, now: datetime, mode: str = "auto") -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    last = (index_doc or {}).get("lastGoogleNewsAt")
    return not isinstance(last, datetime) or now - last >= config.GOOGLE_NEWS_MIN_INTERVAL


def prune_index(hashes: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Drop hashes older than the TTL, then keep at most NEWS_INDEX_MAX_ENTRIES newest."""
    cutoff = now - config.NEWS_INDEX_TTL
    kept = {h: ts for h, ts in hashes.items() if isinstance(ts, datetime) and ts >= cutoff}
    if len(kept) > config.NEWS_INDEX_MAX_ENTRIES:
        newest = sorted(kept.items(), key=lambda kv: kv[1], reverse=True)[: config.NEWS_INDEX_MAX_ENTRIES]
        kept = dict(newest)
    return kept


def plan_signal_push(
    company: Company,
    company_doc: dict[str, Any],
    funding_items: list[NewsItem],
    now: datetime,
) -> tuple[PushMessage | None, bool]:
    """Returns (push to send or None, throttled?). Applies the 48 h and 7-day rules."""
    fresh = [
        item
        for item in funding_items
        if item.published_at is not None and now - item.published_at <= config.SIGNAL_FRESHNESS
    ]
    if not fresh:
        return None, False
    last = company_doc.get("lastSignalPushAt")
    if isinstance(last, datetime) and now - last < config.SIGNAL_PUSH_THROTTLE:
        return None, True
    newest = max(fresh, key=lambda i: i.published_at)  # type: ignore[arg-type,return-value]
    open_count = int(company_doc.get("openCount") or 0)
    return signal_push(company.id, company.name, open_count, newest.hash), False


def run_news(
    registry_all: list[Company],
    selected: list[Company],
    *,
    store: Store,
    client: HttpClient,
    pusher: Pusher,
    matcher: Matcher,
    clock: Clock = utcnow,
    google_mode: str = "auto",
    fetch: FeedFetcher = feeds.fetch,
    run: RunLog | None = None,
) -> RunLog:
    run = run or RunLog("news", clock())
    by_id = {c.id: c for c in registry_all}
    selected_ids = {c.id for c in selected}
    partial = len(selected) != len(registry_all)
    try:
        run.inc("companies", len(selected))
        now = clock()
        index_doc = store.get_news_index() or {}
        hashes: dict[str, Any] = dict(index_doc.get("hashes") or {})
        original_hashes = dict(hashes)
        google = should_run_google(index_doc, now, google_mode)
        sources = list(feeds.DIRECT_FEEDS) + (feeds.google_sources(selected) if google else [])
        log.info("news: %d sources (google news: %s)", len(sources), "yes" if google else "no")

        new_docs: dict[str, dict[str, Any]] = {}
        funding: dict[str, list[NewsItem]] = {}
        google_ok = False
        for source in sources:
            try:
                items = fetch(client, source)
            except FetchError as exc:
                run.inc("failedFetches")
                run.error(f"feed fetch failed: {exc}", source=source.key, status=exc.status)
                log.warning("%s: %s", source.key, exc)
                continue
            run.inc("fetched")
            google_ok = google_ok or source.google
            for item in items:
                run.inc("newsItems")
                if item.published_at is not None and now - item.published_at > config.NEWS_MAX_AGE:
                    continue
                if item.hash in hashes:
                    continue
                hashes[item.hash] = now
                item_tag = tag(item.title)
                ids = [cid for cid in matcher.match(item.title, item_tag, item.hash) if cid in selected_ids]
                if not ids:
                    continue
                run.inc("newsMatched")
                new_docs[item.hash] = {
                    "title": item.title,
                    "source": item.source,
                    "url": item.url,
                    "publishedAt": item.published_at or now,
                    "tag": item_tag,
                    "companyIds": ids,
                }
                if item_tag == "funding":
                    for cid in ids:
                        funding.setdefault(cid, []).append(item)

        if new_docs:
            store.write_news(new_docs)

        # Funding: lastFundingAt + signal pushes.
        directory_patches: dict[str, dict[str, Any]] = {}
        planned: list[tuple[str, PushMessage]] = []
        for cid, items in funding.items():
            company = by_id[cid]
            doc = store.get_company(cid) or {}
            fields: dict[str, Any] = {}
            latest = max(item.published_at or now for item in items)
            current = doc.get("lastFundingAt")
            if not isinstance(current, datetime) or latest > current:
                fields["lastFundingAt"] = latest
                directory_patches[cid] = {"lastFundingAt": latest}
            msg, throttled = plan_signal_push(company, doc, items, now)
            if throttled:
                run.inc("throttled")
            if msg is not None:
                planned.append((cid, msg))
                if pusher.active:
                    fields["lastSignalPushAt"] = now
            if fields:
                store.merge_company_fields(cid, fields)

        for cid, msg in planned:
            try:
                pusher.send(msg)
            except Exception as exc:  # noqa: BLE001
                run.error(f"push failed for {msg.topic}: {exc}", company_id=cid)
                continue
            if pusher.active:
                run.inc("pushed")

        if partial:
            log.info("news: --company run, meta/newsIndex not written")
        else:
            new_index: dict[str, Any] = {"hashes": prune_index(hashes, now)}
            last_google = index_doc.get("lastGoogleNewsAt")
            new_index["lastGoogleNewsAt"] = now if google_ok else last_google
            if new_index["hashes"] != original_hashes or new_index["lastGoogleNewsAt"] != last_google:
                store.set_news_index(new_index)

        if directory_patches:
            store.update_directory(directory.make_mutator(registry_all, directory_patches, clock()))
    except BaseException as exc:
        run.error(f"run aborted: {type(exc).__name__}: {exc}")
        raise
    finally:
        try:
            store.write_run(run.run_id, run.to_doc(clock()))
        except Exception:  # noqa: BLE001
            log.exception("could not write run log")
    return run
