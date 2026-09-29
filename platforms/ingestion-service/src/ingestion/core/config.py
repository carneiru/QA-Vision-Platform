"""Configuration management for Ingestion Service."""
from qav_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "Ingestion Service"
    APP_VERSION: str = "0.1.0"

    POSTGRES_DB: str = "ingestion_db"

    # People's roles come from project-service's GET /projects/{id} (my_role)
    PROJECT_SERVICE_URL: str = "http://localhost:8002"
    PROJECT_SERVICE_TIMEOUT_SECONDS: float = 3.0

    # One upload is one transaction; these keep it bounded
    MAX_RESULTS_PER_RUN: int = 20000
    MAX_TEXT_BYTES: int = 65536


settings = Settings()
