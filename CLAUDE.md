# CLAUDE.md: RW Radar

Project memory for Claude Code. Read this first in every session. Source documents:
- [SPEC.md](SPEC.md): product spec v0.3 (what to build)
- [PLAN.md](PLAN.md): build plan v1.0 with locked decisions D1–D12 (how to build it). **PLAN.md wins over SPEC.md where they differ.**

If this file and PLAN.md disagree on a *data contract* (section 4 below), this file wins: it pins the details PLAN.md left open. Update this file whenever a contract changes.

---

## 1. What this is

RW Radar is an Android app for Indian tech job seekers (0–4 yrs). Users follow companies and get push
notifications when (a) a followed company posts a job in a role family they chose, or (b) the company
raises funding. It is a companion to ReferralWorld Careers. It is standalone: no ReferralWorld DB or
integration, only a plain link button.

Three moving parts, with **no server to run**:
1. **Poller** (Python, `poller/`): run by GitHub Actions cron. Fetches Greenhouse/Lever/Ashby job
   boards and news RSS, diffs them against Firestore, writes the changes, and sends FCM **topic** pushes.
2. **Firestore** (Firebase Spark free plan): all data. Public read for companies, jobs, news and
   directory. `users/{uid}` is owner-only. Only the poller (Admin SDK) writes the shared data.
3. **Android app** (Kotlin + Compose, `app/`): reads Firestore and subscribes to FCM topics.
   **The phone never calls the job/news sources** (spec §5).

## 2. Repo layout

The Android Studio project root is the repo root (the repo is public, D5).

```
RWRadar/                      # repo root = Android Studio project root
├── CLAUDE.md  SPEC.md  PLAN.md  README.md  CHANGELOG.md
├── app/                      # Android app module (com.rwradar.app)
├── build.gradle.kts, settings.gradle.kts, gradle/libs.versions.toml, gradlew
├── registry/companies.json   # 100 hand-curated companies (source of truth for the poller)
├── registry/news_blocklist.json
├── poller/                   # Python package rwradar_poller + tests
├── firebase/                 # firebase.json, firestore.rules, firestore.indexes.json
├── .github/workflows/        # poll-jobs.yml, poll-news.yml, poller-tests.yml
└── docs/                     # install-guide.md, privacy.md, metrics.md
```

**Never commit:** `app/google-services.json`, any service-account JSON, `*.jks`/`*.keystore`, keystore
passwords, `local.properties`, tester data. They are in `.gitignore`. A **placeholder**
`app/google-services.json` (fake project values) may exist locally so the build compiles. Replace it
with the real file from the Firebase console.

## 3. Commands

Windows host. Use Git Bash or PowerShell. JDK 21 (JBR) is on PATH. The Android SDK is at `%LOCALAPPDATA%\Android\Sdk` (platform 36).

```bash
# Android
./gradlew :app:assembleDebug          # build debug APK
./gradlew :app:testDebugUnitTest      # JVM unit tests (TopicSync diff, sort/search, unread logic)
./gradlew :app:assembleRelease        # needs signing props (see §7)

# Poller (run from poller/)
cd poller
python -m pip install -r requirements.txt
python -m pytest -q
python -m rwradar_poller validate-registry            # schema + slug + unique ids (+ --check-endpoints for HTTP 200)
python -m rwradar_poller jobs --dry-run               # no Firestore writes, no pushes
python -m rwradar_poller jobs --company <id> --no-push
python -m rwradar_poller news --dry-run
```

Poller env vars: `FIREBASE_SERVICE_ACCOUNT` (the service-account JSON *contents*), `RWRADAR_REPO_URL`
(goes into the User-Agent; the workflows set it from `github.server_url/github.repository`),
`RWRADAR_DEBUG_ALL_TOPIC=1` (also send each push to the `debug_all` topic; **off before Day 13**).

## 4. Data contracts (poller ⇄ app). Do not change one side only

### 4.1 Keys
- **Company id**: lowercase slug `^[a-z0-9-]+$`, unique, never renamed (it goes into topic names).
- **Role family keys** (D9), in classifier order:
  `design`=Design, `data`=Data, `product`=Product, `gtm`=Marketing/Sales, `eng`=Engineering, `other`=Other.
  The UI shows the labels. Data and topics use only the keys.
- **News tag keys**: `funding`, `layoffs`, `acquisition`, `financials`, `other`
  (UI labels: Funding, Layoffs, Acquisition, Financials, Other).
- **Job doc id**: `{atsType}_{atsJobId}` e.g. `greenhouse_4012345`, `lever_<uuid>`, `ashby_<uuid>`.
- **News doc id**: `sha1(normalizedUrl)` hex.
- **All `*At` fields are Firestore `Timestamp`** (never strings or epoch numbers), and may be `null` when unknown.

