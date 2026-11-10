"""Headline -> company matcher and blocklist (PLAN §4.5 step 4). Headlines marked (real) are from
the Day-1 spike feeds; the rest are realistic constructions for rules the feeds did not exercise."""

from __future__ import annotations

import pytest

from rwradar_poller import config
from rwradar_poller.models import Company
from rwradar_poller.news.matcher import Blocklist, BlocklistError, Matcher
from rwradar_poller.news.tagger import tag


def _c(cid: str, name: str, *aliases: str) -> Company:
    return Company(cid, name, tuple(aliases), "Tech", "https://example.com", "lever", cid)


COMPANIES = [
    _c("groww", "Groww", "Nextbillion Technology"),
    _c("cred", "CRED", "Dreamplug Technologies"),
    _c("zeta", "Zeta", "Zeta Suite"),
    _c("meesho", "Meesho"),
    _c("sarvam", "Sarvam AI", "Sarvam"),
    _c("hcltech", "HCLTech", "HCL Technologies"),
    _c("accel", "Accel", "Accel Partners"),
    _c("tiger-global", "Tiger Global"),
    _c("swiggy", "Swiggy"),
    _c("zepto", "Zepto"),
    _c("makemytrip", "MakeMyTrip"),
    _c("ottonomy", "Ottonomy"),
    _c("enrission", "Enrission India Capital"),
    _c("swift-tech", "Swift Technologies"),
]

BLOCKLIST = Blocklist.from_data(
    {
        "version": 1,
        "rules": [
            {"companyId": "zeta", "phrase": "Zeta Global"},
            {"companyId": "zeta", "phrase": "Zeta-Jones"},
            {"companyId": "cred", "caseSensitive": True},
            {"companyId": "groww", "newsHash": "a" * 40},
            {"companyId": "*", "newsHash": "b" * 40},
        ],
    }
)


@pytest.fixture
def matcher() -> Matcher:
    return Matcher(COMPANIES, BLOCKLIST)


def m(matcher: Matcher, headline: str, news_hash: str | None = None) -> list[str]:
    return matcher.match(headline, tag(headline), news_hash)


@pytest.mark.parametrize(
    "headline,expected",
    [
        # Name and aliases, case-insensitive, exact phrase.
        ("Sashikumar Sreedharan joins Sarvam as President and Chief Business Officer", ["sarvam"]),  # (real) alias
        ("Sarvam AI Appoints Ex-Google Cloud India MD Sashikumar Sreedharan as President and CBO", ["sarvam"]),  # (real)
        ("Dreamplug Technologies posts Rs 2,000 Cr revenue in FY26", ["cred"]),  # alias
        ("meesho completes rs 186.71 crore kirana club acquisition", ["meesho"]),  # lowercase headline
        ("Sarvam   AI hires a CTO", ["sarvam"]),  # whitespace inside a phrase
        ("Nextbillion  Technology files DRHP", ["groww"]),
        # Word boundaries.
        ("Startup layoffs: CRED-owned Happay fires over 150 employees in restructuring exercise", ["cred"]),  # (real)
        ("Zepto's IPO filing reveals fast growth, bigger losses", ["zepto"]),  # possessive
        ("Growwth hacking tips for founders", []),  # not "Groww"
        ("Meeshonomics: a newsletter", []),
        ("Taylor Swift tour boosts hotel bookings", []),  # "Swift" alone is not an alias
        ("Swift Technologies opens Pune office", ["swift-tech"]),
        # Several companies in a non-funding headline: all match.
        ("Swiggy and Zepto battle for quick commerce share", ["swiggy", "zepto"]),
        ("MakeMyTrip Acquires Majority Stake In Quick Ride To Enter Ride Pooling", ["makemytrip"]),  # (real)
        ("India's HCLTech to buy 10.5% stake in Sarvam AI, valuing startup at $1.5 billion", ["sarvam", "hcltech"]),
    ],
)
def test_match(matcher: Matcher, headline: str, expected: list[str]) -> None:
    assert sorted(m(matcher, headline)) == sorted(expected)


