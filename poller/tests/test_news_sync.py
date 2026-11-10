"""News sync (PLAN §4.5): newsIndex, matched-only writes, lastFundingAt, signal push with the
48 h freshness rule and the 7-day throttle, Google News every 2nd run."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from rwradar_poller import config
from rwradar_poller.http import FetchError
from rwradar_poller.models import Company, NewsItem
from rwradar_poller.news import feeds
from rwradar_poller.news.matcher import Blocklist, Matcher
from rwradar_poller.news.news_sync import prune_index, run_news, should_run_google
from rwradar_poller.push import DisabledPusher, FcmPusher, PushMessage
from rwradar_poller.runlog import RunLog
from rwradar_poller.store import InMemoryStore

from .conftest import FakeClock, load_bytes

T0 = datetime(2026, 11, 10, 12, 13, tzinfo=timezone.utc)
GROWW = Company("groww", "Groww", (), "Fintech", "https://groww.in", "greenhouse", "groww")
SARVAM = Company("sarvam", "Sarvam AI", ("Sarvam",), "AI", "https://sarvam.ai", "ashby", "sarvam")
MEESHO = Company("meesho", "Meesho", (), "E-commerce", "https://meesho.com", "lever", "meesho")
ZETA = Company("zeta", "Zeta", (), "Fintech", "https://zeta.tech", "lever", "zeta")
REGISTRY = [GROWW, SARVAM, MEESHO, ZETA]


def item(title: str, url: str, published: datetime | None, source: str = "Entrackr") -> NewsItem:
    norm = feeds.normalize_url(url)
    return NewsItem(title=title, source=source, url=norm, published_at=published, hash=feeds.news_hash(norm))


class Feeds:
    """Fake feed fetcher keyed by source key; Google sources share the key prefix 'googlenews'."""

    def __init__(self) -> None:
        self.items: dict[str, Any] = {"inc42": [], "entrackr": [], "yourstory": [], "googlenews": []}
        self.calls: list[str] = []

    def __call__(self, client: Any, source: feeds.FeedSource) -> list[NewsItem]:
        self.calls.append(source.key)
        key = "googlenews" if source.google else source.key
        value = self.items[key]
        if isinstance(value, Exception):
            raise value
        return list(value)


class Harness:
    def __init__(self, blocklist: Blocklist | None = None) -> None:
        self.store = InMemoryStore()
        self.feeds = Feeds()
        self.clock = FakeClock(T0)
        self.sent: list[PushMessage] = []
        self.pusher = FcmPusher(transport=lambda m: self.sent.append(m) or "id")
        self.matcher = Matcher(REGISTRY, blocklist)

    def run(self, selected: list[Company] | None = None, pusher: Any = None, google: str = "auto") -> RunLog:
        return run_news(
            REGISTRY, selected or REGISTRY, store=self.store, client=None,  # type: ignore[arg-type]
            pusher=pusher or self.pusher, matcher=self.matcher, clock=self.clock, google_mode=google,
            fetch=self.feeds,
        )


@pytest.fixture
def h() -> Harness:
    return Harness()


FUNDING_URL = "https://entrackr.com/news/sarvam-raises-250-mn?utm_source=rss#top"


def test_matched_items_written_unmatched_only_indexed(h: Harness) -> None:
    h.feeds.items["entrackr"] = [
        item("Sarvam raises $250 Mn led by Nvidia", FUNDING_URL, T0 - timedelta(hours=2)),
        item("Blue Tokai crosses Rs 500 Cr revenue in FY26; losses up 54%", "https://entrackr.com/x", T0 - timedelta(hours=1)),
    ]
    run = h.run(google="never")
    assert run.counts["newsItems"] == 2 and run.counts["newsMatched"] == 1
    assert len(h.store.news) == 1
    [(news_hash, doc)] = h.store.news.items()
    assert news_hash == feeds.news_hash("https://entrackr.com/news/sarvam-raises-250-mn")
    assert doc == {
        "title": "Sarvam raises $250 Mn led by Nvidia",
        "source": "Entrackr",
        "url": "https://entrackr.com/news/sarvam-raises-250-mn",
        "publishedAt": T0 - timedelta(hours=2),
        "tag": "funding",
        "companyIds": ["sarvam"],
    }
    assert set(h.store.news_index["hashes"]) == {i.hash for i in h.feeds.items["entrackr"]}


def test_seen_hash_is_skipped_on_next_run(h: Harness) -> None:
    h.feeds.items["inc42"] = [item("Meesho acquires majority stake in Kirana Club", "https://inc42.com/m/", T0)]
    h.run(google="never")
    writes = h.store.writes
    h.clock.advance(minutes=30)
    # The same article again, with tracking params: same normalized URL, same hash.
    h.feeds.items["inc42"] = [item("Meesho acquires majority stake in Kirana Club", "https://inc42.com/m/?utm_medium=x", T0)]
    run = h.run(google="never")
    assert run.counts["newsMatched"] == 0
    assert h.store.writes - writes == 1  # only the run log; index unchanged -> not rewritten


def test_items_older_than_30_days_are_ignored(h: Harness) -> None:
    h.feeds.items["inc42"] = [item("Meesho acquires X", "https://inc42.com/old", T0 - timedelta(days=31))]
    run = h.run(google="never")
    assert run.counts["newsMatched"] == 0 and h.store.news == {}
    assert (h.store.news_index or {}).get("hashes", {}) == {}


def test_missing_published_date_falls_back_to_now(h: Harness) -> None:
    h.feeds.items["inc42"] = [item("Meesho launches new app", "https://inc42.com/m2", None)]
    h.run(google="never")
    [doc] = h.store.news.values()
    assert doc["publishedAt"] == T0 and doc["tag"] == "other"


# --- funding signal ----------------------------------------------------------------------------


def test_fresh_funding_sets_last_funding_and_pushes(h: Harness) -> None:
    h.store.merge_company_fields("sarvam", {"openCount": 30})
    published = T0 - timedelta(hours=5)
    h.feeds.items["entrackr"] = [item("Sarvam raises $250 Mn led by Nvidia", FUNDING_URL, published)]
    run = h.run(google="never")
    [msg] = h.sent
    news_hash = feeds.news_hash(feeds.normalize_url(FUNDING_URL))
    assert msg.topic == "c_sarvam_signal"
    assert msg.title == "Sarvam AI"
    assert msg.body == "Sarvam AI raised funding. 30 open roles right now."
    assert msg.data == {"type": "signal", "companyId": "sarvam", "newsHash": news_hash}
    assert msg.channel_id == "hiring_signals" and msg.analytics_label == "signal"
    doc = h.store.companies["sarvam"]
    assert doc["lastFundingAt"] == published and doc["lastSignalPushAt"] == T0
    assert run.counts["pushed"] == 1
    row = next(r for r in h.store.directory["companies"] if r["id"] == "sarvam")
    assert row["lastFundingAt"] == published


def test_stale_funding_sets_last_funding_but_no_push(h: Harness) -> None:
    published = T0 - timedelta(hours=49)
    h.feeds.items["entrackr"] = [item("Sarvam raises $250 Mn led by Nvidia", FUNDING_URL, published)]
    run = h.run(google="never")
    assert h.sent == [] and run.counts["pushed"] == 0 and run.counts["throttled"] == 0
    assert h.store.companies["sarvam"]["lastFundingAt"] == published
    assert "lastSignalPushAt" not in h.store.companies["sarvam"]


def test_freshness_boundary_48h(h: Harness) -> None:
    h.feeds.items["entrackr"] = [item("Sarvam raises $250 Mn", FUNDING_URL, T0 - timedelta(hours=48))]
    h.run(google="never")
    assert len(h.sent) == 1


@pytest.mark.parametrize("days_since_last,pushed", [(2, False), (6.9, False), (7, True), (10, True)])
def test_seven_day_signal_throttle(h: Harness, days_since_last: float, pushed: bool) -> None:
    h.store.merge_company_fields("sarvam", {"lastSignalPushAt": T0 - timedelta(days=days_since_last), "openCount": 1})
    h.feeds.items["entrackr"] = [item("Sarvam raises $250 Mn", FUNDING_URL, T0 - timedelta(hours=1))]
    run = h.run(google="never")
    assert (len(h.sent) == 1) is pushed
    assert run.counts["throttled"] == (0 if pushed else 1)
    if pushed:
        assert h.sent[0].body == "Sarvam AI raised funding. 1 open role right now."


def test_last_funding_only_moves_forward(h: Harness) -> None:
    newer = T0 - timedelta(days=1)
    h.store.merge_company_fields("sarvam", {"lastFundingAt": newer})
    h.feeds.items["entrackr"] = [item("Sarvam raises $250 Mn", FUNDING_URL, T0 - timedelta(days=3))]
    h.run(google="never")
    assert h.store.companies["sarvam"]["lastFundingAt"] == newer


def test_investor_does_not_get_the_signal(h: Harness) -> None:
    h.feeds.items["entrackr"] = [item("Groww invests $10 Mn in Meesho", "https://entrackr.com/g", T0)]
    h.run(google="never")
    assert [m.topic for m in h.sent] == ["c_meesho_signal"]
    [doc] = h.store.news.values()
    assert doc["companyIds"] == ["meesho"]


def test_no_push_flag_does_not_stamp_signal_throttle(h: Harness) -> None:
    h.feeds.items["entrackr"] = [item("Sarvam raises $250 Mn", FUNDING_URL, T0)]
    run = h.run(pusher=DisabledPusher(), google="never")
    assert run.counts["pushed"] == 0
    assert "lastSignalPushAt" not in h.store.companies["sarvam"]
    assert h.store.companies["sarvam"]["lastFundingAt"] == T0


def test_signal_push_does_not_need_seeding(h: Harness) -> None:
    # A funded company the jobs workflow never polled: openCount unknown -> 0.
    h.feeds.items["entrackr"] = [item("Zeta raises $30 Mn in Series D", "https://entrackr.com/z", T0)]
    h.run(google="never")
    assert h.sent[0].body == "Zeta raised funding. 0 open roles right now."


def test_blocklisted_match_is_dropped() -> None:
    h = Harness(Blocklist.from_data({"rules": [{"companyId": "zeta", "phrase": "Zeta Global"}]}))
    h.feeds.items["googlenews"] = [
        item("Truist raises Zeta Global stock price target on strong growth", "https://news.google.com/rss/articles/a?oc=5", T0, "Investing.com"),
    ]
    run = h.run(google="always")
    assert run.counts["newsMatched"] == 0 and h.store.news == {}


# --- Google News cadence (every 2nd run) -------------------------------------------------------


def test_google_news_every_second_run(h: Harness) -> None:
    ran = []
    for _ in range(6):  # runs at :13 and :43 for 3 hours
        h.feeds.calls.clear()
        h.run()
        ran.append(any(k.startswith("googlenews") for k in h.feeds.calls))
        h.clock.advance(minutes=30)
    assert ran == [True, False, False, False, True, False]  # 105-min minimum gap: first, then 2 h later


def test_google_news_survives_late_cron(h: Harness) -> None:
    h.run()
    h.clock.advance(minutes=30)
    assert not should_run_google(h.store.news_index, h.clock.now)
    h.clock.advance(minutes=75)  # 105 min after the last pass (a late :13 run)
    assert should_run_google(h.store.news_index, h.clock.now)


def test_google_news_failure_does_not_advance_its_clock(h: Harness) -> None:
    h.feeds.items["googlenews"] = FetchError("HTTP error", status=429)
    run = h.run()
    assert run.counts["failedFetches"] == 1
    assert run.errors[0]["source"] == "googlenews-1" and run.errors[0]["status"] == 429
    assert (h.store.news_index or {}).get("lastGoogleNewsAt") is None
    h.clock.advance(minutes=30)
    assert should_run_google(h.store.news_index, h.clock.now)


def test_google_news_batches_ten_companies() -> None:
    companies = [Company(f"c{i}", f"Co {i}", (), "x", "https://x", "lever", f"c{i}") for i in range(25)]
    h = Harness()
    run_news(companies, companies, store=h.store, client=None, pusher=h.pusher,  # type: ignore[arg-type]
             matcher=Matcher(companies), clock=h.clock, google_mode="always", fetch=h.feeds)
    assert [k for k in h.feeds.calls if k.startswith("googlenews")] == ["googlenews-1", "googlenews-2", "googlenews-3"]


def test_google_mode_flags() -> None:
    assert should_run_google({"lastGoogleNewsAt": T0}, T0, "always")
    assert not should_run_google(None, T0, "never")
    assert should_run_google(None, T0, "auto")


# --- index pruning, partial runs, failures, run log -------------------------------------------


def test_prune_index() -> None:
    hashes = {"old": T0 - timedelta(days=31), "new": T0 - timedelta(days=1), "bad": "x"}
    assert prune_index(hashes, T0) == {"new": T0 - timedelta(days=1)}


def test_prune_index_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "NEWS_INDEX_MAX_ENTRIES", 2)
    hashes = {str(i): T0 - timedelta(minutes=i) for i in range(5)}
    assert set(prune_index(hashes, T0)) == {"0", "1"}


def test_company_flag_does_not_write_news_index(h: Harness) -> None:
    h.feeds.items["inc42"] = [
        item("Meesho acquires X", "https://inc42.com/a", T0),
        item("Groww files for IPO", "https://inc42.com/b", T0),
    ]
    run = h.run(selected=[GROWW])
    assert run.counts["newsMatched"] == 1
    assert [d["companyIds"] for d in h.store.news.values()] == [["groww"]]
    assert h.store.news_index is None
    assert [k for k in h.feeds.calls if k.startswith("googlenews")] == ["googlenews-1"]


def test_feed_failure_logged_others_continue(h: Harness) -> None:
    h.feeds.items["yourstory"] = FetchError("HTTP error", status=403)
    h.feeds.items["inc42"] = [item("Meesho acquires X", "https://inc42.com/a", T0)]
    run = h.run(google="never")
    assert run.counts["failedFetches"] == 1 and run.counts["fetched"] == 2
    assert run.errors == [{"message": "feed fetch failed: HTTP error (HTTP 403)", "source": "yourstory", "status": 403}]
    assert len(h.store.news) == 1


def test_run_log_written(h: Harness) -> None:
    run = h.run(google="never")
    doc = h.store.runs[run.run_id]
    assert doc["kind"] == "news" and doc["counts"]["companies"] == len(REGISTRY)
    assert doc["delays"] == []


def test_end_to_end_with_real_fixtures(h: Harness) -> None:
    """Parse the saved feeds and run them through tagging + matching."""
    sources = {s.key: s for s in feeds.DIRECT_FEEDS}
    h.feeds.items["inc42"] = feeds.parse_feed(load_bytes("rss_inc42.xml"), sources["inc42"])
    h.feeds.items["entrackr"] = feeds.parse_feed(load_bytes("rss_entrackr.xml"), sources["entrackr"])
    h.feeds.items["yourstory"] = feeds.parse_feed(load_bytes("rss_yourstory.xml"), sources["yourstory"])
    google = feeds.FeedSource("googlenews-1", "Google News", "https://x", google=True)
    h.feeds.items["googlenews"] = feeds.parse_feed(load_bytes("rss_googlenews.xml"), google)
    h.clock.now = datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc)
    h.matcher = Matcher(REGISTRY, Blocklist.load(config.BLOCKLIST_PATH))
    run = h.run(google="always")
    assert run.counts["fetched"] == 4 and run.counts["newsItems"] == 12 + 16 + 12 + 21
    by_company: dict[str, list[str]] = {}
    for doc in h.store.news.values():
        assert set(doc) == {"title", "source", "url", "publishedAt", "tag", "companyIds"}
        for cid in doc["companyIds"]:
            by_company.setdefault(cid, []).append(doc["title"])
    assert any("Sreedharan" in t for t in by_company["sarvam"])
    assert any("Kirana Club" in t for t in by_company["meesho"])
    # The seed blocklist keeps Zeta Global / Zeta-Jones stories away from Zeta.
    assert not any("Zeta Global" in t or "Zeta-Jones" in t for t in by_company.get("zeta", []))
