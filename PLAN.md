# PLAN: RW Radar MVP build

Build plan for [SPEC.md](SPEC.md) v0.3 · Plan v1.0 (decisions locked) · 10 Nov 2026 · Owner: Somshekhar Pandey

How to use this file:
- Section 1 records the decisions taken during plan review, including where the build differs from the spec.
- Sections 2–9 explain how each part is built.
- Section 10 is the day-by-day checklist. Each day ends with a **Done when** check.
- Section 11 maps every acceptance criterion in the spec to how it is verified.

---

## 1. Decisions locked in (10 Nov 2026)

All of these were reviewed and accepted by the owner. They are already built into the rest of this
plan. Items marked **spec change** mean the build differs from SPEC.md v0.3. Copy them into the
spec when it moves to v0.4.

| # | Topic | Decision | Reason | Spec change |
| --- | --- | --- | --- | --- |
| D1 | Firestore read quota | Each `companies/{id}` doc carries a compact `jobIndex` map (jobId → content hash, missCount, lastSeenAt). The poller reads ~100 docs per run (≈ 2,400 reads/day), not every job doc. | Reading every job doc hourly ≈ 72,000 reads/day, over the 50,000/day Spark limit. | Yes (§7 data model) |
| D2 | Firestore write quota | `lastSeenAt` and `missCount` live only in `jobIndex`. A job doc is written only when it is new, changed or closed. | Writing `lastSeenAt` on every job each poll ≈ 72,000 writes/day, over the 20,000/day Spark limit. | Yes (§7 data model) |
| D3 | Directory search | The poller maintains one `directory/v1` doc with a summary row per company. The app reads 1 doc and searches/sorts in memory. The 20-per-page rule applies to job and news lists. | M1 search and sort need all 100 companies; a 20-doc page can't support that. | Yes (§6 guardrails, §7) |
| D4 | Run log path | Top-level collection `pollerRuns/{runId}`. | `meta/pollerRuns/{runId}` is not a valid document path. | Yes (§7) |
| D5 | Repo visibility | The repo is **public**. Secrets live in GitHub Secrets. Keystore, `google-services.json` and tester data never enter the repo. | 72 scheduled runs/day exceed the 2,000 free minutes/month of a private repo; public repos run free. | No |
| D6 | First-poll flood | A `seededAt` field per company. The first successful poll records jobs **without** pushing. Funding pushes only for news published in the last 48 h. | Otherwise every existing job is "new" on the first poll. | Yes (§7) |
| D7 | Failed fetches | `missCount` is incremented only when the fetch returned HTTP 200 with a valid payload. Failures are logged and the company is skipped. | Two failed polls in a row would otherwise close every job. | No (clarifies M3) |
| D8 | Open-rate measurement | Main: `fcm_options.analytics_label` per push type + FCM delivery reports in the console (received/opens). Backup: custom `notif_open` event on tap. | Topic sends don't tell you how many devices received them. | No (clarifies §2 metric) |
| D9 | Role-family keys | Topics and data use `eng`, `data`, `design`, `product`, `gtm`, `other`. Labels appear only in the UI. | FCM topic names can't contain "/". | Yes (§6 push topics) |
| D10 | Throttle state | `companies/{id}` stores `lastJobPushAt{family}` and `lastSignalPushAt`. | M4 (6 h) and M7 (7 days) throttles need stored timestamps. | Yes (§7) |
| D11 | ReferralWorld brand | **Permission confirmed by owner.** Button label: "Get referred on ReferralWorld". Keep a copy of the written permission with the project files. | Closes the open item in spec §11. | No |
| D12 | Follows on reinstall | Accepted for MVP: uninstalling (or clearing app data) loses follows; installing an update over the old version keeps them. Stated in the install guide. | Anonymous Auth gives a new uid on reinstall; sign-in is out of scope. | No |

---

## 2. Repository layout

One public repo (D5), named `rw-radar`.

