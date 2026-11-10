"""News tagger (PLAN §4.5 step 3). Every headline here is real: Inc42, Entrackr, YourStory and
Google News RSS, fetched in the Day-1 spike on 10 Nov 2026 (Google's " - Publisher" suffix stripped).
First match wins: layoffs > acquisition > funding > financials > other.
"""

from __future__ import annotations

import pytest

from rwradar_poller import config
from rwradar_poller.news.tagger import tag

LAYOFFS = [
    "Indian startup layoffs cross 4,500 in eight months, largely linked to business pressures",
    "Layoffs at Sam Altman's $2.5 billion startup, as company struggles to show how its key 'Eye technology' c",
    "Indian national Innovaccer CEO announces fresh AI-driven layoffs across startup",
    "A Year Of Pink Slips: Around 9,500 In Blues As Startups Cut Jobs",
    "A comprehensive list of 2025 tech layoffs",
    "Indian tech start-ups lay off over 4,000 employees in 2025, second highest after the US",
    "Globally, Over 1,600 Tech Employees Were Fired a Day on Average in 2023 So Far: Data",
    "CRED Layoff Buzz Meets Kunal Shah’s Profit Tweet, And Social Media Reads Between the Lines",
    "Indian Startup Layoff Tracker 2025",
    "Good news for IT employees: Layoffs finally reduce as Indian startups cut 60 per cent less jobs in Jan-March",
    "Over 5,600 Layoffs At Indian Startups: Unicorns, Tech Cos Bleed Jobs",
    "Indian Startups Restructure, Cut 18,000 Jobs In 2022: Will 2023 Bring Stability?",
    "Indian Startup Layoff Tracker: 37,260+ Employees Laid Off By 130+ Startups Since 2022",
    "Layoffs, shutdowns, funding crunch: The Great Indian Startup Party is over",
    "Tech layoffs: Health tech startup, Healthifyme fires 150 employees",
    "PayPal lays off around 600 employees in India amid global restructuring",
    "Startup layoffs: Practo fires 41 employees; engineering roles take a hit",
    "Byju’s to Dunzo: A list of startups that laid off their employees",
    "Startup layoffs: CRED-owned Happay fires over 150 employees in restructuring exercise",
    "PhysicsWallah cites AI efficiencies for job cuts; offline biz faces profit pressure, earmarks $20 Mn for M&A",
    "Indian IT Startup Shuts Down Overnight, 19 Employees Laid Off On Video Call",
    "Bengaluru IT startup lays off 40% staff in a day, netizens say: ‘Absurd salaries are real reason’",
    "14 Indian startups have sacked over 2,100 employees in the first three weeks of 2023",
    "Edtech startup PhysicsWallah lays off 120 employees after performance review",
    "Swiggy lays off 380 employees as startup winter deepens",
    "Healthtech startup PharmEasy lays off more employees",
    "Udaan Fires 350 Employees In Second Wave Of Layoffs This Year",
    "Indian edtech Unacademy cuts another 250 jobs",
    "Exclusive: Lightrock India-Backed MediBuddy Lays Off Around 200 Employees",
    "Healthtech startup MFine lays off over 500 employees amid funding crunch",
    "Tech upskilling startup Scaler lays off 150 employees",
    "Hobby startup FrontRow lays off 145 employees due to ‘market conditions’",
    "Exclusive: Tiger Global-Backed Healthtech Unicorn Innovaccer Lays Off 245 Employees",
    "BNPL Startup Simpl Lays Off 80 Employees After RBI Whiplash",
    "Indian healthcare startup PharmEasy struggles to raise funds, lays off employees",
    "Indian startups raised $1.2 Bn in January amid layoffs season: Entrackr Report",
    "Lightspeed-backed Teachmint becomes latest edtech startup to lay off employees",
    "Updated: InMobi Too Is Laying Off Employees; Is The Startup Froth Being Blown Away?",
]

