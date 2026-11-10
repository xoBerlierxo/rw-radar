"""Role-family classifier (PLAN §4.3, D9). Titles are real, from the Day-1 spike fixtures."""

from __future__ import annotations

import pytest

from rwradar_poller import config
from rwradar_poller.ats import ashby, greenhouse, lever
from rwradar_poller.classify import classify

from .conftest import load_json

REAL_TITLES: list[tuple[str, str]] = [
    # --- design
    ("Product Designer", "design"),  # order: design before product
    ("Creative Illustrator", "design"),
    ("Creative Manager", "design"),
    ("Instructional Designer- ValMo Training", "design"),
    # --- data
    ("Data Scientist - Evaluations, Chanakya", "data"),
    ("Embedded Data Scientist, Chanakya", "data"),
    ("ML Ops Engineer, Chanakya", "data"),  # order: data before eng
    ("ML Researcher, Foundational Models", "data"),
    ("ML Engineer (Training Infra), Foundational Models", "data"),
    ("Data Scientist III", "data"),
    ("Data Scientist III (Team- Valmo)", "data"),
    ("Director Data Science", "data"),
    ("AM/M - Risk Analytics - User Lending", "data"),
    ("AM/ Manager - Risk & Decision Science", "data"),
    ("Analytics Lead - UPI Product | Experience : 7-9 yrs", "data"),
    ("Analytics Lead- User Growth I Exp- 8- 10 Years", "data"),  # data before gtm ("growth")
    ("fraud analyst", "data"),
    ("Senior AI Engineer", "data"),
    ("Manager Data Reliability Engineering", "data"),
    ("Senior Data Base Engineer", "data"),
    # --- product
    ("Product Manager (Models)", "product"),
    ("Product Manager On-Device & Edge AI", "product"),
    ("Product Manager, Monetization & Retention", "product"),
    ("Product Manager – Media & Entertainment, Sarvam Studio", "product"),
    ("Product Manager II", "product"),
    ("Group Product Manager", "product"),
    ("Director - Product", "product"),
    ("Director, Product Management, Security", "product"),
    ("Staff Program Manager, NPI and Product Operations", "product"),
    ("GSI Services Program Manager", "product"),
    # --- gtm (Marketing/Sales)
    ("Product Marketing Manager", "gtm"),
    ("Marketing Operations Manager", "gtm"),
    ("Senior Manager, Growth Marketing", "gtm"),
    ("GTM & Strategy, Model API", "gtm"),
    ("Business Development Representative", "gtm"),
    ("Enterprise Account Executive - SF/Bay Area", "gtm"),
    ("Enterprise Account Executive - NYC", "gtm"),
    ("Senior Sales Engineer", "gtm"),  # order: gtm before eng
    ("Sales Engineer", "gtm"),
    ("Senior Partner Sales Engineer", "gtm"),
    ("Senior Sales Engineer, Dell", "gtm"),
    ("Bay Area Sales - Future Opportunities", "gtm"),
    ("Channel Business Manager - Softcat", "gtm"),
    ("Customer Success Manager", "gtm"),
    ("Partner Sales Manager, SHI", "gtm"),
    ("Sales Development Representative - Future Opportunity", "gtm"),
    ("Senior Account Executive", "gtm"),
    ("Associate - Content (Digest)", "gtm"),
    ("Finance Content Creator", "gtm"),
    ("Relationship Manager", "gtm"),
    ("Account Executive", "gtm"),
    ("Account Executive, M365 Product Specialist", "gtm"),
    ("Account Executive, SaaS Product Line Specialist (East)", "gtm"),
    ("Channel Development Manager - CDW (East Coast)", "gtm"),
    ("Customer Success Manager - Growth and Retention", "gtm"),
    ("business development & partnerships", "gtm"),
    ("business development & strategic partnerships - d2c", "gtm"),
    ("credit card bill payments growth", "gtm"),
    ("issuance growth lead", "gtm"),
    ("long form content writer/editor", "gtm"),
    ("Director – Sales, Meesho AI Services (MAS) | North India", "gtm"),
    ("Lead Copy", "gtm"),
    ("Manager - Branding", "gtm"),
    ("Manager – GTM & Sales Strategy, Meesho AI Services (MAS)", "gtm"),
    ("Account Executive/ Director - AI Agentic Enterprise Sales", "gtm"),
    ("Area Sales Manager - Manager - Bihar - Lending (LRM)", "gtm"),
    ("Associate - User Growth (Field Marketing)", "gtm"),
    ("Director - Solutions Sales (Dubai)", "gtm"),
    ("Head of Commercial/ Sales, Paytm Europe", "gtm"),
    ("Sales/ BD - Team Lead - Paytm (Pi Commerce)", "gtm"),
    ("Vice President - Business Development", "gtm"),
    # --- eng
    ("AI Native Builder/Architect", "eng"),
    ("Principal Software Engineer - Agent & App Platform", "eng"),
    ("Staff Software Engineer - Infrastructure", "eng"),
    ("Embedded Infrastructure Engineer, Chanakya", "eng"),
    ("Strategic Deployment Engineer, Chanakya", "eng"),
    ("Frontend Engineer, Chanakya", "eng"),
    ("Solution Architect", "eng"),
    ("Staff Engineer, Product Infrastructure", "eng"),
    ("Staff Engineer, API Platform", "eng"),
    ("Infrastructure SRE - HPC", "eng"),
    ("Platform Engineer - AI Infrastructure", "eng"),
    ("Performance Engineer, Kernels", "eng"),
    ("DevOps Engineer", "eng"),
    ("Agent Engineer", "eng"),
    ("Cloud Operations Support Engineer", "eng"),
    ("Senior Staff Engineer, Product Security", "eng"),
    ("Senior Staff Engineer, QA", "eng"),
    ("Senior Staff Software Engineer (DataLake)", "eng"),  # "DataLake" is not "data"
    ("Senior Staff Software Engineer, Distributed Systems", "eng"),
    ("Application Security Engineer", "eng"),
    ("Database Reliability Engineer/Database Engineer (Rubrik Security Cloud Platform)", "eng"),
    ("ENG Project/ Program - Intern", "eng"),
    ("Global Solutions Architect", "eng"),
    ("cloud security engineer", "eng"),
    ("threat detection engineer", "eng"),
    ("Engineering Manager -Backend", "eng"),
    ("Engineering Manager- Platform", "eng"),
    ("Staff AI Platform Engineer - Inference & Agentic Systems", "eng"),
    ("Analyst II - SIEM/SecOps", "eng"),  # security analyst: not data
    ("DevSecOps Engineer II", "eng"),
    ("Director - Solution Engineering", "eng"),
    ("Lead Site Reliability Engineer", "eng"),
    ("Product Security Engineer II", "eng"),
    ("Technical Support Engineer II", "eng"),
    # --- other
    ("Engagement Manager, Chanakya", "other"),
    ("Deployment Strategist", "other"),
    ("Technical Partner Enablement Manager", "other"),
    ("Field CTO", "other"),
    ("Join Druva's Talent Community", "other"),
    ("Learning and Development Director", "other"),
    ("Senior NetSuite Administrator", "other"),
    ("Senior Professional Services Consultant", "other"),
    ("Talent Acquisition Operations Coordinator", "other"),
    ("Assistant Manager - Internal Audit", "other"),
    ("Manager - Compliance (PMS)", "other"),  # "PMS" is not "pm"
    ("Portfolio Specialist - Wealth", "other"),
    ("Procurement Specialist", "other"),
    ("Product Research Specialist (W from Groww)", "other"),
    ("accounts payable manager", "other"),
    ("area collections manager chennai- flows", "other"),
    ("regional collection manager bangalore - flows", "other"),
    ("lead – on deck payments", "other"),
    ("Cluster Head ( Security & Investigation)", "other"),  # physical security, not eng
    ("Cluster Head- Last Mile", "other"),
    ("Deputy Manager - Revenue Intelligence and Governance", "other"),
    ("Manager – HRBP & ER", "other"),
    ("Area Collection Manager - Manager - Lending Collections (Frontend)", "other"),  # not eng
    ("Associate - Motor Insurance", "other"),
    ("Head of Financial Crime & MLRO Paytm Europe", "other"),
    ("Office Administrator and Executive Assistant", "other"),
    ("Supply chain, Logistics and Operations – Indonesia", "other"),
    ("Manager - Employer Branding & Communications", "other"),  # HR, not marketing
    ("Manager - Talent Management", "other"),
    ("Specialist Total Rewards", "other"),
    ("Executive - IT Support", "other"),
    ("Americas Field Enablement Director", "other"),
]

