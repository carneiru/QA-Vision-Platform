"""
Environment Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class Environment(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    description: Optional[str] = None
    environment_type: str  # e.g., dev, test, staging, prod, etc.
    status: str = "available"  # available, provisioning, provisioned, deprovisioning, deprovisioned, maintenance, failed
    infrastructure_as_code: Optional[str] = None  # e.g., terraform, cloudformation, etc.
    configuration: dict = {}  # environment-specific configuration
    tags: List[str] = []
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    provisioned_at: Optional[datetime] = None
    deprovisioned_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "name": "test-environment-01",
                "description": "Test environment for regression testing",
                "environment_type": "test",
                "status": "available",
                "infrastructure_as_code": "terraform",
                "configuration": {
                    "instance_type": "t3.medium",
                    "os": "ubuntu-20.04",
                    "region": "us-west-2"
                },
                "tags": ["test", "regression", "ubuntu"],
                "created_by": "devops@example.com"
            }
        }