ACQUISITION = [
    "Adobe just acquired this Indian AI startup less than a year after it launched",
    "Adobe acquires Indian AI startup Rilo",
    "Adobe acquires Indian market intelligence startup Rilo",
    "Adobe Acquires Peak XV-Backed AI Martech Startup Rilo",
    "Adobe picks up AI marketing startup Rilo in second India acquisition",
    "L'Oreal to acquire majority stake in Indian beauty startup Innovist",
    "BizDateUp Acquires 54.5% Stake in Cumma for ₹21 Cr to Unlock India’s Startup Infrastructure",
    "11 big startup acquisitions in India and what they mean for entrepreneurs",
    "India’s Marico Acquires Majority Stake in Plant-Based Protein Startup Cosmix for $25M",
    "Five Indian startup acquisitions that created billion-dollar value",
    "C5i Acquires Analytic Edge, Second Indian Startup Acquired by the AI Firm So Far",
    "Indian startups saw over 250 acquisitions in 2021: Entrackr report",
    "Legal AI giant Harvey acquires Hexus as competition heats up in legal tech",
    "Amazon acquires Indian retail startup Perpule",
    "Distressed Indian startup GoMechanic acquired by Lifelong Group-led consortium",
    "Amazon acquires Indian social commerce startup GlowRoad",
    "Stripe acquires fintech startup Recko in first Indian acquisition",
    "Twitter Acquires India-Based 'Missed Call' Startup ZipDial",
    "BlackRock-backed Minute Media acquires Indian AI startup that extracts sports highlights",
    "This Hyderabad-Based Startup Is Apple's First Acquisition in India",
    "Indian gaming unicorn Dream Sports sets up USD 250 million fund to invest and acquire startups",
    "Truecaller acquires payments startup Chillr",
    "Everstone acquires bootstrapped Indian startup Wingify for $200M",
    "15 notable Indian startup acquisitions by global companies",
    "Dr Oetker acquires startup Kuppies",
    "The redBus Acquisition: A Boost for India’s Startup Ecosystem",
    "Vahan.ai Secures Strategic Investment from LemmaTree, Acquires GoodWorker’s L.earn to Boost Blue-Collar Recruitment and Upskilling",
    "Domestic help provider Didi acquires home services startup TimeMyTask",
    "MakeMyTrip Acquires Majority Stake In Quick Ride To Enter Ride Pooling",
    "MakeMyTrip acquires majority stake in Quick Ride",
    "Meesho acquires majority stake in Kirana Club and RPLPL",
    "Meesho completes majority stake acquisition in Kirana Club and Retail Pulse Labs",
    "Meesho Limited to Buy Kirana Club for Rs 202.08 Crore",
    "Meesho completes Rs 186.71 crore Kirana Club acquisition",
    "How a $250 million acquisition collapsed into allegations of fraud and forged signatures",
    "Why InMobi’s acquisition of an American tech company is a big deal for India’s startup ecosystem",
    "Funding and acquisitions in Indian startups this week [Nov 02- Nov 07]",  # roundup: acquisition rule fires first
]

