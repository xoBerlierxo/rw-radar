"""Feed parsing and URL normalization against the saved RSS fixtures (Day-1 spike)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from rwradar_poller.http import FetchError
from rwradar_poller.models import Company
from rwradar_poller.news import feeds

from .conftest import load_bytes

DIRECT = {s.key: s for s in feeds.DIRECT_FEEDS}
GOOGLE = feeds.FeedSource("googlenews-1", "Google News", "https://news.google.com/rss/search?q=x", google=True)


@pytest.mark.parametrize(
    "fixture,key,count,source",
    [
        ("rss_inc42.xml", "inc42", 12, "Inc42"),
        ("rss_entrackr.xml", "entrackr", 16, "Entrackr"),
        ("rss_yourstory.xml", "yourstory", 12, "YourStory"),
    ],
)
def test_direct_feeds(fixture: str, key: str, count: int, source: str) -> None:
    items = feeds.parse_feed(load_bytes(fixture), DIRECT[key])
    assert len(items) == count
    for item in items:
        assert item.title and item.title == item.title.strip()
        assert item.source == source
        assert item.url.startswith("https://")
        assert item.hash == hashlib.sha1(item.url.encode()).hexdigest()
        assert item.published_at is not None and item.published_at.tzinfo is not None


def test_entrackr_dates_are_converted_to_utc() -> None:
    items = feeds.parse_feed(load_bytes("rss_entrackr.xml"), DIRECT["entrackr"])
    sarvam = next(i for i in items if i.title.startswith("Sarvam appoints"))
    # pubDate "Tue, 10 Nov 2026 14:44:01 +0530"
    assert sarvam.published_at == datetime(2026, 11, 10, 9, 14, 1, tzinfo=timezone.utc)


def test_google_news_titles_and_publishers() -> None:
    items = feeds.parse_feed(load_bytes("rss_googlenews.xml"), GOOGLE)
    assert len(items) == 21
    first = items[0]
    assert first.title == "Sashikumar Sreedharan joins Sarvam as President and Chief Business Officer"
    assert first.source == "Sarvam AI"  # from <source>, the " - Sarvam AI" suffix is stripped
    for item in items:
        assert not item.title.endswith(f" - {item.source}")
        assert "oc=" not in item.url  # Google's tracking param dropped
        assert item.url.startswith("https://news.google.com/rss/articles/")


def test_feeds_never_keep_bodies() -> None:
    items = feeds.parse_feed(load_bytes("rss_inc42.xml"), DIRECT["inc42"])
    assert set(items[0].__dict__) == {"title", "source", "url", "published_at", "hash", "feed"}


def test_html_error_page_is_fetch_error() -> None:
    with pytest.raises(FetchError):
        feeds.parse_feed(b"<!doctype html><html><head><title>404</title></head><body>Not found</body></html>", DIRECT["entrackr"])


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://inc42.com/buzz/x/?utm_source=rss&utm_medium=feed#comments", "https://inc42.com/buzz/x/"),
        ("HTTPS://YourStory.com/2026/11/x?utm_campaign=a&b=2&a=1", "https://yourstory.com/2026/11/x?a=1&b=2"),
        ("https://news.google.com/rss/articles/CBMi?oc=5", "https://news.google.com/rss/articles/CBMi"),
        ("https://entrackr.com/news/x?fbclid=abc&id=7", "https://entrackr.com/news/x?id=7"),
        ("  https://example.com  ", "https://example.com/"),
    ],
)
def test_normalize_url(raw: str, expected: str) -> None:
    assert feeds.normalize_url(raw) == expected


def test_same_article_with_different_tracking_has_same_hash() -> None:
    a = feeds.news_hash(feeds.normalize_url("https://inc42.com/buzz/x/?utm_source=twitter"))
    b = feeds.news_hash(feeds.normalize_url("https://inc42.com/buzz/x/#respond"))
    assert a == b and len(a) == 40


def test_google_sources_batch_10_companies() -> None:
    companies = [Company(f"c{i}", f"Company {i}", (), "x", "https://x", "lever", f"c{i}") for i in range(23)]
    sources = feeds.google_sources(companies)
    assert [len(s.company_ids) for s in sources] == [10, 10, 3]
    assert all(s.google for s in sources)
    assert "%22Company%200%22%20OR%20%22Company%201%22" in sources[0].url
    assert "when%3A7d" in sources[0].url
    assert sources[0].url.endswith("&hl=en-IN&gl=IN&ceid=IN:en")
