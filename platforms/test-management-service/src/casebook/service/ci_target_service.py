"""A project's CI target (where Play dispatches) and its audit trail."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.casebook.models import CiTarget, CiTargetEvent, RunRequest
from src.casebook.models.ci import ACTIVE_STATUSES
from src.casebook.utils import github_client, secret_box


class TokenRequired(Exception):
    """The first save of a target must carry a token."""


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_target(db: Session, project_id: int) -> Optional[CiTarget]:
    return db.get(CiTarget, project_id)


def _last_change(db: Session, project_id: int) -> Optional[CiTargetEvent]:
    return (db.query(CiTargetEvent).filter(CiTargetEvent.project_id == project_id)
            .order_by(CiTargetEvent.at.desc(), CiTargetEvent.id.desc()).first())


def out(db: Session, project_id: int) -> dict:
    row = get_target(db, project_id)
    change = _last_change(db, project_id)
    body = {
        "available": secret_box.is_available(), "configured": row is not None,
        "last_change": {"action": change.action, "user_id": change.user_id, "at": change.at} if change else None,
    }
    if row is not None:
        body.update(provider=row.provider, repo=row.repo, workflow=row.workflow, ref=row.ref,
                    token_last4=row.token_last4, token_expires_at=row.token_expires_at, updated_at=row.updated_at)
    return body


def has_active_run(db: Session, project_id: int) -> bool:
    return db.query(RunRequest.id).filter(
        RunRequest.project_id == project_id, RunRequest.status.in_(ACTIVE_STATUSES)).first() is not None


def save_target(db: Session, project_id: int, user_id: int, repo: str, workflow: str, ref: str,
                token: Optional[str]) -> CiTarget:
    """Checks the token with GitHub before anything is stored. Raises secret_box.SecretsUnavailable,
    TokenRequired and github_client.GitHubError (RateLimited included)."""
    if not secret_box.is_available():
        raise secret_box.SecretsUnavailable(secret_box.NOT_CONFIGURED)
    row = get_target(db, project_id)
    if token is None and row is None:
        raise TokenRequired()
    plain = token if token is not None else secret_box.decrypt(row.token_encrypted)
    expires = github_client.check_target(plain, repo, workflow)
    try:
        return _write_target(db, row, project_id, user_id, repo, workflow, ref, token, plain, expires)
    except IntegrityError:  # two first saves raced: the other one inserted the row, so this one updates it
        db.rollback()
        row = get_target(db, project_id)
        if row is None:
            raise
        return _write_target(db, row, project_id, user_id, repo, workflow, ref, token, plain, expires)


def _write_target(db: Session, row: Optional[CiTarget], project_id: int, user_id: int, repo: str, workflow: str,
                  ref: str, token: Optional[str], plain: str, expires: Optional[datetime]) -> CiTarget:
    action = "created" if row is None else ("token_replaced" if token is not None else "updated")
    if row is None:
        row = CiTarget(project_id=project_id, provider="github")
        db.add(row)
    row.repo, row.workflow, row.ref = repo, workflow, ref
    if token is not None:
        row.token_encrypted, row.token_last4 = secret_box.encrypt(plain), plain[-4:]
    row.token_expires_at = expires
    row.updated_by, row.updated_at = user_id, now()
    db.add(CiTargetEvent(project_id=project_id, user_id=user_id, action=action, at=row.updated_at))
    db.commit()
    return row


def delete_target(db: Session, project_id: int, user_id: int) -> bool:
    row = get_target(db, project_id)
    if row is None:
        return False
    db.delete(row)
    db.add(CiTargetEvent(project_id=project_id, user_id=user_id, action="deleted", at=now()))
    db.commit()
    return True