FUNDING = [
    "Startup Funding: India’s Series A Slump in Oct Was Mostly About Cheque Size",
    "Venomics AI Raises $2.7M in Pre-Seed Funding",
    "Google-backed Indian space startup raises $100 million in latest funding round",
    "Cosmoserve Space Raises $6 Million in Seed Funding Round",
    "Indian AI Fashion Discovery App Slayd Raises $156,400 in Pre-Seed Funding",
    "Funding Wrap: Gnani.ai, Bachatt, Kuku raise fresh capital",
    "Deeptech Startup Jaipur Robotics Raises €4.3 Mn, Eyes India Expansion",
    "Bio-tech startup Venomics AI raises $2.7 Mn in pre-seed round",
    "Indian startups raise $2.9 Bn in Q3 2026 as EV, AI drive funding",
    "Sarvam is reportedly in talks to raise $250 million in a new funding round that could value the company at around $1.5 billion",
    "Indian EV startup River raises $120M Series C to scale production, launch more models",
    "Anthropic's $65-billion round is larger than what all Indian startups raised in four years",
    "Sarvam becomes India’s newest AI unicorn with $234 million funding round led by HCLTech",
    "Indian startup funding plummets to $630 Mn in May despite Rapido's $240 Mn round",
    "Wealthtech startup Nexedge Capital raises $20 Mn in maiden funding round",
    "Indian startups raise $7.4 Bn in H1 2026 as CRED-Meta deal lifts funding",
    "India AI Startup Sarvam Raises Funds at $1.5 Billion Valuation",
    "Ema raises $77M as AI starts eating into enterprise software and services",
    "Healthcare AI startup Consint.AI raises Rs 22 Cr in Series A round",
    "Indian startup funding jumps to $2 Bn in February on Neysa’s mega round",
    "Indian startup funding drops 10% to $13 Bn in 2025, but IPO count hits record 18",
    "Indian vibe-coding startup Emergent triples valuation to $300M with $70M fundraise",
    "HR-tech startup All Things People raises seed funding round",
    "Froncort.AI Raises $2.3 Mn From Google.org To Expand AI-Based Disease Surveillance",
    "From GIVA To EloElo Group — Indian Startups Raised $255 Mn This Week",
    "Arka Fincap raises Rs 525 Cr from The Rise Funds of TPG",
    "IIFL Finance to raise Rs 6,414 Cr led by Blackstone",
    "Festive boost: D2C startups bag every third funding deal in October",
    "Spacetech startup Cosmoserve Space raises $6 Mn in seed round",
    "Daksham Growth Ventures raises Rs 125 Cr in first close of maiden consumer fund",
    "Specialty chemicals startup altM raises $10.3 Mn led by Rainmatter, Mela Ventures",
    "Enrission India Capital participates in Ottonomy’s Rs 40.6 Cr funding round",
    "Fintech infra startup OneStack raises Rs 12.5 Cr from Shepherd's Hill, others",
    "EloElo Group raises $80 Mn in Series C led by Hornbill Capital, NBCUniversal",
    "Peppermint Robotics raises Rs 100 Cr in Pre-Series B led by pi Ventures, Crane Venture Partners",
    "GIVA raises over $100 Mn in funding round led by Multiples PE",
    "Decoding: Spill Games’ Rs 100 Cr Series A round, valuation and cap table",
    "Unify Foodworks raises Rs 5 Cr in seed round",
    "Exclusive: Armatrix kicks off Rs 67 Cr seed round at 4.8X valuation premium",
    "Solgram raises over $1 Mn in pre-seed round led by DSG Consumer Partners, Saama Capital",
    "The Croffle Guys raises Rs 14 Cr from V3 Ventures, N.A.N Partners at Rs 100 Cr valuation",
    "Wealthtech startup PowerUp Money raises $10 Mn led by Flourish Ventures",
    "Zepto Pauses IPO Amid Valuation Concerns, To Raise ₹1,000 Cr Pre-IPO Round",
]

