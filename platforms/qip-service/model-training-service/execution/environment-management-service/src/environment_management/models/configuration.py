"""
Configuration Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

class Configuration(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    environment_id: str
    name: str
    description: Optional[str] = None
    configuration_type: str  # e.g., database, network, security, application, etc.
    configuration_data: dict = {}  # the actual configuration data
    version: str = "1.0"
    status: str = "active"  # active, inactive, archived
    tags: List[str] = []
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "environment_id": "env_123",
                "name": "database-config-01",
                "description": "PostgreSQL database configuration for test environment",
                "configuration_type": "database",
                "configuration_data": {
                    "host": "db-test.example.com",
                    "port": 5432,
                    "database": "test_db",
                    "username": "test_user",
                    "password": "secure_password",
                    "pool_size": 10
                },
                "version": "1.0",
                "status": "active",
                "tags": ["database", "postgresql", "test"],
                "created_by": "devops@example.com"
            }
        }