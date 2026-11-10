"""Headline -> company ids (PLAN §4.5 step 4), plus the news blocklist.

Matching: exact phrase, case-insensitive, word-boundary match of the company name or any alias
in the headline (whitespace inside a phrase matches any run of whitespace). "CRED-owned Happay"
matches CRED, and "Zepto's" matches Zepto. "Groww" does not match "Growwth".

Funding items only: the matched company must be the one *raising* the money.
- The company must appear before the funding verb: the first raise verb ("raises $", "secures",
  "bags"), or if there is none, the first funding keyword ("funding", "Series B", "led by").
  In "Sarvam ... $234 Mn funding round led by HCLTech", Sarvam matches and HCLTech does not; in
  "Funding Wrap: Sarvam, Rusk Media raise fresh capital", Sarvam matches.
- If an investor marker comes first ("invests in", "-backed", "backs", "participates in",
  "bets on"), the companies *before* it are investors and do not match. The funded company is the
  one after the marker (and before the funding verb, if there is one). So "X invests in Y" -> Y, and
  "Tiger Global-backed Groww raises $100 Mn" -> Groww.

Blocklist file: ``registry/news_blocklist.json``
------------------------------------------------
::

    {
      "version": 1,
      "rules": [
        {"companyId": "zeta",  "phrase": "Zeta Global", "note": "US adtech, not Zeta (Bengaluru)"},
        {"companyId": "cred",  "caseSensitive": true,   "note": "match only 'CRED' in capitals"},
        {"companyId": "groww", "newsHash": "<sha1 of the normalized URL>", "note": "wrong match"},
        {"companyId": "*",     "newsHash": "<sha1>",   "note": "drop this item for everyone"}
      ]
    }

Each rule has ``companyId`` (a registry id, or ``"*"`` for ``newsHash`` rules), an optional
``note``, and exactly one of:

- ``phrase`` (string): a company match that falls *inside* an occurrence of this phrase is
  ignored (case-insensitive, word boundaries). Use it for a different organization with a similar
  name ("Zeta Global", "Catherine Zeta-Jones", "Eagle Point Cred").
- ``caseSensitive`` (true): this company's name and aliases are matched with exact case
  ("CRED" matches, "AI cred" does not).
- ``newsHash`` (40-char hex, the ``news/{hash}`` doc id): never attach this company (or, with
  ``"*"``, any company) to that item. Use it for one-off wrong matches found in the Day-9 review.
- ``aliasesOnly`` (true): never match the bare ``name``, only the ``aliases`` (e.g. "Toast" is
  ignored, "Toast Inc" / "Toasttab" match). Google News queries also use the aliases. Use it for
  companies whose name is a common word or person's name (Toast, Harvey, Plane, Wiz, G2...).

Unknown ``companyId`` values are ignored at run time and reported by ``validate-registry``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .. import config
from ..models import Company
from .tagger import FUNDING_RE, INVESTOR_RE, RAISE_VERB_RE, normalize_headline

HASH_RE = re.compile(r"^[0-9a-f]{40}$")


class BlocklistError(Exception):
    pass


@dataclass
class Blocklist:
    phrases: dict[str, list[str]] = field(default_factory=dict)  # company id -> phrases
    case_sensitive: set[str] = field(default_factory=set)
    aliases_only: set[str] = field(default_factory=set)
    hashes: dict[str, set[str]] = field(default_factory=dict)  # news hash -> company ids ("*" = all)

    @property
    def company_ids(self) -> set[str]:
        ids = set(self.phrases) | self.case_sensitive | self.aliases_only
        for owners in self.hashes.values():
            ids |= owners
        ids.discard("*")
        return ids

    @classmethod
    def from_data(cls, data: Any) -> "Blocklist":
        if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
            raise BlocklistError('blocklist must be an object with a "rules" array')
        bl = cls()
        for i, rule in enumerate(data["rules"]):
            where = f"rule #{i}"
            if not isinstance(rule, dict):
                raise BlocklistError(f"{where}: not an object")
            cid = rule.get("companyId")
            if not isinstance(cid, str) or not cid:
                raise BlocklistError(f"{where}: companyId must be a non-empty string")
            kinds = [k for k in ("phrase", "caseSensitive", "newsHash", "aliasesOnly") if k in rule]
            if len(kinds) != 1:
                raise BlocklistError(f"{where}: needs exactly one of phrase / caseSensitive / newsHash / aliasesOnly")
            kind = kinds[0]
            if cid == "*" and kind != "newsHash":
                raise BlocklistError(f'{where}: companyId "*" is only allowed with newsHash')
            if kind == "phrase":
                phrase = rule["phrase"]
                if not isinstance(phrase, str) or not phrase.strip():
                    raise BlocklistError(f"{where}: phrase must be a non-empty string")
                bl.phrases.setdefault(cid, []).append(" ".join(phrase.split()))
            elif kind == "caseSensitive":
                if rule["caseSensitive"] is not True:
                    raise BlocklistError(f"{where}: caseSensitive must be true")
                bl.case_sensitive.add(cid)
            elif kind == "aliasesOnly":
                if rule["aliasesOnly"] is not True:
                    raise BlocklistError(f"{where}: aliasesOnly must be true")
                bl.aliases_only.add(cid)
            else:
                news_hash = rule["newsHash"]
                if not isinstance(news_hash, str) or not HASH_RE.match(news_hash):
                    raise BlocklistError(f"{where}: newsHash must be a 40-char lowercase hex sha1")
                bl.hashes.setdefault(news_hash, set()).add(cid)
        return bl

    @classmethod
    def load(cls, path: Path | None = None) -> "Blocklist":
        path = path or config.BLOCKLIST_PATH
        if not path.exists():
            return cls()
        with path.open(encoding="utf-8") as fh:
            try:
                return cls.from_data(json.load(fh))
            except json.JSONDecodeError as exc:
                raise BlocklistError(f"{path.name}: invalid JSON: {exc}") from exc


def match_names(company: Company, blocklist: Blocklist | None = None) -> list[str]:
    """Names used to match headlines and build Google News queries for this company."""
    if blocklist is not None and company.id in blocklist.aliases_only:
        return list(company.aliases)
    return [company.name, *company.aliases]


def _phrase_regex(phrases: Iterable[str], case_sensitive: bool) -> re.Pattern[str] | None:
    parts = sorted({" ".join(p.split()) for p in phrases if p and p.strip()}, key=len, reverse=True)
    if not parts:
        return None
    alternatives = "|".join(r"\s+".join(re.escape(word) for word in p.split(" ")) for p in parts)
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", flags)


class Matcher:
    def __init__(self, companies: Iterable[Company], blocklist: Blocklist | None = None) -> None:
        self.blocklist = blocklist or Blocklist()
        self._companies: list[tuple[str, re.Pattern[str], re.Pattern[str] | None]] = []
        for company in companies:
            pattern = _phrase_regex(
                match_names(company, self.blocklist), company.id in self.blocklist.case_sensitive
            )
            if pattern is None:
                continue
            blocked = _phrase_regex(self.blocklist.phrases.get(company.id, []), case_sensitive=False)
            self._companies.append((company.id, pattern, blocked))

    def query_names(self, company: Company) -> list[str]:
        """Google News query terms for ``company``: its name, or its aliases if ``aliasesOnly``."""
        names = match_names(company, self.blocklist)
        return names[:1] if company.id not in self.blocklist.aliases_only else names

    @staticmethod
    def _funding_window(lower: str) -> tuple[int, int]:
        """[start, end) span of the headline where the funded company may appear.

        The end is the first raise verb ("raises $", "secures", "bags"); if there is none, the
        first other funding keyword ("funding", "Series B", "led by").
        """
        investor = INVESTOR_RE.search(lower)
        recipient_start: int | None = None
        for pattern in (RAISE_VERB_RE, FUNDING_RE):
            for m in pattern.finditer(lower):
                if investor and m.start() < investor.end() and investor.start() < m.end():
                    continue  # the investor verb itself ("invests $10 Mn") is not the raise verb
                recipient_start = m.start()
                break
            if recipient_start is not None:
                break
        end = recipient_start if recipient_start is not None else len(lower) + 1
        if investor is not None and investor.start() < end:
            return investor.end(), end
        return 0, end

    def match(self, title: str, tag: str, news_hash: str | None = None) -> list[str]:
        """Company ids for this headline, in registry order."""
        text = normalize_headline(title)
        if not text:
            return []
        window = self._funding_window(text.lower()) if tag == "funding" else (0, len(text) + 1)
        blocked_for_item = self.blocklist.hashes.get(news_hash or "", set())
        if "*" in blocked_for_item:
            return []
        out: list[str] = []
        for company_id, pattern, blocked in self._companies:
            if company_id in blocked_for_item:
                continue
            blocked_spans = [m.span() for m in blocked.finditer(text)] if blocked else []
            for m in pattern.finditer(text):
                if any(s <= m.start() and m.end() <= e for s, e in blocked_spans):
                    continue
                if window[0] <= m.start() < window[1]:
                    out.append(company_id)
                    break
        return out
