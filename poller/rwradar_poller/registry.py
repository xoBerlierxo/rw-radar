"""Load and validate ``registry/companies.json`` (PLAN §3).

``validate`` checks the schema, the id slug format, unique ids and unique ATS boards, and flags
risky aliases. ``check_endpoints`` (``validate-registry --check-endpoints``) fetches every board and
requires HTTP 200 with a valid payload. It also warns when a board has no job in India or remote
(PLAN §3: keep a company only if it has at least one).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import ats, config
from .http import FetchError, HttpClient
from .models import Company, Job

SLUG_RE = re.compile(r"^[a-z0-9-]+$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")
REQUIRED_STR_FIELDS = ("id", "name", "sector", "website")
EXPECTED_COUNT = 100

# Location words that count as "India or remote" for the endpoint check.
_INDIA_WORDS = (
    "india", "remote", "bengaluru", "bangalore", "mumbai", "delhi", "ncr", "gurgaon", "gurugram",
    "noida", "pune", "hyderabad", "chennai", "kolkata", "ahmedabad", "jaipur", "kochi", "indore",
    "chandigarh", "coimbatore", "surat", "lucknow", "thane", "navi mumbai", "mysore", "mysuru",
)


class RegistryError(Exception):
    pass


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _company_from_dict(raw: dict[str, Any]) -> Company:
    ats_obj = raw.get("ats") or {}
    return Company(
        id=raw["id"],
        name=" ".join(str(raw["name"]).split()),
        aliases=tuple(" ".join(str(a).split()) for a in raw.get("aliases") or [] if str(a).strip()),
        sector=str(raw.get("sector") or ""),
        website=str(raw.get("website") or ""),
        ats_type=str(ats_obj.get("type") or ""),
        ats_token=str(ats_obj.get("token") or ""),
        logo_url=str(raw.get("logoUrl") or ""),
    )


def load_raw(path: Path | None = None) -> Any:
    path = path or config.REGISTRY_PATH
    if not path.exists():
        raise RegistryError(f"registry not found: {path}")
    with path.open(encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            raise RegistryError(f"{path.name}: invalid JSON: {exc}") from exc


def validate_data(data: Any) -> ValidationReport:
    """Schema checks on the parsed JSON (no network)."""
    report = ValidationReport()
    if not isinstance(data, list):
        report.errors.append("registry must be a JSON array of company objects")
        return report
    seen_ids: set[str] = set()
    seen_boards: dict[tuple[str, str], str] = {}
    phrase_owner: dict[str, str] = {}
    for i, raw in enumerate(data):
        where = f"entry #{i}"
        if not isinstance(raw, dict):
            report.errors.append(f"{where}: not an object")
            continue
        cid = raw.get("id")
        if isinstance(cid, str):
            where = f"{where} ({cid})"
        for key in REQUIRED_STR_FIELDS:
            value = raw.get(key)
            if not isinstance(value, str) or not value.strip():
                report.errors.append(f"{where}: '{key}' must be a non-empty string")
        if isinstance(cid, str):
            if not SLUG_RE.match(cid):
                report.errors.append(f"{where}: id must match {SLUG_RE.pattern}")
            if cid in seen_ids:
                report.errors.append(f"{where}: duplicate id")
            seen_ids.add(cid)
        website = raw.get("website")
        if isinstance(website, str) and website and not website.startswith(("https://", "http://")):
            report.errors.append(f"{where}: website must start with http(s)://")
        aliases = raw.get("aliases")
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            report.errors.append(f"{where}: 'aliases' must be an array of strings")
            aliases = []
        logo = raw.get("logoUrl", "")
        if logo is not None and not isinstance(logo, str):
            report.errors.append(f"{where}: 'logoUrl' must be a string")
        ats_obj = raw.get("ats")
        if not isinstance(ats_obj, dict):
            report.errors.append(f"{where}: 'ats' must be an object {{type, token}}")
        else:
            ats_type, token = ats_obj.get("type"), ats_obj.get("token")
            if ats_type not in ats.ATS_TYPES:
                report.errors.append(f"{where}: ats.type must be one of {', '.join(ats.ATS_TYPES)}")
            if not isinstance(token, str) or not TOKEN_RE.match(token):
                report.errors.append(f"{where}: ats.token must match {TOKEN_RE.pattern}")
            elif isinstance(ats_type, str):
                board = (ats_type, token.lower())
                if board in seen_boards:
                    report.errors.append(f"{where}: same ATS board as {seen_boards[board]}")
                seen_boards[board] = str(cid)
        # Matching phrases (name + aliases): short ones and ones shared by two companies are risky.
        name = raw.get("name") if isinstance(raw.get("name"), str) else ""
        for phrase in [name, *aliases]:
            key = " ".join(phrase.lower().split())
            if not key:
                continue
            if len(key) < 3:
                report.warnings.append(f"{where}: name/alias {phrase!r} is very short; headline matches will be noisy")
            owner = phrase_owner.get(key)
            if owner is not None and owner != cid:
                report.warnings.append(f"{where}: name/alias {phrase!r} is also used by {owner}")
            phrase_owner.setdefault(key, str(cid))
    if len(data) != EXPECTED_COUNT:
        report.warnings.append(f"registry has {len(data)} companies (target {EXPECTED_COUNT})")
    return report


def load(path: Path | None = None) -> list[Company]:
    """Load and validate; raises :class:`RegistryError` listing every schema error."""
    data = load_raw(path)
    report = validate_data(data)
    if not report.ok:
        raise RegistryError("invalid registry:\n  " + "\n  ".join(report.errors))
    return [_company_from_dict(raw) for raw in data]


def select(companies: Iterable[Company], company_id: str | None) -> list[Company]:
    companies = list(companies)
    if company_id is None:
        return companies
    chosen = [c for c in companies if c.id == company_id]
    if not chosen:
        raise RegistryError(f"company {company_id!r} is not in the registry")
    return chosen


def india_or_remote(job: Job) -> bool:
    loc = job.location.lower()
    return job.remote or any(word in loc for word in _INDIA_WORDS)


def check_endpoints(companies: Iterable[Company], client: HttpClient, report: ValidationReport) -> None:
    """Fetch every board; errors for non-200/invalid payloads, warnings for no India/remote jobs."""
    for company in companies:
        try:
            jobs = ats.fetch_jobs(client, company.ats_type, company.ats_token)
        except FetchError as exc:
            report.errors.append(f"{company.id}: {company.ats_type}/{company.ats_token} fetch failed: {exc}")
            continue
        local = sum(1 for j in jobs if india_or_remote(j))
        print(f"  {company.id:28} {company.ats_type:10} {len(jobs):4} jobs, {local:4} India/remote")
        if not jobs:
            report.warnings.append(f"{company.id}: board returned 0 jobs")
        elif not local:
            report.warnings.append(f"{company.id}: no job located in India or remote")