### 4.2 Firestore documents
| Path | Fields |
| --- | --- |
| `companies/{id}` | registry fields `id, name, aliases[], sector, website, ats{type, token}, logoUrl` + `openCount:int, newThisWeek:int, lastFundingAt, lastPolledAt, seededAt, lastJobPushAt:{family: Timestamp}, lastSignalPushAt, jobIndex:{jobId: {h:str, miss:int, seen:Timestamp, f:Timestamp(firstSeenAt)}}`. The app **ignores** `jobIndex`. The doc may hold **only registry fields** (first fetch failed), or may not exist yet, so the app must tolerate both. |
| `companies/{id}/jobs/{jobId}` | `title, family, location, remote:bool, dept, url, postedAt, firstSeenAt, status:"open"\|"closed"` |
| `directory/v1` | `updatedAt, companies:[{id, name, aliases[], sector, openCount, newThisWeek, lastFundingAt, logoUrl}]` |
| `news/{hash}` | `title, source, url, publishedAt, tag, companyIds[]` (**no body, ever**) |
| `users/{uid}` | `follows:[companyId], families:[familyKey], notifPrefs:{jobs:bool, signals:bool}, createdAt` |
| `meta/newsIndex` | `hashes:{hash: Timestamp}` (pruned to 30 days), `lastGoogleNewsAt` (Google News runs when this is unset or ≥ 105 min old) |
| `pollerRuns/{runId}` | `kind:"jobs"\|"news", startedAt, finishedAt, durationMs, counts:{companies, fetched, new, changed, closed, reopened, pushed, throttled, failedFetches, newsItems, newsMatched}, errors:[{companyId?, source?, status?, message}], delays:[minutes:float]` |

Queries the app makes (indexes are in `firebase/firestore.indexes.json`):
- Openings: `companies/{id}/jobs` where `status == "open"` orderBy `firstSeenAt desc`, limit 20, paged with `startAfter`.
- News: `news` where `companyIds array-contains {id}` orderBy `publishedAt desc`, limit 20.
- Directory: a single doc read/listen of `directory/v1`. Search and sort happen in memory (D3).

### 4.3 FCM topics and payloads
- Topics: `c_{companyId}_{family}` (jobs), `c_{companyId}_signal` (funding), `debug_all` (dev only).
- All pushes are **notification + data** messages, Android priority `high`, with `notification.channel_id` set.

| Kind | Topic | Title | Body | Data | Channel | analytics_label |
| --- | --- | --- | --- | --- | --- | --- |
| Jobs (M4) | `c_{id}_{family}` | `{Company}` | `3 new Engineering roles at {Company}` / `1 new Engineering role at {Company}` | `type=jobs, companyId, family, since=<run start, epoch millis as string>` | `new_openings` | `jobs_{family}` |
| Funding (M7) | `c_{id}_signal` | `{Company}` | `{Company} raised funding. {N} open roles right now.` | `type=signal, companyId, newsHash` | `hiring_signals` | `signal` |

App tap routing: `type=jobs` opens Company detail → Openings tab and highlights jobs with
`firstSeenAt >= since`. `type=signal` opens Company detail → News tab. Log `notif_open {type, id}`.

### 4.4 Throttles and safety rules (do not remove; PLAN §10)
- Seeding (D6): first successful poll of a company sets `seededAt` and **sends no push**. On the seeding run, each job's
  `firstSeenAt = min(postedAt, now)` (not `now`), so `newThisWeek` and the Openings order make sense from day 1.
- Job content hash = sha1 of `title|location|dept|remote|url|family` (family included, so a classifier change rewrites the affected docs once).
- Greenhouse: `/jobs` (master list) + `/departments` (for dept), both of which must succeed. `?content=true` is not used (it can be 2 MB+).
- News items without a published date use their first-seen time as `publishedAt` and never push. The signal push copy says "1 open role" when N is 1.
- The same story from several publishers becomes several news items (no cross-source dedupe in the MVP).
- **India-only job filter** (`poller/rwradar_poller/location_filter.py`, on by default, `RWRADAR_INDIA_ONLY=0` disables it):
  only jobs located in India, or remote jobs with a generic location ("Remote", "Anywhere", "APAC"…), are stored and pushed.
  Why: the 100 boards hold ~12.6k jobs but only ~2.3k are India-relevant (e.g. OpenAI 827 jobs, 7 in India), so without the
  filter users get pushes for US jobs and the seeding run costs ~12.6k writes. A job that moves out of India is treated as missing and closes after 2 polls.
- Jobs push: ≤ 1 per company per family per 6 h (`lastJobPushAt[family]`).
- Funding push: ≤ 1 per company per 7 days (`lastSignalPushAt`), and only for news published in the last 48 h.
- `missCount` changes only after a successful (HTTP 200, valid payload) fetch (D7). At miss 2 → `status: closed`.
- A closed job that reappears is reopened, with no push.
- Firestore writes: only new, changed or closed job docs. `lastSeenAt` and `missCount` live in `jobIndex` only (D1/D2).
  Always use `update()`/`set(merge=True)` on `companies/{id}`, because the jobs and news workflows write different fields.
