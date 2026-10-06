from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session, sessionmaker

from src.ingestion.api.deps import get_db
from src.ingestion.api.key_auth import get_api_key
from src.ingestion.models import ApiKey
from src.ingestion.schemas.collect import KeyCheck, RunReceipt, RunUpload
from src.ingestion.service import ingest_service, notification_service, run_service
from src.ingestion.utils import metrics

router = APIRouter()  # mounted at /collect


@router.get("/key", response_model=KeyCheck)
def check_key(key: ApiKey = Depends(get_api_key)):
    """Proof the key works, for `qav-collector check` — uploads nothing."""
    return key


@router.post("/runs", response_model=RunReceipt, status_code=status.HTTP_201_CREATED)
def collect_run(
    upload: RunUpload,
    response: Response,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    key: ApiKey = Depends(get_api_key),
    idempotency_key: Optional[str] = Header(
        None, alias="Idempotency-Key", min_length=1, max_length=255, pattern=r"^[\x21-\x7e]+$"
    ),
):
    with metrics.DURATION.time():
        try:
            run, created = ingest_service.ingest(db, key, upload, idempotency_key)
        except ingest_service.IdempotencyConflict:
            metrics.REJECTED.labels(reason="conflict").inc()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Idempotency-Key reused with a different payload"
            )
    if created:
        metrics.RUNS.inc()
        metrics.RESULTS.inc(run.total)
        if run.failed + run.errored:
            # After the response: the collector never waits on Slack or Teams
            background.add_task(notification_service.notify_run, sessionmaker(bind=db.get_bind()), run.id)
    else:
        response.status_code = status.HTTP_200_OK
    return RunReceipt.model_validate(run).model_copy(update=run_service.quarantine_counts(db, run))
