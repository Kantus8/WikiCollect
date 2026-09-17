"""Wikimedia sync command and deliberately single-worker local scheduler."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Match the server's optional local environment configuration.
from dotenv import load_dotenv
if __name__ == "__main__":
    load_dotenv(ROOT / ".env")

from sqlalchemy import func, select
from backend.wikidex.db import SessionLocal, init_db
from backend.wikidex.ingestion import WikimediaClient, last_complete_month, run_report, sync_catalogue
from backend.wikidex.models import Card, IngestionItem, IngestionRun


@contextmanager
def worker_lock():
    """OS locks are released on crash, unlike stale exclusive-created lock files."""
    path = ROOT / "data" / "ingestion.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Another catalogue worker is already running in this workspace") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def resumable_run(month: str) -> int | None:
    """Resume only the latest interrupted full pass of the current catalogue.

    A finished pass with errors has already tried every article. Starting a new
    pass next cycle also refreshes successful pages and picks up catalogue
    additions, even when another article remains permanently blocked.
    """
    with SessionLocal() as session:
        run = session.scalar(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(1))
        if run is None or run.status != "running":
            return None
        detail = json.loads(run.detail)
        if detail.get("month") != month:
            return None
        if detail.get("version") == 2:
            item_cards = select(IngestionItem.card_id).where(IngestionItem.run_id == run.id)
            item_count = session.scalar(select(func.count()).select_from(IngestionItem).where(IngestionItem.run_id == run.id))
            card_count = session.scalar(select(func.count()).select_from(Card))
            missing = session.scalar(select(Card.id).where(~Card.id.in_(item_cards)).limit(1))
            if item_count == card_count and missing is None:
                return run.id
        elif detail.get("version") == 1:
            # sync_catalogue upgrades legacy checkpoints when they are resumed.
            item_ids = {item["card_id"] for item in detail.get("items", [])}
            if item_ids == set(session.scalars(select(Card.id))):
                return run.id
    return None


def progress(item: dict) -> None:
    print(json.dumps(item, ensure_ascii=False), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and enrich the Wikidex catalogue using Wikimedia's read-only APIs.")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("sync", "worker"):
        run = sub.add_parser(command)
        run.add_argument("--month", help="YYYY-MM, defaults to last complete UTC month")
        run.add_argument("--user-agent", default=None, help="Identifiable User-Agent including your contact URL/email")
        run.add_argument("--report", type=Path, help="Write the full durable run report as JSON")
        run.add_argument("--min-interval", type=float, default=0.5, help="Minimum seconds between HTTP requests")
    sync = sub.choices["sync"]
    sync.add_argument("--title", action="append", help="Restrict to an existing title; repeat this option")
    sync.add_argument("--resume", type=int, help="Resume an interrupted/failed run; completed items are skipped")
    worker = sub.choices["worker"]
    worker.add_argument("--interval", type=float, default=86400, help="Seconds between completed jobs (minimum 60)")
    worker.add_argument("--max-runs", type=int, help="Optional finite number of worker cycles")
    status = sub.add_parser("status")
    status.add_argument("--id", type=int, help="Full report for one run; otherwise display last ten runs")
    args = parser.parse_args(argv)
    if args.command == "worker" and args.interval < 60:
        parser.error("--interval must be at least 60 seconds")
    if args.command == "worker" and args.max_runs is not None and args.max_runs < 1:
        parser.error("--max-runs must be positive")
    if args.command == "sync" and args.resume and args.title:
        parser.error("--resume retains its original titles; do not combine with --title")
    init_db()
    if args.command == "status":
        with SessionLocal() as session:
            if args.id is not None:
                run = session.get(IngestionRun, args.id)
                if run is None:
                    parser.error("Unknown run")
                print(json.dumps(run_report(session, run.id), ensure_ascii=False, indent=2))
            else:
                for run in session.scalars(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(10)):
                    print(json.dumps({"id": run.id, "status": run.status, "processed": run.processed,
                                      "failed": run.failed, "finished_at": run.finished_at}))
        return 0
    try:
        with worker_lock():
            cycle = 0
            while True:
                month = args.month or last_complete_month()
                resume = args.resume if args.command == "sync" else resumable_run(month)
                with WikimediaClient(user_agent=args.user_agent, min_interval=args.min_interval) as client:
                    report = sync_catalogue(SessionLocal, client, titles=args.title if args.command == "sync" else None,
                                            month=args.month if resume else month, resume_run_id=resume, on_progress=progress)
                if args.report:
                    args.report.parent.mkdir(parents=True, exist_ok=True)
                    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps({key: report[key] for key in ("id", "status", "processed", "failed")}), flush=True)
                cycle += 1
                if args.command == "sync" or (args.max_runs and cycle >= args.max_runs):
                    return 1 if report["failed"] else 0
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped; the current run can be resumed from its last committed article.", file=sys.stderr)
        return 130
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
