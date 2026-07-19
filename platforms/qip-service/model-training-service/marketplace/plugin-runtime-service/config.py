from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Plugin Runtime Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # API settings
    API_V1_STR: str = "/api/v1"
    PORT: int = 8003
    
    # MongoDB settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "plugin_runtime"
    
    # Kafka settings (optional)
    KAFKA_BOOTSTRAP_SERVERS: Optional[str] = None
    
    # Docker settings
    DOCKER_HOST: Optional[str] = "unix:///var/run/docker.sock"
    
    # Environment
    ENVIRONMENT: str = "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
