"""
Configuration management for Auth Service
"""
import os
from typing import Optional
from pydantic import BaseSettings, PostgresDsn, RedisDsn
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

    # Database
    DATABASE_URL: PostgresDsn

    # Redis
    REDIS_URL: RedisDsn

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days
    ALGORITHM: str = "HS256"

    # Superuser
    FIRST_SUPERUSER: str
    FIRST_SUPERUSER_PASSWORD: str

    class Config:
        case_sensitive = True
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()


settings = get_settings()