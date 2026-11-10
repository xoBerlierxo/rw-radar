"""FCM topic pushes (CLAUDE.md §4.3, PLAN §4.6).

All pushes are notification + data messages with Android priority ``high``, a ``channel_id`` and
``fcm_options.analytics_label`` (D8). This module builds the messages and decides *how* they are
delivered; the actual FCM call lives in ``store.py`` (the only module that imports firebase-admin).

Pushers:
- :class:`FcmPusher`: real sends through a transport callable from the store.
- :class:`DryRunPusher` (``--dry-run``): prints and records; counts as sent so throttle decisions
  and counts match a real run.
- :class:`DisabledPusher` (``--no-push``): logs and records; counts as *not* sent, so throttle
  timestamps are not stamped.

When ``RWRADAR_DEBUG_ALL_TOPIC=1``, each push is also sent to the ``debug_all`` topic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Callable

from . import config

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PushMessage:
    topic: str
    title: str
    body: str
    data: dict[str, str]
    channel_id: str
    analytics_label: str


def job_topic(company_id: str, family: str) -> str:
    return f"c_{company_id}_{family}"


def signal_topic(company_id: str) -> str:
    return f"c_{company_id}_signal"


def job_push(company_id: str, company_name: str, family: str, count: int, since_ms: int) -> PushMessage:
    """``3 new Engineering roles at {Company}`` / ``1 new Engineering role at {Company}``."""
    label = config.FAMILY_LABELS[family]
    noun = "role" if count == 1 else "roles"
    return PushMessage(
        topic=job_topic(company_id, family),
        title=company_name,
        body=f"{count} new {label} {noun} at {company_name}",
        data={"type": "jobs", "companyId": company_id, "family": family, "since": str(int(since_ms))},
        channel_id=config.CHANNEL_JOBS,
        analytics_label=f"jobs_{family}",
    )


def signal_push(company_id: str, company_name: str, open_count: int, news_hash: str) -> PushMessage:
    """``{Company} raised funding. {N} open roles right now.`` (singular for N == 1)."""
    noun = "role" if open_count == 1 else "roles"
    return PushMessage(
        topic=signal_topic(company_id),
        title=company_name,
        body=f"{company_name} raised funding. {open_count} open {noun} right now.",
        data={"type": "signal", "companyId": company_id, "newsHash": news_hash},
        channel_id=config.CHANNEL_SIGNALS,
        analytics_label="signal",
    )


@dataclass
class Pusher:
    """Base pusher. ``active`` says whether a send counts as delivered (and stamps throttles)."""

    debug_all: bool = False
    sent: list[PushMessage] = field(default_factory=list)
    active: bool = True

    def send(self, msg: PushMessage) -> None:
        """Send ``msg`` (and its ``debug_all`` copy if enabled). Raises on delivery failure."""
        self._deliver(msg)
        self.sent.append(msg)
        if self.debug_all:
            copy = replace(msg, topic=config.DEBUG_ALL_TOPIC)
            try:
                self._deliver(copy)
            except Exception as exc:  # the debug copy must never fail the real push
                log.warning("debug_all copy failed: %s", exc)

    def _deliver(self, msg: PushMessage) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


@dataclass
class FcmPusher(Pusher):
    transport: Callable[[PushMessage], str] | None = None

    def _deliver(self, msg: PushMessage) -> None:
        assert self.transport is not None
        message_id = self.transport(msg)
        log.info("pushed %s -> %s (%s)", msg.topic, msg.body, message_id)


@dataclass
class DryRunPusher(Pusher):
    def _deliver(self, msg: PushMessage) -> None:
        print(f"[dry-run] PUSH topic={msg.topic} title={msg.title!r} body={msg.body!r} data={msg.data}")


@dataclass
class DisabledPusher(Pusher):
    active: bool = False

    def _deliver(self, msg: PushMessage) -> None:
        print(f"[no-push] would PUSH topic={msg.topic} body={msg.body!r} data={msg.data}")