```
rw-radar/
├── SPEC.md
├── PLAN.md
├── README.md
├── CHANGELOG.md
├── registry/
│   ├── companies.json            # 100 hand-curated entries (spec §5)
│   └── news_blocklist.json       # manual blocklist of bad news matches
├── poller/
│   ├── requirements.txt          # firebase-admin, requests, feedparser, pytest
│   ├── rwradar_poller/
│   │   ├── __main__.py           # CLI: jobs | news | validate-registry
│   │   ├── config.py             # env vars, flags (--dry-run, --no-push, --company)
│   │   ├── http.py               # shared session, User-Agent, 1 req/s/host limiter, retries
│   │   ├── registry.py           # load + validate companies.json
│   │   ├── models.py             # Job, NewsItem dataclasses
│   │   ├── ats/
│   │   │   ├── greenhouse.py     # fetch + normalize to Job
│   │   │   ├── lever.py
│   │   │   └── ashby.py
│   │   ├── classify.py           # job title → role family
│   │   ├── jobs_sync.py          # diff vs jobIndex, writes, push decisions
│   │   ├── news/
│   │   │   ├── feeds.py          # RSS sources + Google News queries
│   │   │   ├── tagger.py         # headline → Funding/Layoffs/Acquisition/Financials/Other
│   │   │   ├── matcher.py        # headline → companyIds (name + aliases)
│   │   │   └── news_sync.py
│   │   ├── directory.py          # rebuild directory/v1 summary doc (D3)
│   │   ├── push.py               # FCM topic messages, throttles
│   │   ├── store.py              # thin Firestore wrapper
│   │   └── runlog.py             # pollerRuns/{runId}
│   └── tests/
│       ├── fixtures/             # saved real responses from each ATS + RSS
│       ├── test_ats_normalize.py
│       ├── test_classify.py
│       ├── test_tagger.py
│       ├── test_matcher.py
│       └── test_jobs_diff.py
├── firebase/
│   ├── firebase.json
│   ├── firestore.rules
│   └── firestore.indexes.json
├── .github/workflows/
│   ├── poll-jobs.yml
│   ├── poll-news.yml
│   └── poller-tests.yml          # pytest on push
├── app/                          # Android Studio project
└── docs/
    ├── install-guide.md          # sideload steps with screenshots
    ├── privacy.md                # same text as the in-app privacy note
    └── metrics.md                # filled on Day 17
```

Never committed: `google-services.json`, the service-account JSON, the release keystore
and its passwords, and `local.properties`. Add them to `.gitignore` on Day 1.

---

## 3. Company registry

File: `registry/companies.json`

```json
[
  {
    "id": "examplecorp",
    "name": "ExampleCorp",
    "aliases": ["Example Corp", "ExampleCorp Technologies"],
    "sector": "Fintech",
    "website": "https://example.com",
    "ats": { "type": "greenhouse", "token": "examplecorp" },
    "logoUrl": ""
  }
]
```

Rules:
- `id`: lowercase slug, `[a-z0-9-]` only (it goes into topic names), unique, never changed after launch.
- `ats.type`: one of `greenhouse`, `lever`, `ashby`.
- `aliases`: only names specific enough to match a headline safely. Skip generic words
  (for example a company called "Swift" needs aliases like "Swift Technologies" and must not use "Swift" alone).
- `logoUrl`: optional. The app shows an initials avatar when it is empty. Don't depend on a third-party logo API.
- `python -m rwradar_poller validate-registry` checks the schema, unique ids, the slug format,
  and that each ATS endpoint returns 200. It runs in CI.

Finding companies (Days 1–3):
- Search for `site:boards.greenhouse.io Bengaluru`, `site:jobs.lever.co Bangalore`,
  `site:jobs.ashbyhq.com India` (also try Gurugram, Mumbai, Pune, Hyderabad, Remote India).
- The token is the path segment in the board URL (`boards.greenhouse.io/{token}`,
  `jobs.lever.co/{company}`, `jobs.ashbyhq.com/{name}`).
- Keep a company only if its board returns at least 1 job located in India or remote.
- Sector mix to aim for: fintech, SaaS, consumer, devtools, AI, e-commerce, health. Prefer
  companies that hire 0–4 years experience.

---

## 4. Poller (Python, GitHub Actions)

### 4.1 Shared HTTP
- `User-Agent: RWRadarPoller/0.1 (+https://github.com/<user>/rw-radar)`.
- A rate limiter per host allows at most 1 request/second (spec §5).
- Timeout 15 s, 2 retries with backoff on 5xx and timeouts, no retry on 4xx.
- Every failure is recorded in the run log with the company id and HTTP status.

### 4.2 ATS adapters
Each adapter returns `list[Job]` or raises `FetchError`. Check field names against real
responses during the Day 1 spike, and save those responses as test fixtures.

