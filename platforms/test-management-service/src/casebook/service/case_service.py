"""Cases (docs/superpowers/specs/2026-10-06-test-management-design.md)."""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.casebook.models import Case, CaseLabel, Suite, SuiteCase


def case_key(number: int) -> str:
    return f"TC-{number}"


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def out(row: Case, suites: Optional[list] = None) -> dict:
    return {
        "number": row.number, "key": case_key(row.number), "title": row.title, "description": row.description,
        "steps": row.steps or [], "labels": [label.label for label in row.labels], "priority": row.priority,
        "status": row.status, "automated_test_key": row.automated_test_key, "automated_name": row.automated_name,
        "created_by": row.created_by, "created_at": row.created_at, "updated_by": row.updated_by,
        "updated_at": row.updated_at, "source_path": row.source_path, "gherkin": row.gherkin,
        "suites": suites or [],
    }


def get_case(db: Session, project_id: int, number: int) -> Optional[Case]:
    return db.query(Case).filter(Case.project_id == project_id, Case.number == number).one_or_none()


def suites_of(db: Session, case: Case) -> List[dict]:
    rows = (
        db.query(Suite.id, Suite.name).join(SuiteCase, SuiteCase.suite_id == Suite.id)
        .filter(SuiteCase.case_id == case.id).order_by(Suite.name).all()
    )
    return [{"id": r.id, "name": r.name} for r in rows]


def _next_number(db: Session, project_id: int) -> int:
    current = db.execute(select(func.max(Case.number)).where(Case.project_id == project_id)).scalar()
    return (current or 0) + 1


def create_case(db: Session, project_id: int, user_id: int, data: dict) -> Case:
    labels = data.pop("labels", [])
    steps = [dict(s) for s in data.pop("steps", [])]
    if not data.get("automated_test_key"):
        data["automated_test_key"], data["automated_name"] = None, None
    # Two people saving at once may pick the same number; the unique constraint catches it
    for attempt in range(3):
        row = Case(project_id=project_id, number=_next_number(db, project_id), steps=steps,
                   created_by=user_id, labels=[CaseLabel(label=label) for label in labels], **data)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise
            continue
        db.refresh(row)
        return row
    raise RuntimeError("unreachable")


REPOSITORY_FIELDS = ("title", "steps", "labels", "gherkin")


def repository_owned(row: Case, changes: dict) -> list:
    """Fields a PATCH may not change on an imported case: its .feature file owns them (ADR-023)."""
    if row.source_key is None:
        changes.pop("gherkin", None)
        return []
    return [f for f in REPOSITORY_FIELDS if f in changes]


def update_case(db: Session, row: Case, user_id: int, changes: dict) -> Case:
    if "labels" in changes:
        labels = changes.pop("labels") or []
        row.labels = [CaseLabel(label=label) for label in labels]
    if "steps" in changes:
        row.steps = [dict(s) for s in (changes.pop("steps") or [])]
    if "automated_test_key" in changes and not changes["automated_test_key"]:
        changes["automated_name"] = None
    for key in ("title", "priority", "status"):
        if key in changes and changes[key] is None:
            changes.pop(key)  # these cannot be emptied; null means "leave as it is"
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_by = user_id
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def list_cases(db: Session, project_id: int, *, search: Optional[str], labels: List[str], status: Optional[str],
               priority: Optional[str], include_archived: bool, limit: int, offset: int,
               origin: Optional[str] = None):
    query = db.query(Case).filter(Case.project_id == project_id)
    if status is not None:
        query = query.filter(Case.status == status)
    elif not include_archived:
        query = query.filter(Case.status != "archived")
    if priority is not None:
        query = query.filter(Case.priority == priority)
    if origin == "imported":
        query = query.filter(Case.source_key.isnot(None))
    elif origin == "manual":
        query = query.filter(Case.source_key.is_(None))
    if search:
        pattern = f"%{_escape_like(search)}%"
        query = query.filter(or_(Case.title.ilike(pattern, escape="\\"), Case.gherkin.ilike(pattern, escape="\\")))
    for label in {label.lower() for label in labels}:
        query = query.filter(exists().where(CaseLabel.case_id == Case.id, CaseLabel.label == label))
    total = query.count()
    rows = query.order_by(Case.number).offset(offset).limit(limit).all()
    return total, rows


def label_counts(db: Session, project_id: int) -> List[dict]:
    rows = (
        db.query(CaseLabel.label, func.count(CaseLabel.id))
        .join(Case, Case.id == CaseLabel.case_id)
        .filter(Case.project_id == project_id, Case.status != "archived")
        .group_by(CaseLabel.label).order_by(CaseLabel.label).all()
    )
    return [{"label": label, "count": count} for label, count in rows]