FINANCIALS = [
    "Matrimony Q2 Profit Soars 2.7X YoY To ₹20.7 Cr, Revenue up 17.6%",
    "ShareChat Parent Mohalla Tech’s FY26 Loss Widens 79% To ₹1,978 Cr, Revenue Inches Past ₹1,000 Cr Mark",
    "SEBI Clears MakeMyTrip’s India IPO",
    "Profits Are Just Half The Story This Earnings Season",
    "OYO Parent PRISM’s Profit Jumps 17% YoY To ₹353 Cr In Q1",
    "AvenuesAI Q2 Net Profit Rises 6% YoY To ₹72 Cr, Revenue Up 47%",
    "MDR And AI: Inside The Two Acronyms That Could Shape Razorpay’s ₹6,000 Cr IPO",
    "Anthropic targets upto $1.4T valuation with $70 to $78 IPO price range",
    "MakeMyTrip's India arm gets Sebi nod to float IPO",
    "Blue Tokai crosses Rs 500 Cr revenue in FY26; losses up 54%",
    "ShareChat parent crosses Rs 1,000 Cr revenue in FY26, posts Rs 672 Cr loss",
    "FamApp’s revenue touches Rs 25 Cr in FY26, profit nosedives 99%",
    "DriveU’s net profit doubles in FY26; NTV grows to Rs 131 Cr",
    "Sugar Cosmetics cuts losses by 41% in FY26, revenue dips 11%",
    "Mamaearth parent Honasa profit jumps 87% to Rs 73 Cr in Q2 FY27, revenue grows 36%",
    "Sleepy Owl’s revenue surges 86% to Rs 82 Cr in FY26; nears breakeven",
    "Moneyview's Q2 FY27 profit jumps 5.15X to Rs 201 Cr",
    "Tonbo Imaging turns profitable in Q2 FY27 with Rs 23.5 Cr; shares hit 20% upper circuit",
    "Shiprocket swings to profit in Q2 FY27; revenue rises 35% to Rs 674 Cr",
    "Decathlon India’s total income crosses Rs 4,500 Cr in FY26; EBITDA stands at Rs 424 Cr",
    "Exclusive: Scripbox to convert into public company ahead of IPO plans",
    "Razorpay receives SEBI approval for IPO",
    "Freshworks posts $245 Mn revenue in Q3 CY26; turns profitable with $18 Mn net profit",
    "Quick services startup Snabbit posts Rs 168 crore loss on Rs 12 crore revenue in FY26",
    "Skincare Startup CureSkin Cuts FY26 Loss to Rs 35 Cr",
    "Teachmint revenue jumps 2.8X to Rs 205 Cr in FY26",
    "Indian Startup IPO Tracker 2026",
    "IPO-bound Kuku’s FY26 revenue jumps six-fold to Rs 1,484 crore; turns profitable",
    "Y Combinator-backed Orange Health posts Rs 139 Cr revenue in FY26; loss nears Rs 100 Cr",
    "Zepto doubles revenue in FY26, losses widen to Rs 5,905 Cr",
    "Prosus India FY26 revenue rises 13% to $781 million as PayU turns EBITDA positive",
    "Zetwerk opens its IPO this week seeking a $2.8 billion valuation",
    "Temasek-backed Indian startup Licious plans IPO in 2026, eyes $2 billion valuation, says source",
    "India’s EV startup Ather cuts IPO size to $308M, seeking $1.4B post-money valuation",
    "Furlenco Eyes ₹1,200 Cr IPO At ₹7,000 Cr Valuation: Report",
    "Truist raises Zeta Global stock price target on strong growth",  # "raises" is not funding here
    "Zeta Raises Guide to $1.855B; CFO Credits Athena AI Adoption",
    "Zeta Global Holdings earnings beat by $0.10, revenue topped estimates",
    "3 Indian Founder Led Stocks With Earnings Growth Up To 36%",
    "ZETA Maintained by RBC Capital -- Price Target Raised to $41.00",  # live run: "Raised to $" is not funding
    "(ZETA) Zeta Global Now Expects 2026 EPS Range $0.22 - $0.24, vs. FactSet Est of $0.11",
]

