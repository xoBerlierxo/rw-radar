# RW Radar: Security and privacy audit

Date: 2026-11-11 · Scope: the whole public repo `xoBerlierxo/rw-radar` (all git history), the GitHub
Actions setup, the Firebase/Firestore configuration and the Android app (`com.rwradar.app` 0.1.0).

## Result
**No secrets or private data are exposed.** Nine issues were found and fixed. Four items need the
owner to act in the Firebase/Google Cloud console (section 3).

## 1. Checks run (and results)

| # | Check | Result |
| --- | --- | --- |
| 1 | Scan of all commits for keys and tokens (Google API keys, private keys, service-account JSON, GitHub/Slack/AWS/OpenAI tokens, passwords) | None found. The only hits were signing-config **variable names** with no values. |
| 2 | Files that must never be committed (`google-services.json`, `*adminsdk*.json`, `*.jks`, `local.properties`, `.idea`) | None ever committed. All are covered by `.gitignore`. |
| 3 | Personal data in tracked files and commit metadata | Only the owner's contact email (published on purpose for the privacy note and the commit author). No local paths, usernames or tester data. |
| 4 | Test fixtures (real ATS/RSS responses) | Public job and news data only. No personal emails or phone numbers. (The 10-digit numbers are Greenhouse job IDs.) |
| 5 | Firestore rules, tested live without auth | Public: `directory`, `companies`, `jobs`, `news` (intended). **Denied (403):** `users/{uid}`, listing `users`, `meta`, `pollerRuns`. |
| 6 | GitHub Actions: secret exposure | The secret goes only to the poll step. Fork PRs get no secrets. Default token is read-only. Inputs reach the shell as quoted env vars, so no script injection. The poller never logs credentials. |
| 7 | GitHub secret scanning and Dependabot | 0 secret alerts, 0 vulnerable-dependency alerts. |
| 8 | Android manifest (merged) | Only the launcher activity is exported. Backups are off. Cleartext is not used (Firebase is HTTPS only). |

## 2. Issues found and fixed

| # | Severity | Issue | Fix |
| --- | --- | --- | --- |
| F1 | **High (compliance)** | Firebase Analytics added the **Advertising ID** permission (`AD_ID`) and ad-attribution permissions, which contradicted the privacy note. | Permissions removed in the manifest (`tools:node="remove"`). Ad ID, Android ID (SSAID) and ad-personalization collection are turned off. The privacy note now states that the Advertising ID is not collected. Verified in the merged release manifest. |
| F2 | **High (supply chain)** | The poll jobs (which hold the Firebase admin key) installed unpinned Python packages, so a compromised release could steal the key. | All 43 packages (42 + colorama on Windows) are pinned to exact versions in `poller/requirements-lock.txt` and installed with `--no-deps`. Verified with a clean install, `pip check` and 572 tests. |
| F3 | Medium | GitHub Actions were referenced by mutable tags (`@v4`). | Pinned to full commit SHAs. |
| F4 | Medium | `actions/checkout` left a GitHub token in `.git/config` on the runner. | `persist-credentials: false`. |
| F5 | Medium | GitHub secret scanning, push protection and Dependabot were off. | All enabled, plus Dependabot security updates and `.github/dependabot.yml` (pip, actions, gradle). |
| F6 | Medium | `MainActivity` is exported (launcher), and any app could send it a crafted `companyId` that becomes a Firestore path. | `PushTarget.parse` validates every extra (slug regex, family keys, 40-hex hash, positive `since`). Unit tests added. |
| F7 | Low | `users/{uid}` rules checked only the field names, so a user could store arbitrary values. | The rules now enforce types: `families` uses only the 6 keys, `notifPrefs` is `{jobs, signals}` as booleans, `createdAt` is a timestamp, and `follows` is bounded. **Owner must deploy** (section 3). |
| F8 | Low | The debug log printed the user's search text. | Logged only in debug builds, without the query. |
| F9 | Low | Workflows from outside contributors' PRs ran after a first approval. | Approval is now required for all outside contributors. |

## 3. Owner actions (console, can't be done from the repo)

1. **Deploy the updated Firestore rules** (F7). Paste `firebase/firestore.rules` into Firestore → Rules → Publish, or run
   `firebase deploy --only firestore:rules --config firebase/firebase.json --project rw-radar`.
2. **Restrict the Android API key.** Google Cloud console → APIs & Services → Credentials → the "Android key (auto created by Firebase)":
   restrict it to Android apps with package `com.rwradar.app` plus your debug and release SHA-1 fingerprints. This key is in every
   APK by design (it is not a secret), so the restriction limits misuse.
3. **Least-privilege poller key (recommended).** The current key is the default `firebase-adminsdk` account, which has broad admin
   rights. Create a dedicated service account with only *Cloud Datastore User* + *Firebase Cloud Messaging API Admin*, put its key
   in the `FIREBASE_SERVICE_ACCOUNT` secret, then delete the old key under IAM → Service accounts → Keys.
4. **Protect the local key file.** The downloaded key under `D:\Sketch\` grants admin access to the project. Move it into your password
   manager (or delete it, since GitHub already has it) so it can't leak from your PC.

## 4. Accepted risks (MVP)

- **Public read of jobs/news/directory** is intended (spec §7). Someone could script reads to use up the Spark free read quota for a day.
  The Spark plan has no billing, so the worst case is a temporary outage. Firebase App Check would block this, but Play Integrity
  doesn't recognize sideloaded APKs, so it is deferred until a Play Store release.
- **Anonymous Auth:** anyone can create an anonymous user and write their own `users/{uid}` doc (bounded by the rules in F7).
  No one can read anyone else's.
- **Owner email in commit metadata and the privacy note:** published on purpose. Use a GitHub `noreply` address for future
  commits if you prefer (`git config user.email <id>+<user>@users.noreply.github.com`).
