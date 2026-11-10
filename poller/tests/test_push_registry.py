"""Push payloads (CLAUDE.md §4.3), registry validation (PLAN §3) and the store's merge semantics."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from rwradar_poller import config, registry
from rwradar_poller.push import DisabledPusher, FcmPusher, job_push, signal_push
from rwradar_poller.store import InMemoryStore, JobWrite

from .conftest import FIXTURES


@pytest.mark.parametrize(
    "family,count,body",
    [
        ("eng", 3, "3 new Engineering roles at Groww"),
        ("eng", 1, "1 new Engineering role at Groww"),
        ("gtm", 2, "2 new Marketing/Sales roles at Groww"),
        ("design", 1, "1 new Design role at Groww"),
        ("data", 4, "4 new Data roles at Groww"),
        ("product", 1, "1 new Product role at Groww"),
        ("other", 2, "2 new Other roles at Groww"),
    ],
)
def test_job_push_copy(family: str, count: int, body: str) -> None:
    msg = job_push("groww", "Groww", family, count, 1_762_776_000_000)
    assert msg.topic == f"c_groww_{family}"
    assert msg.title == "Groww" and msg.body == body
    assert msg.data == {"type": "jobs", "companyId": "groww", "family": family, "since": "1762776000000"}
    assert all(isinstance(v, str) for v in msg.data.values())
    assert msg.channel_id == "new_openings" and msg.analytics_label == f"jobs_{family}"


def test_signal_push_copy() -> None:
    msg = signal_push("sarvam", "Sarvam AI", 47, "f" * 40)
    assert msg.topic == "c_sarvam_signal"
    assert msg.body == "Sarvam AI raised funding. 47 open roles right now."
    assert msg.data == {"type": "signal", "companyId": "sarvam", "newsHash": "f" * 40}
    assert msg.channel_id == "hiring_signals" and msg.analytics_label == "signal"


def test_family_labels_match_contract() -> None:
    assert config.FAMILY_LABELS == {
        "design": "Design", "data": "Data", "product": "Product",
        "gtm": "Marketing/Sales", "eng": "Engineering", "other": "Other",
    }
    assert config.NEWS_TAGS == ("funding", "layoffs", "acquisition", "financials", "other")


def test_pusher_modes() -> None:
    sent = []
    fcm = FcmPusher(transport=lambda m: sent.append(m.topic) or "id", debug_all=True)
    fcm.send(job_push("groww", "Groww", "eng", 1, 0))
    assert sent == ["c_groww_eng", "debug_all"] and fcm.active
    disabled = DisabledPusher()
    disabled.send(job_push("groww", "Groww", "eng", 1, 0))
    assert not disabled.active and len(disabled.sent) == 1


def test_fcm_message_shape() -> None:
    """The real transport builds a notification + data message, high priority, channel, label."""
    from firebase_admin import messaging

    from rwradar_poller.store import FirestoreStore

    store = FirestoreStore.__new__(FirestoreStore)  # skip credential init
    store._app = None  # type: ignore[attr-defined]
    captured = {}

    def fake_send(message: messaging.Message, app: object = None) -> str:
        captured["m"] = message
        return "ok"

    original = messaging.send
    messaging.send = fake_send  # type: ignore[assignment]
    try:
        store.push_transport()(job_push("groww", "Groww", "eng", 2, 5))
    finally:
        messaging.send = original  # type: ignore[assignment]
    m = captured["m"]
    assert m.topic == "c_groww_eng"
    assert m.notification.title == "Groww" and m.notification.body == "2 new Engineering roles at Groww"
    assert m.data["type"] == "jobs" and m.data["since"] == "5"
    assert m.android.priority == "high" and m.android.notification.channel_id == "new_openings"
    assert m.fcm_options.analytics_label == "jobs_eng"


# --- registry ----------------------------------------------------------------------------------


def test_sample_registry_loads() -> None:
    companies = registry.load(FIXTURES / "registry_sample.json")
    assert [c.id for c in companies][:3] == ["groww", "druva", "cred"]
    sarvam = next(c for c in companies if c.id == "sarvam")
    assert sarvam.registry_fields() == {
        "id": "sarvam", "name": "Sarvam AI", "aliases": ["Sarvam"], "sector": "AI",
        "website": "https://www.sarvam.ai", "ats": {"type": "ashby", "token": "sarvam"}, "logoUrl": "",
    }


def _entry(**over: object) -> dict:
    base = {"id": "acme", "name": "Acme", "aliases": [], "sector": "SaaS", "website": "https://acme.test",
            "ats": {"type": "lever", "token": "acme"}, "logoUrl": ""}
    base.update(over)
    return base


@pytest.mark.parametrize(
    "entries,needle",
    [
        ([_entry(id="Acme")], "id must match"),
        ([_entry(id="acme_1")], "id must match"),
        ([_entry(), _entry(ats={"type": "lever", "token": "other"})], "duplicate id"),
        ([_entry(ats={"type": "workday", "token": "acme"})], "ats.type"),
        ([_entry(ats={"type": "lever", "token": "a/b"})], "ats.token"),
        ([_entry(name="")], "'name'"),
        ([_entry(aliases="Acme Inc")], "'aliases'"),
        ([_entry(website="acme.test")], "website"),
        ([_entry(), _entry(id="acme-2")], "same ATS board"),
        ({"companies": []}, "JSON array"),
    ],
)
def test_registry_validation_errors(entries: object, needle: str) -> None:
    report = registry.validate_data(entries)
    assert not report.ok
    assert any(needle in e for e in report.errors), report.errors


def test_registry_validation_warnings() -> None:
    report = registry.validate_data([_entry(aliases=["AC"]), _entry(id="acme-two", name="Acme Two", aliases=["Acme"],
                                                                  ats={"type": "ashby", "token": "acme2"})])
    assert report.ok
    text = "\n".join(report.warnings)
    assert "very short" in text and "also used by" in text and "target 100" in text


def test_registry_load_rejects_invalid(tmp_path: Path) -> None:
    path = tmp_path / "companies.json"
    path.write_text(json.dumps([_entry(id="Bad Id")]), encoding="utf-8")
    with pytest.raises(registry.RegistryError):
        registry.load(path)


def test_select_company() -> None:
    companies = registry.load(FIXTURES / "registry_sample.json")
    assert [c.id for c in registry.select(companies, "zeta")] == ["zeta"]
    with pytest.raises(registry.RegistryError):
        registry.select(companies, "nope")


def test_paths_resolve_from_repo_root() -> None:
    assert config.REGISTRY_PATH.parts[-2:] == ("registry", "companies.json")
    assert (config.REPO_ROOT / "poller" / "rwradar_poller").is_dir()


# --- store merge semantics ---------------------------------------------------------------------


def test_in_memory_store_merge_replaces_top_level_fields_only() -> None:
    store = InMemoryStore()
    t = datetime(2026, 11, 10, tzinfo=timezone.utc)
    store.merge_company_fields("x", {"lastFundingAt": t})
    store.commit_company("x", {"jobIndex": {"a": {"h": "1"}, "b": {"h": "2"}}}, [JobWrite("a", {"title": "A", "status": "open"}, False)])
    store.commit_company("x", {"jobIndex": {"a": {"h": "1"}}}, [JobWrite("a", {"status": "closed"}, True)])
    assert store.companies["x"] == {"lastFundingAt": t, "jobIndex": {"a": {"h": "1"}}}
    assert store.jobs["x"]["a"] == {"title": "A", "status": "closed"}
