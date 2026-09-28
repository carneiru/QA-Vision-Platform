"""Settings shared by every QA Vision Platform service."""
from typing import Optional
from urllib.parse import quote_plus

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Subclass this and add whatever else your service needs."""

    APP_NAME: str = "QA Vision Service"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    API_V1_STR: str = "/api/v1"

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "postgres"
    DATABASE_URL: Optional[PostgresDsn] = None

    # No default, deliberately: a service that cannot find a secret must refuse to start
    # rather than run on a predictable one. organization-service previously defaulted this
    # to the literal "your-secret-key-here".
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

    @property
    def database_url(self) -> str:
        """The database URL, always as a str.

        Every consumer either hands this to create_engine or calls a str method on it --
        organization-service's alembic/env.py does `.replace("%", "%%")`, which raises
        AttributeError against a PostgresDsn object. auth-service returned PostgresDsn and
        organization-service returned str; unifying on str removes that trap.

        The components path escapes user and password. auth-service got this right via
        PostgresDsn.build; organization-service's f-string did not, so any password
        containing @, / or : produced a malformed URL there.
        """
        if self.DATABASE_URL:
            return str(self.DATABASE_URL)
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql://{user}:{password}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
