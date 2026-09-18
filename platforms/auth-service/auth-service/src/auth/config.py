"""
Configuration management for Auth Service
"""
import os
from typing import Optional
from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Auth Service"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # API
    API_V1_STR: str = "/api/v1"

    # Database - Individual components (for backwards compatibility)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "auth_db"

    # Database - Full URL (optional, overrides individual components if set)
    DATABASE_URL: Optional[PostgresDsn] = None

    # Redis - Individual components (for backwards compatibility)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Redis - Full URL (optional, overrides individual components if set)
    REDIS_URL: Optional[RedisDsn] = None

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days
    ALGORITHM: str = "HS256"

    # Superuser. Optional: nothing in this service reads these today, and making them
    # required meant Settings() raised on import, so the app could not start at all.
    # No default password is supplied on purpose -- a baked-in one would be worse than absent.
    FIRST_SUPERUSER: Optional[str] = None
    FIRST_SUPERUSER_PASSWORD: Optional[str] = None

    # Email (for notifications)
    SMTP_TLS: bool = True
    SMTP_PORT: int = 587
    SMTP_HOST: str = ""
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = ""
    EMAILS_FROM_NAME: str = ""

    # SSO Providers
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""
    SAML_SETTINGS: str = "{}"

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env"
    )

    @property
    def database_url(self) -> PostgresDsn:
        """Return database URL, either direct or constructed from components."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return PostgresDsn.build(
            scheme="postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            path=f"/{self.POSTGRES_DB or ''}"
        )

    @property
    def redis_url(self) -> RedisDsn:
        """Return Redis URL, either direct or constructed from components."""
        if self.REDIS_URL:
            return self.REDIS_URL
        return RedisDsn.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=str(self.REDIS_PORT),
            path=f"/{self.REDIS_DB}"
        )


def get_settings() -> Settings:
    return Settings()


settings = get_settings()