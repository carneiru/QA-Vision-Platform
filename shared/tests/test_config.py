import pytest
import sqlalchemy
from pydantic import ValidationError

from qeos_shared.config import BaseServiceSettings


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


def test_database_url_is_built_from_components_when_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = _Settings(
        SECRET_KEY="x",
        POSTGRES_USER="svc",
        POSTGRES_PASSWORD="pw",
        POSTGRES_SERVER="dbhost",
        POSTGRES_DB="svc_db",
    )
    assert settings.database_url == "postgresql://svc:pw@dbhost/svc_db"


@pytest.mark.parametrize("pw", ["p@ss:w/rd", "a b+c", "100%x", "#?&="])
def test_database_url_escapes_password_special_characters(monkeypatch, pw):
    """organization-service built this with a raw f-string (no encoding at all), and
    auth-service's PostgresDsn.build raised ValidationError on ':' or '/' rather than
    escaping them. quote_plus is also wrong here: it turns a space into '+', which a URL
    parser then decodes back as a literal '+' instead of a space, corrupting the password.
    The escaped form must round-trip through a real URL parser."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = _Settings(
        SECRET_KEY="x",
        POSTGRES_USER="svc",
        POSTGRES_PASSWORD=pw,
        POSTGRES_SERVER="dbhost",
        POSTGRES_DB="svc_db",
    )
    parsed = sqlalchemy.engine.make_url(settings.database_url)
    assert parsed.password == pw
    assert parsed.host == "dbhost"
    assert parsed.database == "svc_db"


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
