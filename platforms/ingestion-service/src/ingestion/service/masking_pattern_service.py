from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.ingestion.models.masking_pattern import MaskingPattern
from src.ingestion.utils import custom_masking


class DuplicatePattern(Exception):
    pass


def list_patterns(db: Session, project_id: int) -> List[MaskingPattern]:
    return db.query(MaskingPattern).filter_by(project_id=project_id).order_by(MaskingPattern.id).all()


def compiled_for(db: Session, project_id: int) -> List[custom_masking.CustomPattern]:
    """The project's patterns, ready to apply. A stored pattern that no longer compiles (it was
    validated on the way in, so only a library change could do this) is skipped, not fatal."""
    patterns = []
    for row in list_patterns(db, project_id):
        try:
            patterns.append(custom_masking.CustomPattern(row.name, custom_masking.compile_pattern(row.pattern)))
        except ValueError:
            continue
    return patterns


def validate(name: str, pattern: str) -> custom_masking.CustomPattern:
    """ValueError with a reason, for a 422."""
    return custom_masking.CustomPattern(custom_masking.validate_name(name), custom_masking.compile_pattern(pattern))


def add_pattern(db: Session, project_id: int, name: str, pattern: str, user_id: int) -> MaskingPattern:
    validate(name, pattern)
    if db.query(MaskingPattern).filter_by(project_id=project_id).count() >= custom_masking.MAX_PATTERNS_PER_PROJECT:
        raise ValueError(f"A project has at most {custom_masking.MAX_PATTERNS_PER_PROJECT} masking patterns")
    row = MaskingPattern(project_id=project_id, name=name, pattern=pattern, created_by_user_id=user_id)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicatePattern(f"This project already has a pattern named {name}")
    db.refresh(row)
    return row


def delete_pattern(db: Session, project_id: int, pattern_id: int) -> bool:
    deleted = db.query(MaskingPattern).filter_by(project_id=project_id, id=pattern_id).delete()
    db.commit()
    return bool(deleted)
