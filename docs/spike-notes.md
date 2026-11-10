# Day-1 spike notes (poller)

Date: 10 Nov 2026. Every request used User-Agent `RWRadarPoller/0.1` and at most 1 request/second per
host. The trimmed responses are saved in `poller/tests/fixtures/`. Each fixture has at most 30
jobs, and long text fields (JD HTML, RSS bodies) are cut to about 160 chars with the JSON/XML
structure left intact.

## 1. ATS endpoints

| ATS | Board | HTTP | Jobs | Size | Fixture |
| --- | --- | --- | --- | --- | --- |
| Greenhouse | `groww` | 200 | 9 | 6 KB | `greenhouse_groww.json` (+ `_departments`, `_content`) |
| Greenhouse | `druva` | 200 | 27 | 17 KB | `greenhouse_druva.json` (+ `_departments`) |
| Greenhouse | `rubrik` | 200 | 149 | 122 KB | `greenhouse_rubrik.json` (+ `_departments`) |
| Greenhouse | `postman`, `phonepe`, `browserstack`, `sprinklr` | 404 | n/a | n/a | not on Greenhouse under these tokens |
| Lever | `cred` | 200 | 14 | 116 KB | `lever_cred.json` |
| Lever | `meesho` | 200 | 50 | 867 KB | `lever_meesho.json` |
| Lever | `zeta` | 200 | 28 | 959 KB | `lever_zeta.json` |
| Lever | `paytm` | 200 | 201 | 3.1 MB | `lever_paytm.json` |
| Ashby | `sarvam` | 200 | 47 | 499 KB | `ashby_sarvam.json` |
| Ashby | `atlan` | 200 | 7 | 124 KB | `ashby_atlan.json` |
| Ashby | `rippling`, `plivo` | 404 | n/a | n/a | not on Ashby under these names |

All three ATSs work for Indian companies, so none is dropped. Registry entries must be checked
board by board (`validate-registry --check-endpoints`): 6 of the 15 guessed tokens were 404s.

## 2. Field mappings (PLAN §4.2), checked against real responses

**Greenhouse** (`GET /v1/boards/{token}/jobs`)
- **Correction: `departments` is absent without `?content=true`.** With `content=true` every job also
  carries its full HTML body: rubrik is 2.0 MB instead of 122 KB, and druva 263 KB instead of 17 KB.
- **Chosen approach:** `GET /jobs` (the authoritative list) plus `GET /v1/boards/{token}/departments`
  (departments with their jobs embedded, no bodies: 24–122 KB). The departments endpoint **omits
  jobs that have no department** (rubrik: 148 of 149), so it cannot replace `/jobs`. Both requests
  must succeed, or the company counts as a failed fetch. Otherwise a missing dept map would change
  every content hash. The adapter also accepts `content=true` payloads (tested).
- `first_published` was present on every job on all 3 boards. It has a UTC offset
  (`2026-09-14T03:49:28-04:00`) and is converted to UTC. `updated_at` is the fallback.
- `location.name` is free text (`"Bengaluru-VTP, India"`, `"Remote"`, `"Remote, UK"`). Remote = the
  text contains "remote" (rubrik: 9 of 30 in the fixture).
- `absolute_url` often points at the company's own careers site (rubrik, druva), not greenhouse.io.
  groww's board is EU-hosted (`job-boards.eu.greenhouse.io`), but the API host is the same.
- `id` is an integer, so the job id is `greenhouse_<int>`.
- Department names can have trailing spaces (`"Private Wealth "`). They are trimmed.

**Lever** (`GET /v0/postings/{company}?mode=json`)
- The response is a **top-level JSON array** (not `{jobs: []}`). No pagination is needed at these
  sizes (paytm returned all 201).
- `workplaceType` is confirmed. Values seen: `onsite`, `remote`, `hybrid`. Hybrid counts as **not** remote.
- `categories.department` and `categories.team` were present on every posting. `categories.location`
  is sometimes lowercase (`"hyderabad"`) and is stored as-is.
- `createdAt` is an int in epoch ms. `hostedUrl` is the posting page. `id` is a uuid.
- Responses are large because every posting carries description HTML, and no parameter drops it.
  Paytm is 3.1 MB per poll. That is acceptable hourly, but these are the heaviest boards.

**Ashby** (`GET /posting-api/job-board/{name}`)
- The response is `{"apiVersion": "1", "jobs": [...]}`. Unknown boards return 404 with a 9-byte body.
- **Correction:** `isRemote` can be `null` (atlan), and `workplaceType` is PascalCase (`OnSite`,
  `Remote`) or `null`. Remote = `isRemote is True` or `workplaceType == "Remote"`, compared
  case-insensitively.
- `publishedAt` is ISO with offset (`2026-04-17T11:46:39.214+00:00`). `jobUrl` is the posting page. `id` is a uuid.
- `isListed` exists (always true in the spike), and unlisted postings are skipped.
  `secondaryLocations` exists but is not used.
- `department` and `team` are both present. `department` is used, with `team` as the fallback.