@pytest.mark.parametrize(
    "headline,expected",
    [
        # Funding: the company must come before the funding verb.
        ("Sarvam becomes India’s newest AI unicorn with $234 million funding round led by HCLTech", ["sarvam"]),  # (real)
        ("Zepto raises $450 Mn led by Accel and Tiger Global", ["zepto"]),
        ("Indian startups raise $7.4 Bn in H1 2026 as CRED-Meta deal lifts funding", []),  # (real) CRED after the verb
        ("Funding Wrap: Sarvam, Rusk Media, SolarSquare raise fresh capital", ["sarvam"]),  # (real)
        # "X invests in Y" counts as Y raising money, not X.
        ("Accel invests $10 Mn in Zepto", ["zepto"]),
        ("Swiggy invests in Zepto's Series B round", ["zepto"]),
        ("Accel Partners invested in Groww's seed round", ["groww"]),
        ("Enrission India Capital participates in Ottonomy’s Rs 40.6 Cr funding round", ["ottonomy"]),  # (real)
        ("Tiger Global-backed Groww raises $100 Mn in Series E", ["groww"]),
        ("HCLTech bets big on Sarvam with $50 Mn funding", ["sarvam"]),
    ],
)
def test_funding_attribution(matcher: Matcher, headline: str, expected: list[str]) -> None:
    assert tag(headline) == "funding"
    assert m(matcher, headline) == expected


def test_blocklist_phrase(matcher: Matcher) -> None:
    # (real) different organizations that share a name
    assert m(matcher, "Truist raises Zeta Global stock price target on strong growth") == []
    assert m(matcher, "Michael Douglas and Catherine Zeta-Jones’ kids are all grown up in rare outing with dad") == []
    # A match outside the blocked phrase still counts.
    assert m(matcher, "Zeta launches card platform as Zeta Global stock slips") == ["zeta"]
    # Without the blocklist the same headline would match.
    assert Matcher(COMPANIES).match("Truist raises Zeta Global stock price target", "financials") == ["zeta"]


def test_blocklist_case_sensitive(matcher: Matcher) -> None:
    assert m(matcher, "China touts tech, AI cred at world Web Summit") == []  # (real)
    assert m(matcher, "Form 8K Eagle Point Cred For: 10 November") == []  # (real)
    assert m(matcher, "CRED Layoff Buzz Meets Kunal Shah’s Profit Tweet") == ["cred"]  # (real)
    # Aliases follow the same rule.
    assert m(matcher, "dreamplug technologies posts revenue") == []


def test_blocklist_news_hash(matcher: Matcher) -> None:
    headline = "Swiggy and Groww team up"
    assert sorted(m(matcher, headline)) == ["groww", "swiggy"]
    assert m(matcher, headline, news_hash="a" * 40) == ["swiggy"]  # groww blocked for that item
    assert m(matcher, headline, news_hash="b" * 40) == []  # "*" drops the item


def test_empty_headline(matcher: Matcher) -> None:
    assert m(matcher, "") == []


@pytest.mark.parametrize(
    "rules",
    [
        [{"companyId": "zeta"}],  # no kind
        [{"companyId": "zeta", "phrase": "Zeta Global", "newsHash": "a" * 40}],  # two kinds
        [{"companyId": "*", "phrase": "x"}],  # "*" only with newsHash
        [{"companyId": "zeta", "newsHash": "XYZ"}],  # bad hash
        [{"companyId": "zeta", "caseSensitive": False}],
        [{"phrase": "x"}],  # no companyId
    ],
)
def test_blocklist_validation(rules: list[dict]) -> None:
    with pytest.raises(BlocklistError):
        Blocklist.from_data({"version": 1, "rules": rules})


def test_repo_blocklist_file_is_valid() -> None:
    bl = Blocklist.load(config.BLOCKLIST_PATH)
    assert config.BLOCKLIST_PATH.exists()
    assert "zeta" in bl.phrases


# --- aliasesOnly (added after the first live news run, 2026-11-10) -----------------------------

def _co(cid, name, aliases):
    from rwradar_poller.models import Company
    return Company(cid, name, tuple(aliases), "x", "https://x", "lever", cid)


def test_aliases_only_ignores_bare_name():
    from rwradar_poller.news.matcher import Blocklist, Matcher
    bl = Blocklist.from_data({"rules": [{"companyId": "toast", "aliasesOnly": True}]})
    m = Matcher([_co("toast", "Toast", ["Toast Inc", "Toasttab"])], bl)
    assert m.match("Green Goddess Avocado and Smashed White Bean Toast", "other") == []
    assert m.match("Toast Inc reports Q3 revenue growth", "financials") == ["toast"]
    assert m.query_names(_co("toast", "Toast", ["Toast Inc", "Toasttab"])) == ["Toast Inc", "Toasttab"]


def test_query_names_default_is_name_only():
    from rwradar_poller.news.matcher import Matcher
    c = _co("groww", "Groww", ["Nextbillion Technology"])
    assert Matcher([c]).query_names(c) == ["Groww"]
