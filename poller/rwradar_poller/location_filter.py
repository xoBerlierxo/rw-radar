"""Keep only jobs relevant to the target audience: located in India, or remote and open to India.

Why: the registry includes global companies whose boards hold hundreds of non-India jobs
(e.g. OpenAI ~830 jobs, 7 in India). Storing and pushing those would spam Indian job seekers
(spec §2) and cost ~12k Firestore writes on the seeding run against a 20k/day quota.

Rules (case-insensitive, word boundaries):
- Keep if the location names India or an Indian city/state.
- Keep a remote job only if its location is India or generic ("Remote", "Anywhere", "Worldwide",
  "Global", "APAC", "Asia"). "Remote - US" or "Remote, Germany" is dropped.

Disable the filter with ``RWRADAR_INDIA_ONLY=0`` (then every job is kept, as in PLAN v1.0).
"""

from __future__ import annotations

import re

from .models import Job

_INDIA = [
    "india", "bengaluru", "bangalore", "mumbai", "navi mumbai", "thane", "delhi", "new delhi", "ncr",
    "delhi ncr", "gurgaon", "gurugram", "noida", "greater noida", "pune", "hyderabad", "secunderabad",
    "chennai", "kolkata", "ahmedabad", "gandhinagar", "jaipur", "kochi", "cochin", "trivandrum",
    "thiruvananthapuram", "coimbatore", "indore", "chandigarh", "mohali", "lucknow", "bhubaneswar",
    "nagpur", "mysore", "mysuru", "mangalore", "mangaluru", "vadodara", "surat", "goa", "visakhapatnam",
    "karnataka", "maharashtra", "telangana", "tamil nadu", "haryana", "kerala", "gujarat",
    "west bengal", "uttar pradesh", "rajasthan",
]
_INDIA_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(_INDIA, key=len, reverse=True)) + r")\b", re.I)

# Words that may appear in a location that is open to India without naming it.
_GENERIC_WORDS = {
    "remote", "anywhere", "worldwide", "global", "globally", "apac", "asia", "asia pacific",
    "distributed", "work from home", "wfh", "fully remote", "remote first", "remote-first", "hybrid",
    "flexible", "multiple locations", "various", "",
}
_SPLIT_RE = re.compile(r"[,/;|()\-–—•]+|\bor\b|\band\b", re.I)


def is_india_location(location: str) -> bool:
    return bool(_INDIA_RE.search(location or ""))


def _is_generic(location: str) -> bool:
    parts = [p.strip().lower() for p in _SPLIT_RE.split(location or "")]
    return all(p in _GENERIC_WORDS for p in parts)


def keep_job(job: Job) -> bool:
    if is_india_location(job.location):
        return True
    if job.remote or "remote" in (job.location or "").lower():
        return _is_generic(job.location)
    return False


def filter_jobs(jobs: list[Job]) -> list[Job]:
    return [j for j in jobs if keep_job(j)]
