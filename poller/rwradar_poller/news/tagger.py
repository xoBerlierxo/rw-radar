"""Headline -> news tag key (PLAN §4.5 step 3; CLAUDE.md §4.1 tag keys).

First match wins, in this order: ``layoffs`` > ``acquisition`` > ``funding`` > ``financials`` >
``other``. Patterns are word-boundary regexes on the lowercased headline.

Changes from the PLAN keyword list, all driven by real headlines from the Day-1 spike
(``tests/test_tagger.py`` holds them):
- "raises/raised/raise" counts as funding only when money or a round word follows within one word
  ("raises $2.7M", "raises fresh capital", "raises Series A"). A bare "raises" gave false hits:
  "Truist raises Zeta Global stock price target", "AI raises the bar on recovery",
  "Zeta Raises Guide to $1.855B".
- "buys" -> "buys|bought|to buy" ("Meesho Limited to Buy Kirana Club") without matching
  "Maintains Buy Rating"; "acquire" (bare) added ("L'Oreal to acquire majority stake").
- funding also covers "fundraise", "secures/bags $...", "invests $/in", "$X Mn round". "X-backed"
  is *not* a funding signal ("Y Combinator-backed Orange Health posts revenue" is financials).
- layoffs also covers "laid off", "sacks", "pink slips", "cuts N jobs".
- "arr" and "ipo" are whole words only ("arrives", "tipoff" do not match); financials also covers
  earnings, EBITDA, "turns profitable", guidance, price target.

``FUNDING_RE`` is exported for the matcher (the funding verb's position decides which company
raised the money) together with ``INVESTOR_RE`` ("X invests in Y", "X-backed Y").
"""

from __future__ import annotations

import re

_MONEY = r"(?:[$₹€£]|rs\b\.?|inr\b|usd\b|us\$|\d)"
_ROUNDISH = (
    r"(?:funds?\b|funding\b|capital\b|money\b|seed\b|pre-?seed\b|series\b|pre-?series\b|bridge\b|"
    r"debt\b|round\b|undisclosed\b|investments?\b|fresh\b|growth\s+capital\b)"
)

LAYOFFS_RE = re.compile(
    r"\blay(?:s|ing)?[\s-]?offs?\b"
    r"|\blaid[\s-]?off\b"
    r"|\bjob\s+cuts?\b"
    r"|\bcut(?:s|ting)?\s+(?:(?:another|over|around|nearly|about|up\s+to)\s+)?(?:[\d,.]+%?\s+|\w+\s+)?(?:jobs|roles|staff|employees|workforce|headcount)\b"
    r"|\bretrench\w*"
    r"|\bdownsiz\w*"
    r"|\bfires\b|\bfired\b"
    r"|\bsack(?:s|ed|ing)\b"
    r"|\bpink\s+slips?\b"
)

ACQUISITION_RE = re.compile(
    r"\bacquir(?:e|es|ed|ing)\b"
    r"|\bacquisitions?\b"
    r"|\bmerg(?:er|ers|es|ed|ing)\b"
    r"|\bbuys\b|\bbought\b|\bto\s+buy\b"
    r"|\btakeover\b|\btakes\s+over\b"
    r"|\bmajority\s+stake\b"
)

_RAISE_VERBS = (
    # "raised to $41" is a price-target/guidance change, never a round: no "to" after the verb.
    rf"\brais(?:e|es|ed|ing)\s+(?!to\b)(?:\S+\s+)?(?:{_MONEY}|{_ROUNDISH})"
    r"|\bfund-?rais\w*"
    rf"|\bsecur(?:es|ed)\s+(?:\S+\s+)?(?:{_MONEY}|funding\b|investment\b|capital\b|strategic\s+investment\b)"
    rf"|\bbag(?:s|ged)\s+(?:\S+\s+)?(?:{_MONEY}|funding\b|investment\b)"
)

# The verb that says *who* raised ("Funding Wrap: Sarvam, Rusk Media raise fresh capital"): the
# matcher prefers it over nouns like "funding" when deciding which company raised the money.
RAISE_VERB_RE = re.compile(_RAISE_VERBS)

FUNDING_RE = re.compile(
    _RAISE_VERBS
    + r"|\bfunding\b"
    r"|\bseries\s+[a-h]\b"
    r"|\bpre-?series\b"
    r"|\bpre-?seed\b"
    r"|\bseed\s+(?:round|funding|capital|investment|stage)\b"
    r"|\bbridge\s+round\b"
    r"|\bmega\s+round\b"
    r"|(?:mn|million|bn|billion|cr|crore|lakh)\s+(?:\w+\s+)?round\b"
    r"|\bled\s+by\b"
    rf"|\binvest(?:s|ed)?\s+(?:{_MONEY}|in\b)"
)

FINANCIALS_RE = re.compile(
    r"\brevenues?\b"
    r"|\bprofit\w*"
    r"|\bloss(?:es)?\b"
    r"|\bfy\s?'?\d{2}\b"
    r"|\bipos?\b"
    r"|\bvaluations?\b"
    r"|\barr\b"
    r"|\bebitda\b"
    r"|\beps\b"
    r"|\bearnings\b"
    r"|\bnet\s+income\b"
    r"|\btotal\s+income\b"
    r"|\bbreak-?even\b"
    r"|\bguidance\b"
    r"|\b(?:raises?|lifts?|cuts?)\s+(?:its\s+)?(?:guide|outlook|forecast)\b"
    r"|\bprice\s+target\b"
    r"|\bturnover\b"
)

# "X invests in Y", "X-backed Y", "X participates in Y's round": X is the investor, not the raiser.
INVESTOR_RE = re.compile(
    rf"\binvest(?:s|ed)?\s+(?:{_MONEY}|in\b)"
    r"|-backed\b|\bbacks\b"
    r"|\bparticipates?\s+in\b"
    r"|\bbets?\s+(?:\S+\s+)?on\b"
    r"|\b(?:pumps|infuses|injects)\b"
)

RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("layoffs", LAYOFFS_RE),
    ("acquisition", ACQUISITION_RE),
    ("funding", FUNDING_RE),
    ("financials", FINANCIALS_RE),
)


def normalize_headline(title: str) -> str:
    return " ".join((title or "").replace("’", "'").split())


def tag(title: str) -> str:
    """Return ``layoffs|acquisition|funding|financials|other`` for a headline."""
    text = normalize_headline(title).lower()
    for key, pattern in RULES:
        if pattern.search(text):
            return key
    return "other"