OTHER = [
    "Three Workers Die After Inhaling Toxic Gases At Tata’s TN iPhone Factory",
    "Why Gramiyaa Had To Think Like A Supermarket To Win On Quick Commerce",
    "Sarvam Ropes In Google Cloud India MD Sashikumar Sreedharan As President & CBO",
    "InMobi Secures Naming Rights For Bengaluru’s Ibbaluru Metro Station For ₹65 Cr",
    "OpenAI Deploys Control Room With 35-Second Kill Switch Amid Security Concerns",
    "Beauty Brands Go Quick Commerce-First",
    "Decoding BlackBuck’s Core Trucking Model And Its New Engines",
    "Pronto’s Second Shift",
    "New-Age Tech Stocks Extend Rally, CarTrade Leads With 23.3% Gain",
    "ED Searches CoinDCX & Delta Exchange Over Alleged Illegal Cross-Border Transfers",
    "MobiKwik To Begin NBFC Operations Within 6 Months Post RBI Clearance",
    "Brokers In October: Angel One Climbs To The Second Spot With 2.4 Lakh New User Additions",
    "Delhi HC Upholds BharatPe’s Veto Rights In Unity SFB Shareholding Dispute",
    "How Bout India built a travel company without selling packages",
    "Why storytelling can be a startup's strongest competitive moat",
    "Beyond the cloud: Why businesses are turning to on-device AI",
    "With Jensen Huang under fire, Nvidia looks at sucession plans",
    "SplashBI opens GCC in Hyderabad, to invest over $100M",
    "National Startup Awards 6.0 opens applications; winners to receive Rs 25 lakh prize in 20 categories",
    "Startup news and updates: daily roundup (November 10, 2026)",
    "Fireside Ventures co-founder Vinay Singh to exit after nearly a decade",
    "Sashikumar Sreedharan joins Sarvam as President and Chief Business Officer",
    "Investing in US stocks through Groww: A Complete Guide",
    "Rubrik expands Google Cloud data protection to BigQuery",
    "Rubrik at Cloud Resilience Summit 2026: AI raises the bar on recovery",  # "raises" is not funding here
    "Lenskart, Meesho add $394 million to SoftBank's portfolio value in September quarter",
    "JioStar’s Saptarshi Mandal joins Paytm as General Manager-West",
    "KeyBanc reiterates Overweight on Zeta Global stock, $38 target",
    "Needham reiterates Buy on Zeta Global stock, cites strong demand",  # "Buy" rating is not "buys"
    "Form 8K Eagle Point Cred For: 10 November",
    "How Meesho's lending business foray may pan out",
    "Rubrik can back up on-prem unstructured data direct to its own cloud",
    "Hyderabad Police warn against fake Paytm Diwali gift messages",
    "Three investors offload 1.84% stake in Groww for ₹2,457 crore in bulk deals",
    "China touts tech, AI cred at world Web Summit",
    "Michael Douglas and Catherine Zeta-Jones’ kids are all grown up in rare outing with dad",
    "India’s MoEngage bets that the future of marketing is millions of AI agents",
    "Death of an Indian tech worker",
    "B. Riley Adjusts PT on Zeta Global Holdings to $39 From $38, Maintains Buy Rating",
]

CASES = (
    [(h, "layoffs") for h in LAYOFFS]
    + [(h, "acquisition") for h in ACQUISITION]
    + [(h, "funding") for h in FUNDING]
    + [(h, "financials") for h in FINANCIALS]
    + [(h, "other") for h in OTHER]
)


@pytest.mark.parametrize("headline,expected", CASES)
def test_tag(headline: str, expected: str) -> None:
    assert tag(headline) == expected


def test_at_least_30_real_headlines_per_tag() -> None:
    for group in (LAYOFFS, ACQUISITION, FUNDING, FINANCIALS, OTHER):
        assert len(group) >= 30
    assert {t for _, t in CASES} == set(config.NEWS_TAGS)


@pytest.mark.parametrize(
    "headline,expected",
    [
        # Precedence: first rule wins.
        ("Startup X lays off 100 after failing to raise funding", "layoffs"),
        ("Startup X acquires Y after raising $10 Mn Series A", "acquisition"),
        ("Startup X raises $10 Mn; revenue doubles in FY26", "funding"),
        # Word boundaries.
        ("Arrival of the new ARR-ivals", "financials"),  # "ARR" whole word
        ("Startup arrives in Pune", "other"),  # "arrives" is not "arr"
        ("Glossary of startup terms", "other"),  # not "loss"
        ("Groww raises Rs 300 Cr", "funding"),
    ],
)
def test_tag_rules(headline: str, expected: str) -> None:
    assert tag(headline) == expected
