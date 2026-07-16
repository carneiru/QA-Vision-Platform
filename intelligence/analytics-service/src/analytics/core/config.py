# src/analytics-service-service/src/analytics-service/core/config.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Provides analytics capabilities including metrics, trends, predictions, and reporting"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    DATABASE_URL: str = "postgresql://postgres:password@db:5432/org_db"
    BACKEND_CORS_ORIGINS: list = []

    class Config:
        env_file = ".env"

settings = Settings()
