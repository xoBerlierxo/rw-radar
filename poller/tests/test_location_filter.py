from datetime import datetime, timezone

import pytest

from rwradar_poller.location_filter import keep_job
from rwradar_poller.models import Job


def _job(location: str, remote: bool = False) -> Job:
    return Job("greenhouse", "1", "Software Engineer", location, "Eng", remote, "https://x", datetime.now(timezone.utc), "eng")


@pytest.mark.parametrize("loc", [
    "Bengaluru, Karnataka, India", "Bangalore", "Gurugram", "Remote - India", "India", "Mumbai / Pune",
    "Hyderabad, Telangana", "New Delhi", "Noida, Uttar Pradesh",
])
def test_keeps_india(loc):
    assert keep_job(_job(loc))


@pytest.mark.parametrize("loc,remote", [
    ("Remote", True), ("Anywhere", True), ("Remote - APAC", True), ("Worldwide", True), ("Remote", False),
])
def test_keeps_generic_remote(loc, remote):
    assert keep_job(_job(loc, remote))


@pytest.mark.parametrize("loc,remote", [
    ("San Francisco, CA", False), ("Remote - US", True), ("Remote, Germany", True), ("London", False),
    ("Indianapolis, IN", False), ("New York; Remote", True), ("Remote - EMEA", True), ("", False),
])
def test_drops_non_india(loc, remote):
    assert not keep_job(_job(loc, remote))
