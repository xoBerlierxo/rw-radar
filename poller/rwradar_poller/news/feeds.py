"""News sources (PLAN §4.5), confirmed in the Day-1 spike (docs/spike-notes.md):

| Source      | URL                                   | Cadence            |
| ----------- | ------------------------------------- | ------------------ |
| Inc42       | https://inc42.com/feed/               | every run (30 min) |
| Entrackr    | https://entrackr.com/rss              | every run          |
| YourStory   | https://yourstory.com/feed            | every run          |
| Google News | news.google.com/rss/search?q=...      | every 2nd run      |

(``entrackr.com/feed`` from the plan is a 404; the site advertises ``/rss``.)

Google News: about 10 companies per query (``("A" OR "B" ...) when:7d``) so a pass is ~10
requests, not 100. Its item titles end with `` - <Publisher>``; that suffix is stripped and the
publisher (from ``<source>``) becomes the item's ``source``. Item links are Google redirect URLs;
they open the article in a browser and are stable, so they are stored as-is.

Only headline, source, link and date are kept. Never the description or article body.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import calendar
import feedparser

from .. import config
from ..http import FetchError, HttpClient
from ..models import Company, NewsItem, sha1_hex

GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"
GOOGLE_NEWS_PARAMS = "hl=en-IN&gl=IN&ceid=IN:en"
GOOGLE_NEWS_WINDOW = "when:7d"

_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid"}


@dataclass(frozen=True)
class FeedSource:
    key: str  # short id for logs/errors
    name: str  # shown in the app as the news source (Google items use their publisher instead)
    url: str
    google: bool = False
    company_ids: tuple[str, ...] = ()  # Google batches: the companies in the query


DIRECT_FEEDS: tuple[FeedSource, ...] = (
    FeedSource("inc42", "Inc42", "https://inc42.com/feed/"),
    FeedSource("entrackr", "Entrackr", "https://entrackr.com/rss"),
    FeedSource("yourstory", "YourStory", "https://yourstory.com/feed"),
)


def normalize_url(url: str) -> str:
    """Lowercase scheme/host, drop the fragment and tracking params (``utm_*``, fbclid, ...,
    and Google News' ``oc``), keep the rest of the query in a stable order."""
    parts = urlsplit((url or "").strip())
    scheme = (parts.scheme or "https").lower()
    host = parts.netloc.lower()
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_")
        and k.lower() not in _TRACKING_PARAMS
        and not (host == "news.google.com" and k == "oc")
    ]
    query.sort()
    return urlunsplit((scheme, host, parts.path or "/", urlencode(query), ""))


def news_hash(normalized_url: str) -> str:
    return sha1_hex(normalized_url)


def google_news_url(names: Iterable[str]) -> str:
    terms = " OR ".join(f'"{n}"' for n in names)
    query = f"({terms}) {GOOGLE_NEWS_WINDOW}"
    return f"{GOOGLE_NEWS_BASE}?q={quote(query)}&{GOOGLE_NEWS_PARAMS}"


def google_sources(companies: Iterable[Company], batch: int = config.GOOGLE_NEWS_BATCH) -> list[FeedSource]:
    companies = list(companies)
    out: list[FeedSource] = []
    for i in range(0, len(companies), batch):
        chunk = companies[i : i + batch]
        out.append(
            FeedSource(
                key=f"googlenews-{i // batch + 1}",
                name="Google News",
                url=google_news_url(c.name for c in chunk),
                google=True,
                company_ids=tuple(c.id for c in chunk),
            )
        )
    return out


def _published(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
    except (OverflowError, ValueError, TypeError):
        return None


def parse_feed(content: bytes, source: FeedSource) -> list[NewsItem]:
    """Parse RSS/Atom bytes into items; raises FetchError if it is not a usable feed."""
    parsed = feedparser.parse(content)
    if not parsed.entries and (parsed.bozo or not parsed.get("feed")):
        raise FetchError(f"{source.key}: not a usable RSS feed", url=source.url)
    items: list[NewsItem] = []
    for entry in parsed.entries:
        title = " ".join((entry.get("title") or "").split())
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        name = source.name
        if source.google:
            publisher = ((entry.get("source") or {}).get("title") or "").strip()
            if publisher:
                name = publisher
                suffix = f" - {publisher}"
                if title.endswith(suffix):
                    title = title[: -len(suffix)].rstrip()
        url = normalize_url(link)
        items.append(
            NewsItem(
                title=title,
                source=name,
                url=url,
                published_at=_published(entry),
                hash=news_hash(url),
                feed=source.key,
            )
        )
    return items


def fetch(client: HttpClient, source: FeedSource) -> list[NewsItem]:
    return parse_feed(client.get_bytes(source.url), source)