| ATS | Request | Title | Location | Dept | Remote | Posted date | URL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | `title` | `location.name` | `departments[0].name` | location text contains "remote" | `first_published` if present, else `updated_at` | `absolute_url` |
| Lever | `GET api.lever.co/v0/postings/{company}?mode=json` | `text` | `categories.location` | `categories.department` or `team` | `workplaceType == "remote"` | `createdAt` (ms epoch) | `hostedUrl` |
| Ashby | `GET api.ashbyhq.com/posting-api/job-board/{name}` | `title` | `location` | `department` | `isRemote` / `workplaceType` | `publishedAt` | `jobUrl` |

Job id in Firestore: `{atsType}_{atsJobId}` (stable across polls).
Content hash: sha1 of `title|location|dept|remote|url`. When it changes, the job document is rewritten.

### 4.3 Role-family classifier (`classify.py`)
Lowercase the title and check the rules in this order. The first match wins. Family keys follow D9.

| Order | Family key | Label | Keywords (title contains) |
| --- | --- | --- | --- |
| 1 | `design` | Design | designer, design, ux, ui/ux, user research |
| 2 | `data` | Data | data, analytics, analyst, machine learning, ml , ai engineer, scientist, bi |
| 3 | `product` | Product | product manager, product owner, pm , program manager |
| 4 | `gtm` | Marketing/Sales | marketing, growth, sales, account executive, business development, bdr, sdr, seo, content, brand, partnerships |
| 5 | `eng` | Engineering | engineer, developer, sde, devops, sre, backend, frontend, full stack, android, ios, qa, test, architect, security |
| 6 | `other` | Other | everything else |

Order matters: "Product Designer" → Design, "Data Engineer" → Data, "Sales Engineer" → Marketing/Sales.
Unit tests use 50+ real titles from the spike fixtures. Fix the rules until all of them pass.

### 4.4 Jobs sync (`jobs_sync.py`): one run
For each company in the registry:
1. Fetch the ATS. If it fails → log it and skip this company. **Don't touch missCount** (D7).
2. Read `companies/{id}` (1 read), which includes `jobIndex` (D1).
3. Compare the fetched jobs with `jobIndex`:
    - **New** (not in the index) → create the job doc with `status: open` and `firstSeenAt = now`. Add it to `newJobs[family]`.
    - **Seen before, hash changed** → update the job doc.
    - **Seen before, hash same** → set `lastSeenAt` and `missCount = 0` in the index only (D2).
    - **In the index but not fetched** → `missCount += 1`. At 2 → set `status: closed` on the job doc (spec M3).
    - **Closed job reappears** → reopen it. Don't push.
4. Update `companies/{id}`: `jobIndex`, `openCount`, `newThisWeek` (open jobs with
   `firstSeenAt` in the last 7 days), `lastPolledAt`. Use one batched write per company.
5. Push decision. If `seededAt` is unset, set it on this run and send nothing (D6). Otherwise,
   for each family with new jobs, if `now - lastJobPushAt[family] >= 6h`, send one push and
   update `lastJobPushAt[family]` (D10). Otherwise log it as `throttled`.
6. Record each new job's delay `pushSentAt - postedAt` in the run log for the 90-minute metric.

After all companies: rebuild `directory/v1` if any summary field changed (D3), and write `pollerRuns/{runId}` (D4).

### 4.5 News sync (`news_sync.py`)
Sources (confirm on Day 1; drop any without a usable feed; at least 2 must work, spec §5):

| Source | Feed URL to test | Cadence |
| --- | --- | --- |
| Inc42 | `https://inc42.com/feed/` | every run (30 min) |
| Entrackr | `https://entrackr.com/feed` | every run |
| YourStory | `https://yourstory.com/feed` | every run |
| Google News | `https://news.google.com/rss/search?q=<query>&hl=en-IN&gl=IN&ceid=IN:en` | every 2nd run (2 h) |

Google News: put about 10 companies in one query (`"A" OR "B" OR …`) so a run makes about 10 requests,
not 100. This lowers the chance of being rate-limited from GitHub's IP addresses. Items from a
company's query are still checked by the matcher below.

Per item:
1. Normalize the URL (drop UTM params, fragments). `hash = sha1(url)`.
2. Skip it if the hash is in `newsIndex` (a single doc `meta/newsIndex` holding hashes from the last 30 days, 1 read per run).
3. **Tag** (`tagger.py`), first match wins:
    - Layoffs: lays off, layoff, job cuts, retrench, downsiz, fires
    - Acquisition: acquires, acquired, acquisition, merger, merges, buys
    - Funding: raises, raised, funding, series a–f, seed round, pre-seed, pre-series, crore round, led by, bridge round
    - Financials: revenue, profit, loss, fy2, ipo, valuation, arr
    - Other: everything else
