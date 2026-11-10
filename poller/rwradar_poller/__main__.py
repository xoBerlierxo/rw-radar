"""CLI: ``python -m rwradar_poller {jobs|news|validate-registry} [flags]``.

    jobs  [--dry-run] [--no-push] [--company ID]
    news  [--dry-run] [--no-push] [--company ID] [--google-news auto|always|never]
    validate-registry [--check-endpoints]

``--dry-run``: fetch for real, diff against Firestore read-only (or an empty store without
credentials), print the writes and pushes it would make. Nothing is written, nothing is sent.
``--no-push``: real Firestore writes, pushes are only logged (throttle timestamps untouched).

Exit codes: 0 ok; 1 the run could not start or every source failed; 2 bad usage/registry.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import config, registry
from .http import HttpClient
from .jobs_sync import run_jobs
from .models import utcnow
from .news.matcher import Blocklist, BlocklistError, Matcher
from .news.news_sync import run_news
from .push import DisabledPusher, DryRunPusher, FcmPusher, Pusher
from .runlog import RunLog
from .store import Store, open_store

log = logging.getLogger("rwradar_poller")


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true", help="no Firestore writes, no pushes; print them")
    common.add_argument("--no-push", action="store_true", help="write to Firestore but do not send pushes")
    common.add_argument("--company", metavar="ID", help="only this registry company")
    common.add_argument("-v", "--verbose", action="store_true", help="debug logging")

    parser = argparse.ArgumentParser(prog="python -m rwradar_poller", description="RW Radar poller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("jobs", parents=[common], help="poll ATS job boards")
    news = sub.add_parser("news", parents=[common], help="poll news feeds")
    news.add_argument("--google-news", choices=("auto", "always", "never"), default="auto",
                      help="auto = every 2nd run (see news_sync.py)")
    validate = sub.add_parser("validate-registry", help="check registry/companies.json and the blocklist")
    validate.add_argument("--check-endpoints", action="store_true", help="also require HTTP 200 from every board")
    validate.add_argument("-v", "--verbose", action="store_true")
    return parser


def _make_pusher(store: Store, opts: config.RunOptions) -> Pusher:
    if opts.dry_run:
        return DryRunPusher(debug_all=opts.debug_all)
    if opts.no_push:
        return DisabledPusher(debug_all=opts.debug_all)
    return FcmPusher(debug_all=opts.debug_all, transport=store.push_transport())


def _write_failed_run(store: Store | None, kind: str, message: str) -> None:
    """Every run writes pollerRuns/{runId}, including runs that fail before they start."""
    if store is None:
        return
    started = utcnow()
    run = RunLog(kind, started)
    run.error(message)
    try:
        store.write_run(run.run_id, run.to_doc(utcnow()))
    except Exception:  # noqa: BLE001
        log.exception("could not write run log")


def _cmd_sync(kind: str, args: argparse.Namespace) -> int:
    opts = config.RunOptions(
        dry_run=args.dry_run,
        no_push=args.no_push,
        company=args.company,
        debug_all=config.debug_all_enabled(),
        google_news=getattr(args, "google_news", "auto"),
    )
    store: Store | None = None
    try:
        store = open_store(opts.dry_run)
        companies = registry.load()
        selected = registry.select(companies, opts.company)
        blocklist = Blocklist.load() if kind == "news" else None
    except (registry.RegistryError, BlocklistError) as exc:
        log.error("%s", exc)
        _write_failed_run(store, kind, str(exc))
        return 2
    except Exception as exc:  # noqa: BLE001 - e.g. bad credentials
        log.exception("could not start the %s run", kind)
        _write_failed_run(store, kind, f"{type(exc).__name__}: {exc}")
        return 1

    pusher = _make_pusher(store, opts)
    client = HttpClient()
    if kind == "jobs":
        run = run_jobs(companies, selected, store=store, client=client, pusher=pusher)
    else:
        matcher = Matcher(companies, blocklist)
        run = run_news(
            companies, selected, store=store, client=client, pusher=pusher, matcher=matcher,
            google_mode=opts.google_news,
        )
    log.info("%s run %s: %s", kind, run.run_id, run.counts)
    for err in run.errors[:20]:
        log.info("  error: %s", err)
    if run.counts["fetched"] == 0 and run.counts["failedFetches"] > 0:
        return 1  # every source failed: make the workflow run red
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    report = registry.ValidationReport()
    companies: list = []
    try:
        data = registry.load_raw()
        report = registry.validate_data(data)
        if report.ok:
            companies = registry.load()
    except registry.RegistryError as exc:
        report.errors.append(str(exc))
    try:
        blocklist = Blocklist.load()
        known = {c.id for c in companies}
        for cid in sorted(blocklist.company_ids - known) if companies else []:
            report.warnings.append(f"news_blocklist.json: companyId {cid!r} is not in the registry")
    except BlocklistError as exc:
        report.errors.append(f"news_blocklist.json: {exc}")
    if args.check_endpoints and companies:
        print(f"Checking {len(companies)} ATS endpoints (1 req/s per host)...")
        registry.check_endpoints(companies, HttpClient(), report)
    for w in report.warnings:
        print(f"WARNING: {w}")
    for e in report.errors:
        print(f"ERROR: {e}")
    print(f"{len(companies)} companies, {len(report.errors)} errors, {len(report.warnings)} warnings")
    return 0 if report.ok else 2


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    for noisy in ("urllib3", "google", "grpc"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if args.command == "validate-registry":
        return _cmd_validate(args)
    return _cmd_sync(args.command, args)


if __name__ == "__main__":
    sys.exit(main())
