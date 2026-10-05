"""Re-mask stored results with the masking ingest applies today.

    python -m src.ingestion.jobs.remask [--dry-run] [--project ID] [--batch-size N]

For results stored before masking existed, or before a pattern was added. Masking skips what is
already masked, so a second pass changes nothing and the command is safe to repeat. Rows are
walked by id in batches, each committed on its own, so a long pass never holds one huge
transaction and can be stopped and run again.
"""
import argparse
import json
import sys
from collections import Counter
from typing import List, Optional

from sqlalchemy.orm import Session, sessionmaker

from src.ingestion.core.config import settings
from src.ingestion.models import Run, RunResult
from src.ingestion.service.ingest_service import CI_RUN_URL_LENGTH, mask, truncate_utf8


def _remask_text(text: Optional[str], kinds: Counter) -> tuple[Optional[str], bool, bool]:
    """(new text, changed, cut). Masking can lengthen text past the stored limit: cut it back."""
    masked, found = mask(text)
    if not found:
        return text, False, False
    kinds.update(found)
    masked, cut = truncate_utf8(masked, settings.MAX_TEXT_BYTES)
    return masked, True, cut


def _results_pass(db: Session, project_id: Optional[int], batch_size: int, dry_run: bool, kinds: Counter) -> tuple[int, int]:
    scanned = changed = 0
    last_id = 0
    while True:
        query = db.query(RunResult).filter(RunResult.id > last_id)
        if project_id is not None:
            query = query.join(Run, Run.id == RunResult.run_id).filter(Run.project_id == project_id)
        batch = query.order_by(RunResult.id).limit(batch_size).all()
        if not batch:
            return scanned, changed
        for row in batch:
            scanned += 1
            row_kinds: Counter = Counter()
            message, message_changed, message_cut = _remask_text(row.message, row_kinds)
            details, details_changed, details_cut = _remask_text(row.details, row_kinds)
            if not (message_changed or details_changed):
                continue
            changed += 1
            # A result counts once per kind, the way ingest's metrics count it
            kinds.update({kind: 1 for kind in row_kinds})
            if not dry_run:
                row.message, row.details = message, details
                row.redacted = True
                row.truncated = row.truncated or message_cut or details_cut
        last_id = batch[-1].id
        if dry_run:
            db.rollback()
        else:
            db.commit()


def _runs_pass(db: Session, project_id: Optional[int], dry_run: bool, kinds: Counter) -> int:
    query = db.query(Run).filter(Run.ci_run_url.isnot(None))
    if project_id is not None:
        query = query.filter(Run.project_id == project_id)
    changed = 0
    for run in query.yield_per(500):
        masked, found = mask(run.ci_run_url)
        if not found:
            continue
        changed += 1
        kinds.update({kind: 1 for kind in found})
        if not dry_run:
            run.ci_run_url = masked[:CI_RUN_URL_LENGTH]
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return changed


def run_pass(db: Session, *, project_id: Optional[int], batch_size: int, dry_run: bool) -> dict:
    kinds: Counter = Counter()
    scanned, results_changed = _results_pass(db, project_id, batch_size, dry_run, kinds)
    runs_changed = _runs_pass(db, project_id, dry_run, kinds)
    return {
        "event": "remask",
        "project_id": project_id,
        "results_scanned": scanned,
        "results_changed": results_changed,
        "runs_changed": runs_changed,
        "kinds": dict(sorted(kinds.items())),
        "dry_run": dry_run,
    }


def main(argv: Optional[List[str]] = None, *, session_factory: Optional[sessionmaker] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.ingestion.jobs.remask",
        description="Re-apply today's masking to results already stored. Safe to repeat.",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would change; change nothing")
    parser.add_argument("--project", type=int, metavar="ID", help="only this project's results")
    parser.add_argument("--batch-size", type=int, default=500, metavar="N", help="rows per transaction (default 500)")
    args = parser.parse_args(argv)
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")

    if session_factory is None:
        from src.ingestion.db.session import SessionLocal

        session_factory = SessionLocal
    try:
        with session_factory() as db:
            summary = run_pass(db, project_id=args.project, batch_size=args.batch_size, dry_run=args.dry_run)
    except Exception as exc:  # report and fail; everything committed so far stays masked
        print(json.dumps({"event": "remask_failed", "error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 1
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
