"""Tests for the FIRST_SUPERUSER bootstrap.

These call bootstrap_first_superuser(db) directly against the test session rather than
going through app startup: the startup hook opens its own SessionLocal() pointed at the
real configured database, which is correct for production but is not the test's sqlite
session -- routing through TestClient here would either miss the real behavior or attempt
a connection that does not exist in this environment.
"""
import pytest

from src.auth.config import settings
from src.auth.models.user import User
from src.auth.service.bootstrap import bootstrap_first_superuser


@pytest.fixture(autouse=True)
def _clear_first_superuser_settings(monkeypatch):
    # Belt and suspenders: every test starts from "unset", even if the environment running
    # the suite happens to carry these.
    monkeypatch.setattr(settings, "FIRST_SUPERUSER", None)
    monkeypatch.setattr(settings, "FIRST_SUPERUSER_PASSWORD", None)


def test_noop_when_unconfigured(db):
    bootstrap_first_superuser(db)
    assert db.query(User).count() == 0


def test_creates_the_superuser_on_a_fresh_database(db, monkeypatch):
    monkeypatch.setattr(settings, "FIRST_SUPERUSER", "root@example.com")
    monkeypatch.setattr(settings, "FIRST_SUPERUSER_PASSWORD", "bootstrappassword1")

    bootstrap_first_superuser(db)

    user = db.query(User).filter(User.email == "root@example.com").first()
    assert user is not None
    assert user.is_superuser is True
    assert user.is_active is True
    assert user.hashed_password is not None


def test_does_not_promote_an_existing_account_with_that_email(db, monkeypatch):
    """The email is an operator choice, not a secret. Promoting whatever already registered
    it would let an attacker who read the deployment config choose their own superuser."""
    squatter = User(
        email="root@example.com",
        hashed_password="not-the-bootstrap-hash",
        is_active=True,
        is_superuser=False,
    )
    db.add(squatter)
    db.commit()

    monkeypatch.setattr(settings, "FIRST_SUPERUSER", "root@example.com")
    monkeypatch.setattr(settings, "FIRST_SUPERUSER_PASSWORD", "bootstrappassword1")

    bootstrap_first_superuser(db)

    db.refresh(squatter)
    assert squatter.is_superuser is False
    assert squatter.hashed_password == "not-the-bootstrap-hash"
    assert db.query(User).count() == 1, "no second account may be created for the same email"


def test_is_permanently_a_noop_once_any_superuser_exists(db, monkeypatch):
    """A later redeploy carrying the same env vars must not mint a second superuser, and
    must not touch a different email than the one that already holds the role."""
    db.add(User(
        email="already-admin@example.com",
        hashed_password="x",
        is_active=True,
        is_superuser=True,
    ))
    db.commit()

    monkeypatch.setattr(settings, "FIRST_SUPERUSER", "someone-else@example.com")
    monkeypatch.setattr(settings, "FIRST_SUPERUSER_PASSWORD", "bootstrappassword1")

    bootstrap_first_superuser(db)

    assert db.query(User).filter(User.email == "someone-else@example.com").first() is None
    assert db.query(User).count() == 1
