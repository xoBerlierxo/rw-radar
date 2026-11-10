# RW Radar

A hiring-signal companion app for ReferralWorld Careers. Follow companies and get a push when they post
roles in your field or raise funding.

- **App**: Android (Kotlin, Jetpack Compose), in [`app/`](app/)
- **Poller**: Python, run by GitHub Actions cron, in [`poller/`](poller/). It fetches Greenhouse/Lever/Ashby job
  boards and startup-news RSS, writes changes to Firestore, and sends FCM topic pushes.
- **Data**: Firebase (Firestore, Anonymous Auth, Cloud Messaging, Analytics, Crashlytics) on the free Spark plan.
- **Companies**: [`registry/companies.json`](registry/companies.json), 100 hand-curated entries.

Docs: [SPEC.md](SPEC.md) · [PLAN.md](PLAN.md) · [Install guide](docs/install-guide.md) ·
[Privacy](docs/privacy.md) · [Changelog](CHANGELOG.md)

## Development

```bash
# Android: needs app/google-services.json from the Firebase console (not committed)
./gradlew :app:assembleDebug

# Poller
cd poller && python -m pip install -r requirements.txt && python -m pytest -q
python -m rwradar_poller jobs --dry-run
```

Secrets (`google-services.json`, the service-account key, the release keystore) are never committed. The
poller reads the service account from the `FIREBASE_SERVICE_ACCOUNT` GitHub Actions secret.

## Firebase rules and indexes

```bash
cd firebase
firebase deploy --only firestore:rules,firestore:indexes --project <project-id>
```
