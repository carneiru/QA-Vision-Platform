"""Configuration management for Test Management Service."""
from qav_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "Test Management Service"
    APP_VERSION: str = "0.1.0"

    POSTGRES_DB: str = "testmgmt_db"

    # People's roles come from project-service's GET /projects/{id} (my_role)
    PROJECT_SERVICE_URL: str = "http://localhost:8002"
    PROJECT_SERVICE_TIMEOUT_SECONDS: float = 3.0


settings = Settings()
