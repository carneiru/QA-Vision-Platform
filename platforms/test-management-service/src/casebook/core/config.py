"""Configuration management for Test Management Service."""
from qav_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "Test Management Service"
    APP_VERSION: str = "0.1.0"

    POSTGRES_DB: str = "testmgmt_db"

    # People's roles come from project-service's GET /projects/{id} (my_role)
    PROJECT_SERVICE_URL: str = "http://localhost:8002"
    PROJECT_SERVICE_TIMEOUT_SECONDS: float = 3.0

    # Gherkin import (ADR-023): one request is one transaction; these keep it bounded.
    # Raise them in .env; the gateway's GATEWAY_IMPORT_MAX_BODY must stay above the total
    IMPORT_MAX_FILES: int = 2000
    IMPORT_MAX_FILE_BYTES: int = 262144
    IMPORT_MAX_TOTAL_BYTES: int = 10485760


settings = Settings()
