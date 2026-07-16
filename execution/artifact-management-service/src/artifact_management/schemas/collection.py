"""
Collection Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CollectionBase(BaseModel):
    name: str
    description: Optional[str] = None
    collection_type: str = Field(..., regex="^(test-run|test-suite|build|release|hotfix|other)$")
    owner: str
    artifact_count: int = Field(default=0, ge=0)
    total_size: int = Field(default=0, ge=0)
    created_by: str

class CollectionCreate(CollectionBase):
    pass  # created_at is set automatically by the model

class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    collection_type: Optional[str] = Field(None, regex="^(test-run|test-suite|build|release|hotfix|other)$")
    owner: Optional[str] = None
    artifact_count: Optional[int] = Field(None, ge=0)
    total_size: Optional[int] = Field(None, ge=0)
    updated_by: Optional[str] = None

class CollectionResponse(CollectionBase):
    id: str
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True