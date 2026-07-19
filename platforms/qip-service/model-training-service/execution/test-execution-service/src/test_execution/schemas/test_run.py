"""
Test Run Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class TestRunBase(BaseModel):
    test_case_id: Optional[str] = None
    test_suite_id: Optional[str] = None
    environment: str = "default"
    status: str = Field(default="pending", regex="^(pending|running|completed|failed|cancelled)$")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    triggered_by: str
    configuration: dict = {}
    tags: List[str] = []

class TestRunCreate(TestRunBase):
    created_by: str

class TestRunUpdate(BaseModel):
    test_case_id: Optional[str] = None
    test_suite_id: Optional[str] = None
    environment: Optional[str] = None
    status: Optional[str] = Field(None, regex="^(pending|running|completed|failed|cancelled)$")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    triggered_by: Optional[str] = None
    configuration: Optional[dict] = None
    tags: Optional[List[str]] = None
    updated_by: Optional[str] = None

class TestRunResponse(TestRunBase):
    id: str
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True