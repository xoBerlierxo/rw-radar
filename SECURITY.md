# Security policy

## Reporting a vulnerability
Please email **somshekharpandey@gmail.com** with the subject "RW Radar security". Don't open a public issue.
You will get a reply within 3 working days.

## What is (and isn't) in this repository
This repository is public. It contains **no secrets**:
- `app/google-services.json`, Firebase service-account keys, release keystores and `local.properties` are
  git-ignored and have never been committed. History was scanned on 2026-11-11 (see `docs/security-audit.md`).
- The poller reads its Firebase credentials only from the GitHub Actions secret `FIREBASE_SERVICE_ACCOUNT`.
- GitHub secret scanning with push protection is on, so commits containing known secret formats are blocked.

## Rules for contributors
- Never commit credentials, keys or personal data. Put new secrets in GitHub Actions secrets.
- The poller workflows hold the Firebase admin key. Dependencies are installed from the exact pins in
  `poller/requirements-lock.txt`, and actions are pinned by commit SHA. Review dependency updates (Dependabot PRs) before merging.
- Workflows from outside contributors' pull requests need maintainer approval and never receive secrets.
