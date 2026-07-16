"""
Test Specification Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class TestSpecificationBase(BaseModel):
    title: str
    description: Optional[str] = None
    specification_type: str = Field(default="functional", regex="^(functional|performance|security|usability|compatibility)$")
    status: str = Field(default="active", regex="^(active|inactive|archived|deprecated)$")
    version: str = "1.0"
    tags: List[str] = []

class TestSpecificationCreate(TestSpecificationBase):
    created_by: str

class TestSpecificationUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    specification_type: Optional[str] = Field(None, regex="^(functional|performance|security|usability|compatibility)$")
    status: Optional[str] = Field(None, regex="^(active|inactive|archived|deprecated)$")
    version: Optional[str] = None
    tags: Optional[List[str]] = None
    updated_by: Optional[str] = None

class TestSpecificationResponse(TestSpecificationBase):
    id: str
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True