"""_commit maps only uniqueness violations to DuplicateProject (409); any
other integrity failure is a bug and must surface as itself, not as a
misleading 'already exists'."""
import pytest
from sqlalchemy.exc import IntegrityError

from src.project.models.project import Project
from src.project.service import project_service


def _project(**overrides):
    fields = dict(organization_id=1, name="Shop", slug="shop", settings={}, created_by=1)
    fields.update(overrides)
    return Project(**fields)


def test_a_duplicate_slug_is_a_duplicate_project(db):
    db.add(_project())
    project_service._commit(db)
    db.add(_project(name="Shop again"))
    with pytest.raises(project_service.DuplicateProject):
        project_service._commit(db)


def test_a_not_null_violation_is_not_reported_as_a_duplicate(db):
    db.add(_project(created_by=None))
    with pytest.raises(IntegrityError):
        project_service._commit(db)


def test_the_session_stays_usable_after_either_failure(db):
    db.add(_project(created_by=None))
    with pytest.raises(IntegrityError):
        project_service._commit(db)
    db.add(_project(slug="other", name="Other"))
    project_service._commit(db)  # no PendingRollbackError