- HTTP: User-Agent `RWRadarPoller/0.1 (+<RWRADAR_REPO_URL>)`, ≤ 1 req/s per host, 15 s timeout, 2 retries on 5xx/timeout.

## 5. Android app conventions

- Package `com.rwradar.app`, min SDK 26, target/compile SDK 36, Kotlin + Jetpack Compose (Material 3),
  single activity, MVVM (ViewModel + StateFlow), manual DI via `AppContainer` built in `RwRadarApp` (no Hilt).
- Firebase: anonymous Auth, Firestore (offline persistence = local cache), Messaging, Analytics, Crashlytics.
- Package structure follows PLAN §6.2 (`data/`, `push/`, `analytics/`, `ui/<screen>/`, `ui/components/`, `util/`).
- All analytics event names live in `analytics/Events.kt` (PLAN §6.6).
- Local state in DataStore (`LocalPrefs`): `onboardingDone`, `subscribedTopics`, `lastViewedAt{companyId}`.
- `TopicSync.sync()`: diffs the desired topics against `subscribedTopics`. It runs on app start, follow/unfollow, family change and notif toggle (< 5 s, M5).
- Every list has loading, empty and error (with retry) states.
- External links (apply, news, ReferralWorld) open in a **Custom Tab** (`util/CustomTabs.kt`).
- ReferralWorld button: label "Get referred on ReferralWorld" (D11), opens `BuildConfig.REFERRALWORLD_URL`.
  No params, deep links or per-company URLs (M8).
- Versioning: `versionCode` +1 for every APK sent out. `versionName` is `0.1.0` (closed test), `0.1.x` (fixes), `1.0.0` (first GitHub Release).
  APK name `rw-radar-<versionName>.apk`.

## 6. Poller conventions

- Python 3.12, package `poller/rwradar_poller/`, run as `python -m rwradar_poller` from `poller/`.
- Paths are resolved relative to the repo root (from `__file__`), never the CWD.
- Each ATS adapter returns `list[Job]` or raises `FetchError`. Tests run against saved real fixtures in `poller/tests/fixtures/`.
- Firestore access goes only through `store.py`, so tests can use an in-memory fake store.
- Every run writes `pollerRuns/{runId}`, including failed runs.

## 7. Secrets and signing (owner-provided; never in the repo)

- `FIREBASE_SERVICE_ACCOUNT`: GitHub Actions secret (service-account JSON).
- `app/google-services.json`: from the Firebase console, package `com.rwradar.app`.
- Release signing: `app/build.gradle.kts` reads `RWRADAR_KEYSTORE_FILE`, `RWRADAR_KEYSTORE_PASSWORD`,
  `RWRADAR_KEY_ALIAS` and `RWRADAR_KEY_PASSWORD` from `local.properties` or the environment. If they are missing, the release build is unsigned.
- `REFERRALWORLD_URL`: `https://www.referralworldcareers.com/` (confirmed by owner 2026-11-10). It can be overridden with the
  `local.properties` key `rwradar.referralworldUrl`.
- Firebase project id: `rw-radar`. The real `app/google-services.json` is in place locally (gitignored).
- **GitHub repo is PRIVATE** (owner decision 2026-11-10, overriding PLAN D5). Private repos get 2,000 free Actions
  minutes/month, and jobs (hourly) + news (every 30 min) = 72 runs/day, which can exceed that. Watch Settings → Billing → Actions usage.
  If it runs out: make the repo public (D5), or merge the jobs + news cron into one workflow.

## 8. Status log

Keep this current. One line per milestone, newest last.

- 2026-11-10: Repo scaffolded. CLAUDE.md written. Parallel build started: poller, registry, Android app, firebase/docs/CI.
- 2026-11-10: Poller done (562 pytest pass; live dry-run: 100/100 boards fetched, 2,268 India jobs). All 4 news feeds
  work (Entrackr via `/rss`). Registry: 100 companies (GH 53, Ashby 26, Lever 21; 55 India-founded); audit in
  `registry/registry_audit.csv`. Android app done (assembleDebug/Release + 38 unit tests green; Kotlin 2.3.21, AGP 8.13.2,
  Compose BOM 2026.06.01, Firebase BoM 35.1.0). Debug-only Crashlytics test crash: long-press "App version" in Settings.
  Private GitHub repo created and first push made.
- **Next (owner):** deploy firestore rules + indexes; add the `FIREBASE_SERVICE_ACCOUNT` secret; run the poll-jobs workflow
  once by hand (seeding run, no pushes); then install the debug APK and test. Replace `OWNER_CONTACT_EMAIL` in
  `app/src/main/res/values/strings.xml` and `docs/privacy.md`.
- **Known open items:** risky common-word company names (Plane, Glance, Toast, Harness, G2, Bureau…) have blocklist
  phrases, but the Day-9 manual news review is still needed. Actions minutes on a private repo (see §7).