4. **Match** (`matcher.py`): exact-phrase, case-insensitive, word-boundary match of the name or
   any alias in the headline. Drop matches on `news_blocklist.json`.
   For **Funding** items only, the company name must appear *before* the funding verb, so that
   "X invests in Y" counts as Y raising money, not X.
5. Write `news/{hash}` only if it matched at least one company. Unmatched items are only added to `newsIndex`.
6. For each matched company with a Funding tag: set `lastFundingAt`. If `publishedAt` is in the
   last 48 h (D6) and `now - lastSignalPushAt >= 7 days` (D10), send the signal push (M7).

### 4.6 Push messages (`push.py`)
All pushes are FCM **topic** messages of type notification + data, with Android priority `high` (spec §11).

| Kind | Topic | Title | Body | Data | Channel |
| --- | --- | --- | --- | --- | --- |
| New jobs (M4) | `c_{companyId}_{family}` | `{Company}` | `3 new Engineering roles at {Company}` (singular for 1) | `type=jobs, companyId, family, since=<runStartedAt>` | `new_openings` |
| Funding (M7) | `c_{companyId}_signal` | `{Company}` | `{Company} raised funding. {N} open roles right now.` | `type=signal, companyId, newsHash` | `hiring_signals` |

- `fcm_options.analytics_label`: `jobs_{family}` / `signal` (D8).
- `--no-push` and `--dry-run` flags log what would be sent. Use them for all early testing.
- A `debug_all` topic receives a copy of every push during development. Remove it before Day 13.

### 4.7 Workflows
`poll-jobs.yml` (`poll-news.yml` is the same, with `cron: "13,43 * * * *"`, group `poll-news` and command `news`):

```yaml
name: poll-jobs
on:
  schedule:
    - cron: "7 * * * *"      # odd minute: top-of-hour cron queues are the most delayed
  workflow_dispatch: {}
concurrency:
  group: poll-jobs
  cancel-in-progress: false
jobs:
  poll:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r poller/requirements.txt
      - run: python -m rwradar_poller jobs
        working-directory: poller
        env:
          FIREBASE_SERVICE_ACCOUNT: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}
```

- Both workflows update different fields of `companies/{id}`, so always use `update()`/merge, never `set()` on the whole doc.
- `poller-tests.yml` runs `pytest` and `validate-registry` on every push to `main`.

### 4.8 Run log: `pollerRuns/{runId}`
`startedAt, finishedAt, durationMs, kind (jobs|news), counts {companies, fetched, new, changed, closed, pushed, throttled, failedFetches}, errors[], delays[]` (delays are minutes from posted to pushed, for jobs only).

---

## 5. Firebase setup

### 5.1 Project
- One Firebase project on the Spark plan. Enable Anonymous Auth, Firestore (production mode),
  Cloud Messaging, Analytics and Crashlytics.
- Service account with Firestore + FCM access → JSON key → GitHub Secret `FIREBASE_SERVICE_ACCOUNT`.
- Day 1: write down the current Spark quotas from the Firebase pricing page into this file:
  reads/day ______, writes/day ______, deletes/day ______, storage ______.
  If they differ from 50,000 reads / 20,000 writes per day, recheck the D1/D2 numbers.
- Set a budget alert. Watch Usage on the Firestore console daily during the closed test.

### 5.2 Security rules: `firebase/firestore.rules`
```
rules_version = '2';
service cloud.firestore {
  match /databases/{db}/documents {
    match /companies/{id} {
      allow read: if true;
      allow write: if false;
      match /jobs/{jobId} {
        allow read: if true;
        allow write: if false;
      }
    }
    match /directory/{id} { allow read: if true;  allow write: if false; }
    match /news/{id}      { allow read: if true;  allow write: if false; }
    match /users/{uid} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
    match /pollerRuns/{id} { allow read, write: if false; }
    match /meta/{doc}      { allow read, write: if false; }
  }
}
```
The Admin SDK used by the poller bypasses these rules, so "all other writes only from the
poller" holds. Test the rules in the Firebase emulator or Rules Playground before Day 6.

### 5.3 Indexes: `firebase/firestore.indexes.json`
- `jobs` (per company subcollection): `status ASC, firstSeenAt DESC`
- `news`: `companyIds ARRAY_CONTAINS, publishedAt DESC`

