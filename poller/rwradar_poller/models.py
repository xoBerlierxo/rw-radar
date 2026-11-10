"""Plain data types shared by the adapters, the sync logic and the store."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: datetime | None) -> datetime | None:
    """Normalize to a timezone-aware UTC datetime (naive values are assumed to be UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_iso(value: Any) -> datetime | None:
    """Parse an ISO-8601 string such as ``2026-09-14T03:49:28-04:00`` to UTC; ``None`` if unusable."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return to_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def from_epoch_ms(value: Any) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def sha1_hex(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Company:
    """One registry entry (``registry/companies.json``)."""

    id: str
    name: str
    aliases: tuple[str, ...]
    sector: str
    website: str
    ats_type: str
    ats_token: str
    logo_url: str = ""

    def registry_fields(self) -> dict[str, Any]:
        """The registry fields copied onto ``companies/{id}`` (CLAUDE.md §4.2)."""
        return {
            "id": self.id,
            "name": self.name,
            "aliases": list(self.aliases),
            "sector": self.sector,
            "website": self.website,
            "ats": {"type": self.ats_type, "token": self.ats_token},
            "logoUrl": self.logo_url,
        }


@dataclass(frozen=True)
class Job:
    """A normalized job posting. ``family`` is filled in by the adapter via ``classify``."""

    ats_type: str
    ats_job_id: str
    title: str
    location: str
    dept: str
    remote: bool
    url: str
    posted_at: datetime | None
    family: str

    @property
    def doc_id(self) -> str:
        """``{atsType}_{atsJobId}``, stable across polls (CLAUDE.md §4.1)."""
        return f"{self.ats_type}_{self.ats_job_id}"

    def content_hash(self) -> str:
        """sha1 of the fields shown in the app. A change rewrites the job doc (PLAN §4.2).

        ``family`` is included too, so a classifier rule change re-files existing jobs.
        """
        parts = [self.title, self.location, self.dept, "1" if self.remote else "0", self.url, self.family]
        return sha1_hex("|".join(parts))

    def content_fields(self) -> dict[str, Any]:
        """Job doc fields that come from the ATS (everything except firstSeenAt/status)."""
        return {
            "title": self.title,
            "family": self.family,
            "location": self.location,
            "remote": self.remote,
            "dept": self.dept,
            "url": self.url,
            "postedAt": self.posted_at,
        }


@dataclass(frozen=True)
class NewsItem:
    """A normalized feed item. No article body is kept, ever (spec §11)."""

    title: str
    source: str
    url: str  # normalized URL (also what we store)
    published_at: datetime | None
    hash: str = field(default="")
    feed: str = ""  # which feed produced it (run-log/debug only)
