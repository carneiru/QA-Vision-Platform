"""
Test Suite Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class TestSuiteBase(BaseModel):
    name: str
    description: Optional[str] = None
    test_suite_type: str = Field(default="functional", regex="^(functional|regression|smoke|sanity|performance|security|usability)$")
    status: str = Field(default="active", regex="^(active|inactive|archived)$")
    version: str = "1.0"
    tags: List[str] = []

class TestSuiteCreate(TestSuiteBase):
    created_by: str

class TestSuiteUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    test_suite_type: Optional[str] = Field(None, regex="^(functional|regression|smoke|sanity|performance|security|usability)$")
    status: Optional[str] = Field(None, regex="^(active|inactive|archived)$")
    version: Optional[str] = None
    tags: Optional[List[str]] = None
    updated_by: Optional[str] = None

class TestSuiteResponse(TestSuiteBase):
    id: str
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True