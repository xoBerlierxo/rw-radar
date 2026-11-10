"""Shared helpers. Every test runs offline: fixtures are saved real responses (Day-1 spike)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

from rwradar_poller import registry
from rwradar_poller.models import Company

FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str) -> Any:
    with (FIXTURES / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def load_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeClock:
    """Deterministic clock: returns ``now`` and can be advanced."""

    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> datetime:
        self.now = self.now + timedelta(**kwargs)
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def sample_companies() -> list[Company]:
    return registry.load(FIXTURES / "registry_sample.json")


@pytest.fixture
def fixture_loader() -> Callable[[str], Any]:
    return load_json
