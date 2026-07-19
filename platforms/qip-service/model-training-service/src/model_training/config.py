"""Configuration settings for the Model Training Service."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings."""

    # Application settings
    APP_NAME: str = "Model Training Service"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database settings
    DATABASE_URL: str = Field(
        default="postgresql://user:password@localhost:5432/model_training_db",
        env="DATABASE_URL"
    )
    DATABASE_ECHO: bool = Field(default=False, env="DATABASE_ECHO")

    # Redis settings
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )

    # Security settings
    SECRET_KEY: str = Field(
        default="your-secret-key-here",
        env="SECRET_KEY"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Model training settings
    MODEL_STORAGE_PATH: str = Field(
        default="./models",
        env="MODEL_STORAGE_PATH"
    )
    MAX_CONCURRENT_TRAINING_JOBS: int = 5
    TRAINING_TIMEOUT_MINUTES: int = 60

    # Logging settings
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # Jaeger tracing settings
    JAEGER_ENABLED: bool = Field(default=False, env="JAEGER_ENABLED")
    JAEGER_HOST: str = Field(default="localhost", env="JAEGER_HOST")
    JAEGER_PORT: int = Field(default=6831, env="JAEGER_PORT")
    JAEGER_ENDPOINT: str = Field(default="", env="JAEGER_ENDPOINT")

    # Kafka settings (for integration with event-driven architecture)
    KAFKA_BOOTSTRAP_SERVERS: str = Field(
        default="localhost:9092",
        env="KAFKA_BOOTSTRAP_SERVERS"
    )
    MODEL_TRAINING_TOPIC: str = "model-training-requests"
    MODEL_TRAINED_TOPIC: str = "model-trained-events"
    MODEL_EVALUATION_TOPIC: str = "model-evaluation-requests"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }


# Global settings instance
settings = Settings()