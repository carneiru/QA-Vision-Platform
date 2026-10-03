"""Configuration management for Organization Service."""
from qav_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    # Application
    APP_NAME: str = "Organization Service"
    APP_VERSION: str = "0.1.0"
    PROJECT_NAME: str = "Organization Service"

    # Database
    POSTGRES_DB: str = "organization_db"

    # Service-to-service call to auth-service's internal API for user existence
    # checks (HTTP Basic, shared secret — replaced the superuser bearer token)
    AUTH_SERVICE_URL: str = "http://localhost:8000"
    INTERNAL_API_USERNAME: str = "organization-service"
    INTERNAL_API_PASSWORD: str = ""


settings = Settings()
