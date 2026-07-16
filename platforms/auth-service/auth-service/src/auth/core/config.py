# src/services/auth-service/src/auth/core/config.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    DATABASE_URL: str = "postgresql://postgres:password@db:5432/auth_db"

    class Config:
        env_file = ".env"

settings = Settings()
