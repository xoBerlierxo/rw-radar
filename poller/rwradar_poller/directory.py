"""``directory/v1``: one summary row per company, read by the app in a single doc read (D3).

Row fields (CLAUDE.md §4.2): ``id, name, aliases[], sector, openCount, newThisWeek, lastFundingAt,
logoUrl``. Rows are sorted by name.

Both workflows patch the doc inside a transaction (``Store.update_directory``) and only touch their
own fields: the jobs run patches ``openCount``/``newThisWeek``, the news run patches
``lastFundingAt``; registry fields are refreshed from ``companies.json`` by either. The doc is
written only if a row actually changed, and companies that left the registry are dropped.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from .models import Company
from .store import DirectoryMutator

ROW_FIELDS = ("id", "name", "aliases", "sector", "openCount", "newThisWeek", "lastFundingAt", "logoUrl")


def _registry_part(company: Company) -> dict[str, Any]:
    return {
        "id": company.id,
        "name": company.name,
        "aliases": list(company.aliases),
        "sector": company.sector,
        "logoUrl": company.logo_url,
    }


def default_row(company: Company) -> dict[str, Any]:
    return {**_registry_part(company), "openCount": 0, "newThisWeek": 0, "lastFundingAt": None}


def build_rows(
    current: dict[str, Any] | None,
    registry: Iterable[Company],
    patches: dict[str, dict[str, Any]],
    defaults: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """New row list: existing rows, refreshed registry fields, ``patches`` applied.

    ``defaults[cid]`` seeds fields of a row that does not exist yet (e.g. lastFundingAt from the
    company doc).
    """
    existing = {row.get("id"): row for row in (current or {}).get("companies", []) if isinstance(row, dict)}
    rows: list[dict[str, Any]] = []
    for company in registry:
        if company.id in existing:
            row = {**default_row(company), **{k: existing[company.id].get(k) for k in ROW_FIELDS if k in existing[company.id]}}
        else:
            row = {**default_row(company), **(defaults or {}).get(company.id, {})}
        row.update(_registry_part(company))
        row.update(patches.get(company.id, {}))
        rows.append({k: row.get(k) for k in ROW_FIELDS})
    rows.sort(key=lambda r: (str(r["name"]).lower(), r["id"]))
    return rows


def make_mutator(
    registry: list[Company],
    patches: dict[str, dict[str, Any]],
    now: datetime,
    defaults: dict[str, dict[str, Any]] | None = None,
) -> DirectoryMutator:
    def mutate(current: dict[str, Any] | None) -> dict[str, Any] | None:
        rows = build_rows(current, registry, patches, defaults)
        if current is not None and current.get("companies") == rows:
            return None
        return {"updatedAt": now, "companies": rows}

    return mutate
