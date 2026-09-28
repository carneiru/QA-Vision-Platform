import re
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.project.models.project import Project
from src.project.schemas.project import ProjectCreate, ProjectUpdate
from src.project.schemas.settings import merge_settings


class DuplicateProject(Exception):
    pass


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100].rstrip("-")


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        # roll back so the session stays usable for the rest of the request and the next one
        db.rollback()
        raise DuplicateProject("A project with this name or slug already exists in the organization")


def create_project(db: Session, org_id: int, user_id: int, data: ProjectCreate) -> Project:
    slug = data.slug or slugify(data.name)
    if not slug:
        raise ValueError("Could not derive a slug from the project name; supply one")
    project = Project(
        organization_id=org_id,
        name=data.name,
        slug=slug,
        description=data.description,
        settings={},
        created_by=user_id,
    )
    db.add(project)
    _commit(db)
    db.refresh(project)
    return project


def list_projects(db: Session, org_id: int, limit: int, offset: int) -> list[Project]:
    return (
        db.query(Project)
        .filter(Project.organization_id == org_id, Project.deleted_at.is_(None))
        .order_by(Project.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


def update_project(db: Session, project: Project, data: ProjectUpdate) -> Project:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    _commit(db)
    db.refresh(project)
    return project


def update_settings(db: Session, project: Project, patch: dict) -> Project:
    # merge_settings returns a new dict, which is what makes SQLAlchemy see the change
    project.settings = merge_settings(project.settings, patch)
    db.commit()
    db.refresh(project)
    return project


def soft_delete(db: Session, project: Project) -> None:
    project.deleted_at = datetime.now(timezone.utc)
    db.commit()