SYNTHETIC_TITLES: list[tuple[str, str]] = [
    # Order rules from PLAN §4.3 and common Indian startup titles.
    ("Data Engineer", "data"),
    ("UI/UX Designer", "design"),
    ("UX Researcher", "design"),
    ("SDE-2, Payments", "eng"),
    ("Software Engineer, Growth", "eng"),  # growth guard
    ("Android Developer", "eng"),
    ("iOS Engineer", "eng"),
    ("QA Automation Engineer", "eng"),
    ("Associate Product Manager", "product"),
    ("SEO Specialist", "gtm"),
    ("Business Analyst", "data"),
    ("BI Developer", "data"),
    ("Chief of Staff", "other"),
    ("", "other"),
]


@pytest.mark.parametrize("title,family", REAL_TITLES + SYNTHETIC_TITLES)
def test_classify(title: str, family: str) -> None:
    assert classify(title) == family


def test_enough_real_titles() -> None:
    assert len(REAL_TITLES) >= 50
    assert {f for _, f in REAL_TITLES} == set(config.FAMILY_KEYS)


def test_every_fixture_title_classifies_to_a_known_family() -> None:
    jobs = []
    for token in ("groww", "druva", "rubrik"):
        jobs += greenhouse.normalize(load_json(f"greenhouse_{token}.json"), load_json(f"greenhouse_{token}_departments.json"))
    for token in ("cred", "zeta", "paytm", "meesho"):
        jobs += lever.normalize(load_json(f"lever_{token}.json"))
    for token in ("sarvam", "atlan"):
        jobs += ashby.normalize(load_json(f"ashby_{token}.json"))
    assert len(jobs) > 200
    assert all(j.family in config.FAMILY_KEYS for j in jobs)
    # Spot-check that the test titles above really come from the fixtures.
    fixture_titles = {j.title for j in jobs}
    real = [t for t, _ in REAL_TITLES]
    assert sum(t in fixture_titles for t in real) >= 0.9 * len(real)
