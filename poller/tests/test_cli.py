"""CLI wiring: validate-registry and a jobs --dry-run, offline (fixtures instead of the network)."""

from __future__ import annotations

from typing import Any

import pytest

from rwradar_poller import __main__ as cli
from rwradar_poller import ats, config
from rwradar_poller.ats import greenhouse

from .conftest import FIXTURES, load_json


@pytest.fixture
def sample_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "REGISTRY_PATH", FIXTURES / "registry_sample.json")
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT", raising=False)


def test_validate_registry_ok(sample_registry: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["validate-registry"]) == 0
    out = capsys.readouterr().out
    assert "7 companies, 0 errors" in out
    assert "target 100" in out


def test_validate_registry_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(config, "REGISTRY_PATH", tmp_path / "companies.json")
    assert cli.main(["validate-registry"]) == 2
    assert "registry not found" in capsys.readouterr().out


def test_validate_registry_reports_unknown_blocklist_ids(
    sample_registry: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    bl = tmp_path / "news_blocklist.json"
    bl.write_text('{"version": 1, "rules": [{"companyId": "ghost", "phrase": "Ghost Inc"}]}', encoding="utf-8")
    monkeypatch.setattr(config, "BLOCKLIST_PATH", bl)
    assert cli.main(["validate-registry"]) == 0
    assert "'ghost' is not in the registry" in capsys.readouterr().out


def test_jobs_dry_run_single_company(sample_registry: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_greenhouse(client: Any, token: str) -> list:
        return greenhouse.normalize(load_json(f"greenhouse_{token}.json"), load_json(f"greenhouse_{token}_departments.json"))

    monkeypatch.setitem(ats._FETCHERS, "greenhouse", fake_greenhouse)
    assert cli.main(["jobs", "--dry-run", "--company", "groww"]) == 0
    out = capsys.readouterr().out
    assert "[dry-run] MERGE companies/groww" in out
    assert "9 job doc writes (9 new, 0 updates)" in out
    assert "[dry-run] SET pollerRuns/jobs-" in out
    assert "PUSH" not in out  # seeding run against an empty store


def test_unknown_company_exits_2(sample_registry: None) -> None:
    assert cli.main(["jobs", "--dry-run", "--company", "nope"]) == 2


def test_real_run_without_credentials_fails_cleanly(sample_registry: None) -> None:
    assert cli.main(["jobs", "--company", "groww"]) == 1
