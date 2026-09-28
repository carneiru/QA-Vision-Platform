from urllib.parse import quote_plus

import pytest
from pydantic import ValidationError

from qav_shared.config import BaseServiceSettings


class _Settings(BaseServiceSettings):
    """A concrete subclass, since BaseServiceSettings is meant to be extended."""

    model_config = BaseServiceSettings.model_config | {"env_file": None}


def test_explicit_database_url_wins_over_components():
    settings = _Settings(
        SECRET_KEY="x",
        DATABASE_URL="postgresql://someone:somewhere@dbhost/somedb",
        POSTGRES_USER="ignored",
        POSTGRES_PASSWORD="ignored",
        POSTGRES_SERVER="ignored",
        POSTGRES_DB="ignored",
    )
    assert settings.database_url == "postgresql://someone:somewhere@dbhost/somedb"


def test_database_url_is_built_from_components_when_unset():
    settings = _Settings(
        SECRET_KEY="x",
        POSTGRES_USER="svc",
        POSTGRES_PASSWORD="pw",
        POSTGRES_SERVER="dbhost",
        POSTGRES_DB="svc_db",
    )
    assert settings.database_url == "postgresql://svc:pw@dbhost/svc_db"


def test_database_url_escapes_password_special_characters():
    """organization-service built this with a raw f-string, so a password containing @ or :
    produced a URL that parses with the wrong host. The escaped form round-trips."""
    settings = _Settings(
        SECRET_KEY="x",
        POSTGRES_USER="svc",
        POSTGRES_PASSWORD="p@ss:w/rd",
        POSTGRES_SERVER="dbhost",
        POSTGRES_DB="svc_db",
    )
    assert quote_plus("p@ss:w/rd") in settings.database_url
    assert "@dbhost/svc_db" in settings.database_url
    # the raw password must not appear unescaped -- that is the bug being fixed
    assert "p@ss:w/rd@" not in settings.database_url


def test_database_url_is_always_a_str():
    """organization-service's alembic/env.py calls .replace() on this. auth-service
    returned a PostgresDsn, on which that raises AttributeError."""
    settings = _Settings(SECRET_KEY="x", DATABASE_URL="postgresql://a:b@c/d")
    assert isinstance(settings.database_url, str)
    assert settings.database_url.replace("%", "%%") == "postgresql://a:b@c/d"


def test_secret_key_is_required(monkeypatch):
    """Cleared from the environment explicitly: this suite must fail the same way whether
    or not the developer running it happens to have SECRET_KEY exported."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        _Settings()
