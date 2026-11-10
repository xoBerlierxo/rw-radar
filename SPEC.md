# SPEC: RW Radar (working name)

Hiring-signal companion app for ReferralWorld Careers
Version 0.3 (MVP for closed testing, ready to build) · 10 Nov 2026 · Owner: Somshekhar Pandey

## 1. Summary

RW Radar is an Android app where a job seeker follows companies and is
notified when those companies post matching roles or show a hiring signal
such as a funding round.

This spec covers one deliverable: a minimum working app, handed to a
closed group of testers as an APK.

Decisions already taken:
- Solo build, under 3 weeks, free tiers only.
- Native Android in Kotlin with Jetpack Compose.
- Standalone app. No connection to ReferralWorld's database.
- Google Play registration and store publishing are out of scope.
- Future releases after the MVP are distributed through GitHub.

## 2. Users and value

Primary user: tech job seeker in India with 0–4 years of experience
(ReferralWorld's stated audience).

User problem: openings at good startups fill fast, and the user finds
out late. Funding news, which predicts hiring, sits in a different app
from job listings.

Value to ReferralWorld:
- A push-notification channel that can bring users back to the platform.
- A company-interest dataset (which companies users follow).

Success metrics for the final presentation:
| Metric | Target |
| --- | --- |
| Closed-test testers | 12+ |
| Companies tracked | 100 |
| Median delay, job posted to push sent | under 90 minutes |
| Notification open rate | 25%+ |
| Crash-free sessions | 99%+ |

## 3. Scope

### MVP (must ship)
- M1 Company directory with search
- M2 Follow / unfollow companies
- M3 Openings per company, from public job-board APIs
- M4 Push notification for new matching openings
- M5 Role-family preferences (the minimal "profile")
- M6 News per company, with funding/layoff tags
- M7 Hiring-signal notification on funding news
- M8 "Get referred on ReferralWorld" button (plain link only)
- M9 Onboarding, settings, privacy note

### Out of scope for this MVP
- Google Play registration, store listing, production release
- Stock prices and price alerts
- Google sign-in and syncing follows across devices
- UTM tracking, deep links or any integration with ReferralWorld
  (pending their approval of the MVP)
- Full profile and résumé-based matching
- Job sources beyond Greenhouse, Lever and Ashby
- Open-web discovery of hiring websites
- In-app article reading
- iOS

## 4. Features and acceptance criteria

### M1 Directory
- Lists all companies with name, sector, open-role count, last funding tag.
- Search by name returns results in under 300 ms from local cache.
- Sort options: Most new roles this week, Recently funded, A–Z.

### M2 Follow
- One tap to follow/unfollow from list and detail screens.
- Follows are stored against an anonymous ID and survive app restarts.
- Following subscribes the device to that company's push topics.

### M3 Openings
- Each job shows title, location, department, posted date, apply link.
- Apply link opens the company's own posting in a Custom Tab.
- A job missing from two consecutive polls is marked closed and hidden.
- In-list filters: role family, location text, remote only.

### M4 New-opening notification
- Sent only for jobs first seen in the current poll.
- Grouped: one push per company per role family per poll
  ("3 new Engineering roles at <Company>").
- Tapping opens the company's Openings tab with new jobs highlighted.
- At most one push per company per role family every 6 hours.

### M5 Role preferences
- User picks one or more families at onboarding:
  Engineering, Data, Design, Product, Marketing/Sales, Other.
- The poller classifies each job title into a family by keyword rules.
- Changing preferences re-subscribes topics within 5 seconds.

### M6 News
- Each item shows headline, source name, published time, tag.
- Tags by keyword rules: Funding, Layoffs, Acquisition, Financials, Other.
- Tapping opens the publisher's page. No article body is stored or shown.
- Items are matched to companies by name and alias list.

### M7 Hiring-signal notification
- Triggered when a Funding-tagged item matches a followed company.
- Copy: "<Company> raised funding. <N> open roles right now."
- Max one per company per 7 days.

### M8 ReferralWorld button
- Button on every company detail screen.
- Opens the ReferralWorld Careers homepage in a Custom Tab.
- No tracking parameters, deep links or per-company URLs in this MVP.

### M9 Onboarding and settings
- Onboarding: pick role families, follow at least 3 companies,
  grant notification permission (Android 13+ runtime prompt).
- Settings: notification toggles per signal type, role preferences,
  privacy note, app version.

## 5. Data sources

| Signal | Source | Access | Poll rate |
| --- | --- | --- | --- |
| Jobs | Greenhouse Job Board API | Public, no key | Hourly |
| Jobs | Lever Postings API | Public, no key | Hourly |
| Jobs | Ashby Job Posting API | Public, no key | Hourly |
| News | Startup news sites (Entrackr, Inc42, YourStory) | RSS where offered | 30 min |
| News | Google News RSS, query per company | Public RSS | 2 hours |

Endpoints:
- boards-api.greenhouse.io/v1/boards/{token}/jobs
- api.lever.co/v0/postings/{company}?mode=json
- api.ashbyhq.com/posting-api/job-board/{name}

Rules:
- The phone never calls these sources. Only the poller does.
- Poller sends a descriptive User-Agent and at most 1 request/second/host.
- News sources are interchangeable. A site with no usable feed on
  Day 1 is dropped; the MVP needs at least two working sources.

Company registry: a JSON file in the repo, 100 entries, hand-curated.
Fields: id, name, aliases[], sector, website, ats{type, token}, logoUrl.

## 6. Architecture and stack

Android app
- Kotlin, Jetpack Compose, single-activity, MVVM with ViewModel + Flow.
- Firebase SDKs: anonymous Auth, Firestore with offline persistence as
  the local cache, Cloud Messaging, Analytics, Crashlytics.
- Min SDK 26.

Backend (no server to run)
- Firestore on the free Spark plan holds all data.
- Poller: one Python script using firebase-admin, run by a GitHub
  Actions scheduled workflow (hourly for jobs, 30 min for news).
- Poller diffs fetched data against Firestore, writes only changes,
  then sends FCM topic messages.

Why this shape:
- Scheduled Cloud Functions need a paid plan; GitHub Actions cron is free.
- FCM topics avoid storing device tokens or per-user fan-out.

Push topics: c_{companyId}_{roleFamily} for jobs,
c_{companyId}_signal for funding news.

Free-tier guardrails (confirm current quotas on Day 1):
- List queries limited to 20 documents per page.
- Poller writes only new, changed or closed jobs.
- GitHub cron can run late; the 90-minute target allows for that.

## 7. Data model (Firestore)

- companies/{id}: registry fields + openCount, newThisWeek,
  lastFundingAt, lastPolledAt
- companies/{id}/jobs/{jobId}: title, family, location, remote, dept,
  url, firstSeenAt, lastSeenAt, missCount, status(open|closed)
- news/{hash}: title, source, url, publishedAt, tag, companyIds[]
- users/{uid}: follows[], families[], notifPrefs, createdAt
- meta/pollerRuns/{runId}: startedAt, durationMs, counts, errors[]

Security rules: public read on companies, jobs, news.
users/{uid} readable and writable only by that uid. All other writes
only from the poller's service account.

## 8. Screens

1. Onboarding (3 steps)
2. Discover: directory, search, sort
3. Following: followed companies with unread signal counts
4. Company detail: header, Follow, ReferralWorld button,
   tabs Openings / News
5. Settings

## 9. Release plan

- Closed test: a signed release APK shared directly with invited
  testers, with a one-page install guide (allow installs from the
  source, then open the APK).
- Feedback: one shared form for bugs and comments, plus Crashlytics.
- Later releases: published as GitHub Releases with version notes.
- Every build uses the same signing key so updates install over the
  previous version.

## 10. Schedule (18 working days)

| Day | Work |
| --- | --- |
| 1 | Spikes: 3 job APIs on 5 Indian companies, news feed availability. Firebase project. |
| 2–3 | Registry of 100 companies. Poller v1 (jobs to Firestore). App skeleton with Discover. |
| 4–6 | Follow, company detail, Openings tab, FCM topics, new-job push end to end. |
| 7–9 | News ingest, matching, tags, funding signal push. |
| 10–11 | Onboarding, settings, ReferralWorld button, analytics, Crashlytics. |
| 12 | Polish, empty and error states, privacy note, signed APK, install guide. |
| 13 | Closed test starts: APK to testers. |
| 14–16 | Fix tester feedback, ship updated APKs. |
| 17 | Capture metrics, tag the MVP as the first GitHub Release. |
| 18 | Presentation: demo, metrics, roadmap. |

Cut order if behind: news filters and sort options, the Following
screen's unread counts, M7, then M6.

## 11. Risks

| Risk | Mitigation |
| --- | --- |
| Few Indian startups on the 3 job APIs | Day 1 spike; pick registry from those that are |
| A news site has no feed or forbids reuse | Drop it; Google News RSS covers every company |
| News matched to wrong company | Alias list, exact-phrase match, manual blocklist |
| Testers struggle to sideload the APK | Install guide with screenshots |
| OEM battery savers delay pushes | Notification-type FCM messages, high priority |
| Firestore free quota exceeded | Pagination, diff-only writes, quota alert |

Legal and privacy:
- News: headline, source and link only. No scraping of article bodies.
- Brand: confirm you may use the ReferralWorld name on the button.
- Data collected: anonymous ID, follows, role preferences, analytics
  events. No résumé or contact data.