### 5.4 Final data model (spec §7 plus D1–D4, D6, D10)
- `companies/{id}`: registry fields, `openCount, newThisWeek, lastFundingAt, lastPolledAt, seededAt, lastJobPushAt{family}, lastSignalPushAt, jobIndex{jobId: {h, miss, seen}}`
- `companies/{id}/jobs/{jobId}`: `title, family, location, remote, dept, url, postedAt, firstSeenAt, status`
- `directory/v1`: `updatedAt, companies[] {id, name, aliases, sector, openCount, newThisWeek, lastFundingAt, logoUrl}`
- `news/{hash}`: `title, source, url, publishedAt, tag, companyIds[]`
- `users/{uid}`: `follows[], families[], notifPrefs {jobs, signals}, createdAt`
- `meta/newsIndex`: `hashes{hash: seenAt}`, pruned to 30 days
- `pollerRuns/{runId}`: see 4.8

Note: `jobIndex` is readable by anyone because company docs are public. It holds no personal data. The app should ignore it.

---

## 6. Android app

### 6.1 Project setup
- Android Studio, "Empty Activity (Compose)" template. Package `com.rwradar.app`. Min SDK 26, target the latest stable SDK.
- Dependencies (use latest stable versions when you start): Firebase BoM (auth, firestore,
  messaging, analytics, crashlytics), Navigation Compose, Lifecycle ViewModel Compose,
  `androidx.browser` (Custom Tabs), DataStore Preferences, Coil (logos),
  `kotlinx-coroutines-play-services` (`.await()` on Firebase tasks).
- Dependency injection: a manual `AppContainer` created in `Application`. That is enough for
  this size of app, and Hilt would add setup time.
- Release build: R8 on, Crashlytics mapping upload on.

### 6.2 Package structure
```
com.rwradar.app
├── RwRadarApp.kt              # Application: AppContainer, notification channels, Crashlytics
├── MainActivity.kt            # single activity, handles notification-tap intents
├── data/
│   ├── model/                 # Company, DirectoryEntry, Job, NewsItem, RoleFamily, UserPrefs
│   ├── AuthRepository.kt      # anonymous sign-in, current uid
│   ├── DirectoryRepository.kt # listens to directory/v1 → Flow<List<DirectoryEntry>>
│   ├── CompanyRepository.kt   # company doc, jobs page, news page
│   ├── UserRepository.kt      # users/{uid}: follows, families, notifPrefs
│   └── LocalPrefs.kt          # DataStore: onboardingDone, subscribedTopics, lastViewedAt{companyId}
├── push/
│   ├── TopicSync.kt           # desired topics vs subscribed topics → subscribe/unsubscribe
│   ├── RwMessagingService.kt  # onMessageReceived (foreground), onNewToken
│   └── Channels.kt            # new_openings, hiring_signals
├── analytics/Events.kt        # one place for all event names
├── ui/
│   ├── nav/RwNavHost.kt
│   ├── onboarding/            # 3 steps
│   ├── discover/
│   ├── following/
│   ├── company/               # header, Openings tab, News tab
│   ├── settings/
│   └── components/            # CompanyRow, FollowButton, JobRow, NewsRow, EmptyState, ErrorState
└── util/CustomTabs.kt
```

### 6.3 Screens (spec §8)
| Screen | ViewModel state | Key behavior |
| --- | --- | --- |
| Onboarding 1: Role families | selected families | Multi-select chips. At least 1 required. |
| Onboarding 2: Follow companies | directory + follows | Search + follow. "Continue" enabled at ≥ 3 follows (M9). |
| Onboarding 3: Notifications | permission state | Android 13+: request `POST_NOTIFICATIONS`. Below 13: skip. If denied, continue anyway and show a banner later. |
| Discover | query, sort, entries | In-memory search over `directory/v1` (< 300 ms target, M1, D3). Sort: Most new roles this week (`newThisWeek` desc), Recently funded (`lastFundingAt` desc), A–Z. Row: logo, name, sector, open count, funding tag, follow button. |
| Following | followed entries + unread counts | Unread = new jobs + news since `lastViewedAt[companyId]` (first item to cut, spec §10). Banner if notifications are off. |
| Company detail | company, tab, jobs page, news page | Header, Follow, "Get referred on ReferralWorld" button (M8, D11). Openings: 20 per page, filters for family / location text / remote only, jobs with `firstSeenAt >= since` highlighted when opened from a push. News: 20 per page, tag chip, tap → Custom Tab. Opening the screen sets `lastViewedAt`. |
| Settings | prefs | Toggles: New openings, Funding signals. Role families editor. Privacy note. App version (`BuildConfig.VERSION_NAME`). |

