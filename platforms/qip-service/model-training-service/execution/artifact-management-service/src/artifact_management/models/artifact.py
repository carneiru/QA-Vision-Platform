"""
Artifact Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class Artifact(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    description: Optional[str] = None
    artifact_type: str  # e.g., log, screenshot, video, report, etc.
    file_path: str  # Path to the artifact file
    file_size: int  # Size in bytes
    mime_type: str  # MIME type of the file
    collection_id: str  # ID of the collection this artifact belongs to
    created_by: str  # User or system that created this artifact
    tags: List[str] = []  # Tags for categorization
    metadata: dict = {}  # Additional metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "name": "test-execution-log.txt",
                "description": "Log file from test execution",
                "artifact_type": "log",
                "file_path": "/artifacts/logs/test-execution-log.txt",
                "file_size": 10240,
                "mime_type": "text/plain",
                "collection_id": "coll_123",
                "created_by": "test-runner-01",
                "tags": ["log", "test-execution", "verbose"],
                "metadata": {
                    "test_run_id": "tr_456",
                    "test_suite_id": "ts_789",
                    "log_level": "DEBUG"
                }
            }
        }