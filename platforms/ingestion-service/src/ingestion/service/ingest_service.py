import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.ingestion.core.config import settings
from src.ingestion.models import ApiKey, Run, RunResult
from src.ingestion.schemas.collect import RunUpload


class IdempotencyConflict(Exception):
    pass


def truncate_utf8(text: Optional[str], limit: int) -> tuple[Optional[str], bool]:
    """Cut to at most `limit` UTF-8 bytes without splitting a character."""
    if text is None:
        return None, False
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True


def test_key(suite: str, class_name: str, name: str) -> str:
    """Stable identity of a test across runs; the NUL separator keeps ("a","bc") and ("ab","c") apart."""
    return hashlib.sha256(f"{suite}\0{class_name}\0{name}".encode("utf-8")).hexdigest()


test_key.__test__ = False  # not a pytest test, despite the name


def _request_hash(upload: RunUpload) -> str:
    canonical = json.dumps(upload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _existing(db: Session, project_id: int, idempotency_key: str) -> Optional[Run]:
    return db.query(Run).filter(Run.project_id == project_id, Run.idempotency_key == idempotency_key).first()


def _replay(run: Run, request_hash: str) -> tuple[Run, bool]:
    if run.request_hash != request_hash:
        raise IdempotencyConflict()
    return run, False


def ingest(db: Session, key: ApiKey, upload: RunUpload, idempotency_key: Optional[str]) -> tuple[Run, bool]:
    request_hash = _request_hash(upload)
    if idempotency_key is not None:
        existing = _existing(db, key.project_id, idempotency_key)
        if existing is not None:
            return _replay(existing, request_hash)

    counts = Counter(result.status for result in upload.results)
    meta = upload.run
    run = Run(
        project_id=key.project_id,
        api_key_id=key.id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        ci_provider=meta.ci_provider,
        ci_run_url=meta.ci_run_url,
        commit_sha=meta.commit_sha,
        branch=meta.branch,
        environment=meta.environment,
        agent_version=meta.agent_version,
        started_at=meta.started_at,
        finished_at=meta.finished_at,
        duration_ms=int((meta.finished_at - meta.started_at).total_seconds() * 1000),
        total=len(upload.results),
        passed=counts["passed"],
        failed=counts["failed"],
        skipped=counts["skipped"],
        errored=counts["errored"],
    )
    try:
        db.add(run)
        db.flush()  # assigns run.id inside the transaction

        rows = []
        for result in upload.results:
            message, cut_message = truncate_utf8(result.message, settings.MAX_TEXT_BYTES)
            details, cut_details = truncate_utf8(result.details, settings.MAX_TEXT_BYTES)
            rows.append({
                "run_id": run.id,
                "test_key": test_key(result.suite, result.class_name, result.name),
                "suite": result.suite,
                "class_name": result.class_name,
                "name": result.name,
                "status": result.status,
                "duration_ms": result.duration_ms,
                "message": message,
                "details": details,
                "truncated": cut_message or cut_details,
                "file": result.file,
            })
        db.execute(insert(RunResult), rows)  # one executemany, not 20,000 ORM objects

        key.last_used_at = datetime.now(timezone.utc)
        db.commit()
    except IntegrityError:
        db.rollback()
        # Two uploads raced with the same Idempotency-Key and this one lost: answer as if it had
        # arrived second
        if idempotency_key is not None:
            existing = _existing(db, key.project_id, idempotency_key)
            if existing is not None:
                return _replay(existing, request_hash)
        raise
    db.refresh(run)
    return run, True