Each list has three states: loading, empty ("No open roles right now") and error (with a retry button).

### 6.4 Topic sync (M2, M4, M5, M9 settings)
- Desired topics = for each followed company:
  `c_{id}_{family}` for each chosen family if `notifPrefs.jobs`, plus `c_{id}_signal` if `notifPrefs.signals`.
- `TopicSync.sync()` compares the desired set with `subscribedTopics` in DataStore, calls
  `subscribeToTopic`/`unsubscribeFromTopic` for the difference, and stores the result.
- Runs on follow/unfollow, preference change and settings toggle (target < 5 s, M5), and once at app start (fixes any earlier failures).
- FCM limits each app instance to 2,000 topics. Worst case here is 100 × 7 = 700.

### 6.5 Notification handling
- Create channels `new_openings` and `hiring_signals` in `Application.onCreate`.
- **Background or killed:** the system shows the notification. Tapping it launches `MainActivity`
  with the data fields as intent extras → navigate to company detail (Openings tab for `jobs` with `since`, News tab for `signal`).
- **Foreground:** `onMessageReceived` builds the same notification with a `PendingIntent` carrying the same extras.
- Log `notif_open {type, companyId}` on every tap (D8).

### 6.6 Analytics events
`onboarding_complete {families, follows}`, `follow_company {id, source}`, `unfollow_company {id}`,
`view_company {id, source}`, `apply_click {id, family}`, `news_click {id, tag}`,
`referralworld_click {id}`, `notif_open {type, id}`, `prefs_changed {families}`, `notif_toggle {kind, on}`.

---

## 7. Content to write

- **Privacy note** (in-app + `docs/privacy.md`): what is collected (anonymous ID, follows, role
  preferences, analytics events, crash reports), what isn't (no name, email, phone, résumé),
  where it's stored (Google Firebase), how to delete it (uninstall clears the local ID; email the
  owner to delete server data), and that news links go to the publishers' sites.
- **Install guide** (`docs/install-guide.md`): download the APK → allow "Install unknown apps" for
  the browser or Files app → open the APK → "Install anyway" if Play Protect warns → allow notifications.
  Updates install over the old version and keep follows; uninstalling loses them (D12). Add screenshots from 2 phone brands.
- **Feedback form** (Google Form): device model, Android version, what happened, screenshot upload, contact (optional).
- **ReferralWorld button** label: "Get referred on ReferralWorld" (permission confirmed, D11).

---

## 8. Testing

Poller (automated, `pytest`):
- Adapter normalization against saved fixtures for all 3 ATSs.
- Classifier: 50+ real titles. Tagger: 30+ real headlines per tag. Matcher: alias and blocklist cases,
  plus the "X invests in Y" case.
- Diff logic: new / changed / missing once / missing twice → closed / reappear / fetch failure leaves missCount alone / seeding run sends no push / 6 h throttle / 7-day throttle / 48 h news freshness.

Poller (manual):
- `--dry-run` against all 100 companies before the first real write.
- `--company <id> --no-push` for single-company debugging.
- After the first real runs: check `pollerRuns` counts, and confirm Firestore usage is under 20% of quota.

App (manual checklist, run on 2 devices: one Android 13+, one Android 8–12):
- Every acceptance criterion in Section 11.
- Airplane mode: Discover and followed companies still load from cache.
- Notification permission denied → banner shows, app works.
- Kill the app → push arrives → tap → the correct tab opens with highlights.
- Install the v2 APK over v1 → follows kept.

App (automated, small): unit tests for `TopicSync` diff, sort/search logic, unread-count logic.

---

## 9. Release and signing

- Generate the release keystore once (Android Studio → Generate Signed Bundle/APK). Store the file
  and passwords in a password manager **and** an offline backup. Losing it means testers must
  uninstall to update (spec §9).
- Signing config reads its values from `local.properties` or environment variables, never from the repo.
- `versionCode` +1 for every APK sent out. `versionName`: `0.1.0` (closed test), `0.1.x` (fixes), `1.0.0` (first GitHub Release).
- APK file name: `rw-radar-<versionName>.apk`.
- Release notes per build in `CHANGELOG.md`. On Day 17 they become the GitHub Release notes.

---

## 10. Day-by-day checklist (18 working days)

