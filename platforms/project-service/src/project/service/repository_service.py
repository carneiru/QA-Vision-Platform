from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.project.core.config import settings
from src.project.models.project import Project
from src.project.models.repository import Repository
from src.project.schemas.repository import RepositoryCreate
from src.project.utils import repo_verifier
from src.project.utils.repo_url import parse_repo_url


class DuplicateRepository(Exception):
    pass


DUPLICATE_MESSAGE = "This repository is already attached to the project"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(moment: datetime) -> datetime:
    # SQLite returns naive datetimes even for DateTime(timezone=True); treat them as UTC
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _verify_outside_transaction(db: Session, provider: str, owner: str, name: str):
    """Call the provider with no transaction open, so a slow provider API never
    pins a database connection. Takes plain values: touching an ORM attribute
    here would reload it and reopen the transaction before the HTTP call."""
    db.rollback()  # only reads happened so far; this returns the connection to the pool
    return repo_verifier.verify(provider, owner, name, timeout=settings.REPO_VERIFY_TIMEOUT_SECONDS)


def _apply(repo: Repository, result) -> None:
    repo.verification_status = result.status
    repo.verified_at = _now()  # set whatever the outcome, so the cooldown covers failed checks too
    if result.status == repo_verifier.VERIFIED and result.default_branch and not repo.default_branch_is_user_set:
        repo.default_branch = result.default_branch


def add_repository(db: Session, project: Project, data: RepositoryCreate) -> Repository:
    parsed = parse_repo_url(data.url)  # ValueError -> 422 in the endpoint

    # Checked before calling the provider, so a duplicate spends none of the shared rate limit
    existing = (
        db.query(Repository)
        .filter_by(project_id=project.id, provider=parsed.provider, full_name_key=parsed.full_name_key)
        .first()
    )
    if existing is not None:
        raise DuplicateRepository(DUPLICATE_MESSAGE)

    repo = Repository(
        project_id=project.id,
        provider=parsed.provider,
        owner=parsed.owner,
        name=parsed.name,
        full_name_key=parsed.full_name_key,
        url=parsed.url,
        default_branch=data.default_branch or "main",
        default_branch_is_user_set=data.default_branch is not None,
    )
    # repo is not in the session yet, so its attributes survive the rollback
    _apply(repo, _verify_outside_transaction(db, repo.provider, repo.owner, repo.name))
    db.add(repo)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # a concurrent insert of the same repository won the race
        raise DuplicateRepository(DUPLICATE_MESSAGE)
    db.refresh(repo)
    return repo


def list_repositories(db: Session, project: Project) -> list[Repository]:
    return db.query(Repository).filter_by(project_id=project.id).order_by(Repository.id).all()


def get_repository(db: Session, project: Project, repo_id: int) -> Optional[Repository]:
    return db.query(Repository).filter_by(project_id=project.id, id=repo_id).first()


def reverify(db: Session, repo: Repository) -> Repository:
    cooldown = timedelta(seconds=settings.REPO_VERIFY_COOLDOWN_SECONDS)
    if repo.verified_at is not None and _now() - _aware(repo.verified_at) < cooldown:
        return repo
    provider, owner, name = repo.provider, repo.owner, repo.name
    result = _verify_outside_transaction(db, provider, owner, name)
    _apply(repo, result)  # repo reloads here, on a fresh transaction, then takes the result
    db.commit()
    db.refresh(repo)
    return repo


def delete_repository(db: Session, repo: Repository) -> None:
    db.delete(repo)
    db.commit()