**Classifier:** 137 real fixture titles are in `tests/test_classify.py`. The PLAN §4.3 order is kept.
The rule fixes come from real titles: matching uses word boundaries ("Database" is not data, "PMS"
is not pm, "DataLake" is not data), bare "security" is dropped ("Cluster Head (Security &
Investigation)"), security analysts go to eng ("Analyst II - SIEM/SecOps"), "Employer Branding" is
other, collections roles are not eng ("…Lending Collections (Frontend)"), and "growth" in an
engineering title stays eng. Additions: creative/illustrator → design; channel, customer success,
relationship manager and GTM → gtm; "Director - Product" → product.

## 3. News feeds (PLAN §4.5)

| Source | URL | HTTP | Items | pubDate | Fixture |
| --- | --- | --- | --- | --- | --- |
| Inc42 | `https://inc42.com/feed/` | 200 | 24 | yes (+0000) | `rss_inc42.xml` |
| Entrackr | `https://entrackr.com/feed` | **404** | n/a | n/a | n/a |
| Entrackr | `https://entrackr.com/rss` (from the homepage's `<link rel=alternate>`) | 200 | 50 | yes (+0530) | `rss_entrackr.xml` |
| YourStory | `https://yourstory.com/feed` | 200 | 20 | yes (GMT) | `rss_yourstory.xml` |
| Google News | `news.google.com/rss/search?q=("Groww" OR … 10 names) when:7d&hl=en-IN&gl=IN&ceid=IN:en` | 200 | 100 | yes | `rss_googlenews.xml` |

All 4 sources work (at least 2 were needed). Google News details:
- One query with 10 companies OR'd returns 100 items. `when:7d` works inside the query and keeps
  items recent.
- Titles end with `" - <Publisher>"`, and the publisher is in `<source url=…>`. The poller strips the
  suffix and uses the publisher as `source`.
- Links are `news.google.com/rss/articles/…?oc=5` redirect URLs. `oc` is dropped during
  normalization, and the rest is stored as-is (it opens the article in a browser).
- The same story appears from many publishers (one Sarvam hire produced 10 items). Each item has its
  own URL, so each becomes its own `news/{hash}`. There is no cross-source dedupe in the MVP.

Real headlines were gathered for the tagger tests: the four feeds plus 7 Google News topic queries,
giving 30+ per tag (`tests/test_tagger.py`). Tagger corrections from those headlines:
- A bare "raises" is **not** funding ("Truist raises Zeta Global stock price target", "AI raises
  the bar", "Price Target Raised to $41.00"). It needs money or a round word right after it and must
  not be "raised to".
- "to buy" and bare "acquire" count as acquisition, but "Buy rating" does not.
- "laid off", "sacks", "pink slips" and "cuts N jobs" count as layoffs.
- `arr` and `ipo` match as whole words only. Financials also gets earnings, EBITDA, EPS, guidance
  and price target.

## 4. Matching: wrong-company risk found in the spike

A live dry-run on 7 sample companies matched 75 of 194 items, and the noise was name collisions:
- **Zeta**: Zeta Global (NYSE:ZETA, dozens of items a day), Catherine Zeta-Jones, the Zeta Beta Tau
  fraternity, Zeta Network Group, the ZETA DIVISION esports team.
- **CRED**: "AI cred", "Eagle Point Cred" (US fund), "ASX:CRED".
- **Atlan**: "Marine Atlan" (a film director).

`registry/news_blocklist.json` is seeded with rules for these: phrase rules plus `caseSensitive` for
zeta and cred. The format is in the docstring of `poller/rwradar_poller/news/matcher.py`. The
registry ids used there (`zeta`, `cred`, `atlan`) must match `companies.json`, and
`validate-registry` warns when they don't. **Registry advice:** prefer specific aliases, and expect
the Day-9 review to add more blocklist rules for one-word names.

Funding attribution: in a funding headline, the company must come before the raise verb, and
investors are excluded ("X invests in Y" → Y, "Tiger Global-backed Groww raises" → Groww,
"…funding round led by HCLTech" → not HCLTech).

## 5. Google News "every 2nd run"

Decided with a **stored timestamp**, not UTC-hour parity: `meta/newsIndex.lastGoogleNewsAt` (a
poller-only field next to `hashes`). Google runs when that time is unset or at least 105 minutes
old, and the time only advances when a Google query succeeds. On the `13,43` cron this means every
2nd run (about every 2 h). A late or skipped GitHub cron run doesn't break the pattern, and it adds
no reads because the doc is read anyway. `--google-news always|never` overrides it, for manual runs.

## 6. Size and quota notes

- `meta/newsIndex` keeps items no older than 30 days, and older feed items are ignored entirely.
  Expected size is about 5–9k hashes (about 0.4–0.7 MB). A hard cap of 12,000 entries keeps it under
  Firestore's 1 MiB doc limit.
- `jobIndex` costs about 120 bytes per job. A 500-job board is about 60 KB, fine for a company doc.
  Closed entries are pruned 30 days after they were last seen.
- Firestore batches are split at 450 writes, with the company doc in the last batch.
- Spark quota numbers (PLAN §5.1) are the owner's Firebase-console task and were not part of this spike.
