"""
Test Case Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class TestCaseBase(BaseModel):
    title: str
    description: Optional[str] = None
    test_suite_id: Optional[str] = None
    test_specification_id: Optional[str] = None
    priority: str = Field(default="medium", regex="^(low|medium|high|critical)$")
    severity: str = Field(default="medium", regex="^(low|medium|high|critical)$")
    status: str = Field(default="draft", regex="^(draft|ready|in_progress|blocked|passed|failed)$")
    test_type: str = Field(default="functional", regex="^(functional|performance|security|usability|compatibility)$")
    test_level: str = Field(default="component", regex="^(unit|component|integration|system|acceptance)$")
    precondition: Optional[str] = None
    postcondition: Optional[str] = None
    test_steps: List[dict] = []
    test_data: Optional[str] = None
    environment: Optional[str] = None
    tags: List[str] = []

class TestCaseCreate(TestCaseBase):
    created_by: str

class TestCaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    test_suite_id: Optional[str] = None
    test_specification_id: Optional[str] = None
    priority: Optional[str] = Field(None, regex="^(low|medium|high|critical)$")
    severity: Optional[str] = Field(None, regex="^(low|medium|high|critical)$")
    status: Optional[str] = Field(None, regex="^(draft|ready|in_progress|blocked|passed|failed)$")
    test_type: Optional[str] = Field(None, regex="^(functional|performance|security|usability|compatibility)$")
    test_level: Optional[str] = Field(None, regex="^(unit|component|integration|system|acceptance)$")
    precondition: Optional[str] = None
    postcondition: Optional[str] = None
    test_steps: Optional[List[dict]] = None
    test_data: Optional[str] = None
    environment: Optional[str] = None
    tags: Optional[List[str]] = None
    updated_by: Optional[str] = None

class TestCaseResponse(TestCaseBase):
    id: str
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True