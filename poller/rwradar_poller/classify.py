"""Job title -> role family key (PLAN §4.3, D9).

The rules are checked in a fixed order and the first match wins:
``design`` > ``data`` > ``product`` > ``gtm`` > ``eng`` > ``other``.
So "Product Designer" -> design, "Data Engineer" -> data, "Sales Engineer" -> gtm.

Keywords are matched as regexes on the lowercased title with word boundaries, which avoids the
substring traps found in the Day-1 spike titles: "Database Engineer" is not "data", "PMS" is not
"pm", "DataLake" is not "data". Each family may also have *exclusions* (if one matches, the family
is skipped and the next one is tried). They come from real titles:

- data: security analyst titles ("Analyst II - SIEM/SecOps") fall through to eng.
- gtm: "Employer Branding" is HR, not marketing; "growth" only counts when the title is not an
  engineering title ("Software Engineer, Growth" stays eng).
- eng: collections roles ("Area Collection Manager - Lending Collections (Frontend)") are not
  engineering; bare "security" is not used ("Cluster Head (Security & Investigation)").

``tests/test_classify.py`` holds 137 real titles from the spike fixtures; add the failing title
there first, then change a rule.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _Rule:
    family: str
    include: re.Pattern[str]
    exclude: re.Pattern[str] | None = None


def _any(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns))


_ENG_WORDS = r"\b(?:engineer\w*|developer|sde|programmer)\b"

RULES: tuple[_Rule, ...] = (
    _Rule(
        "design",
        _any(
            r"\bdesign(?:er|ers|ing)?\b",
            r"\bux\b",
            r"\bui\b",
            r"\bui/ux\b",
            r"\buser research",
            r"\billustrat\w*",
            r"\bcreative\b",
            r"\bgraphic\w*",
            r"\bvisual\b",
            r"\bmotion graphics?\b",
        ),
    ),
    _Rule(
        "data",
        _any(
            r"\bdata\b",
            r"\banalytics?\b",
            r"\banalysts?\b",
            r"\bmachine learning\b",
            r"\bml\b",
            r"\bmlops\b",
            r"\bai engineer",
            r"\bscientists?\b",
            r"\bdata science\b",
            r"\bdecision science\b",
            r"\bbi\b",
            r"\bbusiness intelligence\b",
        ),
        exclude=_any(r"\bsiem\b", r"\bsecops\b", r"\bsoc\b", r"\bsecurity analyst", r"\bthreat\b"),
    ),
    _Rule(
        "product",
        _any(
            r"\bproduct manag\w*",
            r"\bproduct owner\b",
            r"\bproduct lead\b",
            r"\bproduct head\b",
            r"\b(?:director|head|vp|vice president|avp)\b\W+(?:of\W+)?product\b",
            r"\bpm\b",
            r"\bprogram manager\b",
            r"\bapm\b",
        ),
    ),
    _Rule(
        "gtm",
        _any(
            r"\bmarketing\b",
            rf"^(?!.*{_ENG_WORDS}).*\bgrowth\b",
            r"\bsales\b",
            r"\baccount executive",
            r"\baccount manager\b",
            r"\bbusiness develop\w*",
            r"\bbd\b",
            r"\bbdr\b",
            r"\bsdr\b",
            r"\bseo\b",
            r"\bcontent\b",
            r"\bcopy(?:writer|writing)?\b",
            r"\bbrand(?:ing)?\b",
            r"\bpartnerships?\b",
            r"\bchannel\b",
            r"\bgtm\b",
            r"\bgo[- ]to[- ]market\b",
            r"\bcustomer success\b",
            r"\brelationship manager\b",
            r"\bpre-?sales\b",
        ),
        exclude=_any(r"\bemployer brand"),
    ),
    _Rule(
        "eng",
        _any(
            r"\bengineer\w*",
            r"\beng\b",
            r"\bdevelopers?\b",
            r"\bsde\b",
            r"\bsdet\b",
            r"\bdevops\b",
            r"\bdevsecops\b",
            r"\bsre\b",
            r"\bsite reliability\b",
            r"\bback[- ]?end\b",
            r"\bfront[- ]?end\b",
            r"\bfull[- ]?stack\b",
            r"\bandroid\b",
            r"\bios\b",
            r"\bqa\b",
            r"\btest\w*",
            r"\barchitect\w*",
            r"\bprogrammer\b",
            r"\btech lead\b",
            r"\bcyber ?security\b",
            r"\binfosec\b",
            r"\bappsec\b",
            r"\bsecops\b",
            r"\bsiem\b",
            r"\bsoc\b",
            r"\b(?:application|product|cloud|network|information|platform) security\b",
            r"\bsecurity (?:engineer|analyst|architect|operations)\b",
        ),
        exclude=_any(r"\bcollections?\b"),
    ),
)


def classify(title: str) -> str:
    """Return the family key (``design|data|product|gtm|eng|other``) for a job title."""
    text = " ".join((title or "").lower().split())
    for rule in RULES:
        if rule.include.search(text) and not (rule.exclude and rule.exclude.search(text)):
            return rule.family
    return "other"