### Day 1: Spikes and Firebase
- [ ] Create the public repo (D5), `.gitignore`, README, CHANGELOG, and copy in SPEC.md and PLAN.md.
- [ ] File the written ReferralWorld brand permission with the project records (D11).
- [ ] Job API spike: find 5 Indian companies across Greenhouse / Lever / Ashby. Call each endpoint, save the responses to `poller/tests/fixtures/`, and confirm the field names in the table in 4.2.
- [ ] News spike: fetch each feed in 4.5 and record which work. Try one Google News query with 10 companies OR'd.
- [ ] Firebase project, all services enabled, service-account secret in GitHub, quota numbers written into 5.1.
- [ ] Confirm the FCM delivery reports in the console show received/opens for Android (D8).
- **Done when:** fixtures exist for all 3 ATSs (or a decision is written down to drop one), ≥ 2 news sources work, and the Firebase project is ready.

### Days 2–3: Registry, Poller v1, app skeleton
- [ ] `registry/companies.json` with 100 entries and `validate-registry` passing (all endpoints 200).
- [ ] `http.py`, 3 adapters, `classify.py`, `models.py`, with tests passing.
- [ ] `jobs_sync.py` without pushes: diff, writes, `jobIndex`, missCount, seeding, `directory/v1`, run log.
- [ ] `--dry-run` across all 100, then a real run. Check the docs in the console.
- [ ] `poll-jobs.yml` and `poller-tests.yml` active. Watch 2 scheduled runs succeed.
- [ ] Android project created, Firebase connected, anonymous sign-in on launch, Crashlytics test crash received.
- [ ] Discover screen listing `directory/v1` with search and the 3 sorts.
- **Done when:** the hourly workflow fills Firestore for 100 companies with no manual steps, and Discover shows them on a device.

### Days 4–6: Follow, detail, Openings, new-job push end to end
- [ ] Security rules + indexes deployed and tested.
- [ ] `UserRepository`: follows in `users/{uid}` (arrayUnion/arrayRemove), FollowButton on list + detail.
- [ ] Company detail screen with header and Openings tab: paging by 20, filters, Custom Tab apply link.
- [ ] `TopicSync` + `Channels` + `RwMessagingService` + tap routing with highlights.
- [ ] `push.py` for job pushes with the 6 h throttle and `analytics_label`. Turn pushes on in the workflow.
- [ ] End-to-end test: pick a company with frequent postings, or temporarily delete one job from its
  `jobIndex` using a test script so the next poll sees it as new → push arrives → tap opens Openings with that job highlighted.
- [ ] Measure the delay in `pollerRuns` for the first real new jobs.
- **Done when:** a real new job at a followed company produces one grouped push, and tapping it lands on the highlighted job.

### Days 7–9: News, tags, matching, funding push
- [ ] `feeds.py`, `tagger.py`, `matcher.py`, `news_sync.py` with tests, `meta/newsIndex`, blocklist file.
- [ ] `poll-news.yml` active (Google News every 2nd run).
- [ ] News tab on company detail: 20 per page, tag chip, Custom Tab to the publisher.
- [ ] `lastFundingAt` shown as a "Funded" tag in Discover, and the Recently funded sort works.
- [ ] Funding signal push with the 7-day throttle and the 48 h freshness rule.
- [ ] Review 2 days of matched news by hand. Add aliases or blocklist entries for every wrong match.
- **Done when:** news shows up for followed companies, wrong-match rate is under ~10% on the manual review, and one signal push has been received (use `debug_all` with a crafted test item if no real funding happens).

### Days 10–11: Onboarding, settings, ReferralWorld button, analytics
- [ ] 3-step onboarding, shown until finished, then never again (`onboardingDone`).
- [ ] Settings: two notification toggles, role-family editor (re-sync < 5 s), privacy note, version.
- [ ] Following screen with unread counts and the notifications-off banner.
- [ ] "Get referred on ReferralWorld" button on company detail (Custom Tab, plain homepage URL, no params).
- [ ] All analytics events in 6.6 firing (check in DebugView).
- **Done when:** a fresh install can go from onboarding to receiving a push without help, and every event shows in DebugView.

### Day 12: Polish and release build
- [ ] Empty / error / loading states on every list. Offline behavior checked.
- [ ] App icon, app name, light/dark theme check, large font check.
- [ ] Remove the `debug_all` topic and debug logging.
- [ ] Signed release APK `0.1.0`, installed on 2 devices from a download link.
- [ ] `docs/install-guide.md` with screenshots, `docs/privacy.md`, feedback form ready.
- **Done when:** the release APK passes the full manual checklist in Section 8 on both devices.

