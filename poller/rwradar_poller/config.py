"""Paths, constants, env vars and CLI flags for the poller.

Paths are resolved from this file's location (never the CWD), so the poller behaves the same
whether it is run from ``poller/`` (as the workflows do) or from anywhere else.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

# poller/rwradar_poller/config.py -> parents[0]=rwradar_poller, [1]=poller, [2]=repo root
PACKAGE_DIR = Path(__file__).resolve().parent
POLLER_DIR = PACKAGE_DIR.parent
REPO_ROOT = POLLER_DIR.parent
REGISTRY_PATH = REPO_ROOT / "registry" / "companies.json"
BLOCKLIST_PATH = REPO_ROOT / "registry" / "news_blocklist.json"

# HTTP (CLAUDE.md §4.4)
USER_AGENT_BASE = "RWRadarPoller/0.1"
HTTP_TIMEOUT_S = 15.0
HTTP_RETRIES = 2
HTTP_MIN_INTERVAL_PER_HOST_S = 1.0

# Jobs sync (PLAN §4.4, CLAUDE.md §4.4)
MISSES_TO_CLOSE = 2
JOB_PUSH_THROTTLE = timedelta(hours=6)
NEW_THIS_WEEK_WINDOW = timedelta(days=7)
# Closed jobs stay in jobIndex (so a reappearing job is reopened without a push) until they have
# not been seen for this long; then the entry is pruned to keep the company doc small.
CLOSED_INDEX_RETENTION = timedelta(days=30)
# Firestore allows 500 writes per batch; keep headroom.
FIRESTORE_BATCH_LIMIT = 450

# News sync (PLAN §4.5)
SIGNAL_PUSH_THROTTLE = timedelta(days=7)
SIGNAL_FRESHNESS = timedelta(hours=48)
NEWS_INDEX_TTL = timedelta(days=30)
NEWS_INDEX_MAX_ENTRIES = 12_000  # keeps meta/newsIndex well under Firestore's 1 MiB doc limit
NEWS_MAX_AGE = timedelta(days=30)  # older feed items are ignored entirely (never indexed)
# Google News runs on every 2nd news run (~2 h). Decided by the time stored in
# meta/newsIndex.lastGoogleNewsAt: run when at least this much time has passed since the last
# Google pass. 105 min (not 120) so that a 30-minute cron that fires a few minutes early still
# lands on every 2nd run, and a late cron cannot skip a pass.
GOOGLE_NEWS_MIN_INTERVAL = timedelta(minutes=105)
GOOGLE_NEWS_BATCH = 10

# Push (CLAUDE.md §4.3)
FAMILY_LABELS: dict[str, str] = {
    "design": "Design",
    "data": "Data",
    "product": "Product",
    "gtm": "Marketing/Sales",
    "eng": "Engineering",
    "other": "Other",
}
FAMILY_KEYS: tuple[str, ...] = tuple(FAMILY_LABELS)
NEWS_TAGS: tuple[str, ...] = ("funding", "layoffs", "acquisition", "financials", "other")
DEBUG_ALL_TOPIC = "debug_all"
CHANNEL_JOBS = "new_openings"
CHANNEL_SIGNALS = "hiring_signals"


def repo_url() -> str:
    return os.environ.get("RWRADAR_REPO_URL", "").strip()


def user_agent() -> str:
    """``RWRadarPoller/0.1 (+<repo url>)``, or just ``RWRadarPoller/0.1`` when the env var is unset."""
    url = repo_url()
    return f"{USER_AGENT_BASE} (+{url})" if url else USER_AGENT_BASE


def service_account_json() -> str | None:
    value = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    return value or None


def debug_all_enabled() -> bool:
    return os.environ.get("RWRADAR_DEBUG_ALL_TOPIC", "").strip() == "1"


@dataclass(frozen=True)
class RunOptions:
    """Flags shared by the ``jobs`` and ``news`` commands."""

    dry_run: bool = False
    no_push: bool = False
    company: str | None = None
    debug_all: bool = False
    google_news: str = "auto"  # news only: auto | always | never


def india_only() -> bool:
    """Keep only India / India-open remote jobs (location_filter.py). Default on; set RWRADAR_INDIA_ONLY=0 to disable."""
    return os.environ.get("RWRADAR_INDIA_ONLY", "1").strip() != "0"
