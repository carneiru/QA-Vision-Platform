"""
Artifact Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ArtifactBase(BaseModel):
    name: str
    description: Optional[str] = None
    artifact_type: str = Field(..., regex="^(log|screenshot|video|report|data|config|other)$")
    file_path: str
    file_size: int = Field(..., gt=0)  # Size in bytes, must be positive
    mime_type: str
    collection_id: str
    created_by: str
    tags: List[str] = []
    metadata: dict = {}

class ArtifactCreate(ArtifactBase):
    pass  # created_at is set automatically by the model

class ArtifactUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    artifact_type: Optional[str] = Field(None, regex="^(log|screenshot|video|report|data|config|other)$")
    file_path: Optional[str] = None
    file_size: Optional[int] = Field(None, gt=0)
    mime_type: Optional[str] = None
    collection_id: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None
    updated_by: Optional[str] = None

class ArtifactResponse(ArtifactBase):
    id: str
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True