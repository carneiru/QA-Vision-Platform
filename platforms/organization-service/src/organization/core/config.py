"""Configuration management for Organization Service."""
from typing import Optional
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Organization Service"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Organization Service"

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "organization_db"
    DATABASE_URL: Optional[PostgresDsn] = None

    # Security — must match auth-service's SECRET_KEY/ALGORITHM so its JWTs verify here
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"

    # Service-to-service call to auth-service for user existence checks
    AUTH_SERVICE_URL: str = "http://localhost:8000"
    AUTH_SERVICE_TOKEN: str = ""

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return str(self.DATABASE_URL)
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
        )


settings = Settings()