### Day 13: Closed test starts
- [ ] Send the APK link, install guide and feedback form to 12+ testers.
- [ ] Track installs (`onboarding_complete` count) and reply to setup problems the same day.
- **Done when:** ≥ 12 testers have finished onboarding.

### Days 14–16: Fix tester feedback
- [ ] Triage the feedback form and Crashlytics daily: crashes first, then push problems, then UX.
- [ ] Ship updated APKs (`0.1.x`, same key, versionCode +1) with CHANGELOG entries.
- [ ] Check Firestore usage and Actions run health daily.
- **Done when:** no open crash issues and no known push-delivery bugs.

### Day 17: Metrics and first GitHub Release
- [ ] Fill in `docs/metrics.md`:

  | Metric | Target | Source | Result |
    | --- | --- | --- | --- |
  | Closed-test testers | 12+ | Analytics `onboarding_complete` users | |
  | Companies tracked | 100 | `directory/v1` length | |
  | Median delay, job posted → push sent | < 90 min | median of `delays[]` across `pollerRuns` | |
  | Notification open rate | 25%+ | FCM reports (opens/received), checked against `notif_open` | |
  | Crash-free sessions | 99%+ | Crashlytics dashboard | |
- [ ] Tag `v1.0.0`, create the GitHub Release with the APK and notes.
- [ ] Update SPEC.md to v0.4 with the spec changes from Section 1.
- **Done when:** the release is public and every metric has a number.

### Day 18: Presentation
- [ ] Live demo: onboarding → follow → push → tap → highlighted job → ReferralWorld button.
- [ ] Slides: problem, how it works (one architecture diagram), metrics table, what testers said, roadmap
  (sign-in + sync, more job sources, ReferralWorld integration with UTM/deep links, iOS).

### If behind schedule
Cut in the spec's order: (1) news filters and sort options, (2) Following unread counts,
(3) M7 funding push, (4) M6 news. Decide at the end of Day 9 and Day 12. Don't cut seeding (D6), the throttles (D10) or the run log.

---

## 11. Acceptance checklist (spec §4 → how verified)

| ID | Criterion | Verified by |
| --- | --- | --- |
| M1 | Lists name, sector, open-role count, last funding tag | Manual, Discover |
| M1 | Search < 300 ms from local cache | Airplane mode + timing log around the filter |
| M1 | Sorts: new this week, recently funded, A–Z | Manual, compared against Firestore values |
| M2 | One-tap follow from list and detail | Manual |
| M2 | Follows survive restart | Force-stop, reopen |
| M2 | Follow subscribes topics | `subscribedTopics` in DataStore + push received |
| M3 | Job shows title, location, dept, posted date, apply link | Manual |
| M3 | Apply opens the company posting in a Custom Tab | Manual |
| M3 | Missing 2 polls → closed and hidden | `test_jobs_diff.py` + one real case in the console |
| M3 | Filters: family, location text, remote | Manual |
| M4 | Only jobs first seen this poll | Unit test + seeding check |
| M4 | One push per company per family per poll, grouped copy | Unit test + a real push |
| M4 | Tap opens Openings with new jobs highlighted | Manual (background, killed, foreground) |
| M4 | ≤ 1 push per company per family per 6 h | Unit test + `throttled` count in run log |
| M5 | Pick families at onboarding | Manual |
| M5 | Poller classifies titles by keyword | `test_classify.py` |
| M5 | Pref change re-subscribes in < 5 s | Timing log in `TopicSync` |
| M6 | Headline, source, time, tag | Manual |
| M6 | Tags by keyword rules | `test_tagger.py` |
| M6 | Tap opens publisher, no body stored | Manual + `news/{hash}` schema has no body field |
| M6 | Matched by name and aliases | `test_matcher.py` + Day 9 manual review |
| M7 | Funding + followed → push with exact copy | Real or test-item push |
| M7 | ≤ 1 per company per 7 days | Unit test |
| M8 | Button on every company detail | Manual |
| M8 | Opens homepage in Custom Tab, no params | Manual, check the URL |
| M9 | Onboarding: families, ≥ 3 follows, permission prompt (13+) | Manual on both devices |
| M9 | Settings: per-signal toggles, prefs, privacy note, version | Manual |
| §5 | Phone never calls sources | App network log shows only Firebase/Google hosts + Custom Tabs |
| §5 | User-Agent + 1 req/s/host | `http.py` unit test on the limiter |
| §7 | `users/{uid}` only readable/writable by its owner | Rules Playground test with another uid |
