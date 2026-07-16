"""
Collection Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class Collection(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    description: Optional[str] = None
    collection_type: str  # e.g., test-run, test-suite, build, release, etc.
    owner: str  # User, team, or system that owns this collection
    artifact_count: int = 0  # Number of artifacts in this collection
    total_size: int = 0  # Total size of all artifacts in bytes
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "name": "test-run-2023-01-01-12-00-00",
                "description": "Test run executed on January 1, 2023 at 12:00:00",
                "collection_type": "test-run",
                "owner": "qa-team",
                "artifact_count": 42,
                "total_size": 10485760,  # 10 MB
                "created_by": "test-runner-01",
                "updated_by": "test-runner-01"
            }
        }