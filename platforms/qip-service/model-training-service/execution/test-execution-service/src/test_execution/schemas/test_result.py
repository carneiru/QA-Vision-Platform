"""
Test Result Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class TestResultBase(BaseModel):
    test_run_id: str
    test_case_id: Optional[str] = None
    test_suite_id: Optional[str] = None
    step_number: int
    step_description: str
    expected_result: str
    actual_result: Optional[str] = None
    status: str = Field(default="pending", regex="^(pending|passed|failed|skipped|error)$")
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    execution_time_ms: Optional[int] = None
    screenshots: List[str] = []
    logs: List[str] = []
    data: Dict[str, Any] = {}
    executed_by: str

class TestResultCreate(TestResultBase):
    pass  # executed_at is set automatically by the model

class TestResultUpdate(BaseModel):
    test_case_id: Optional[str] = None
    test_suite_id: Optional[str] = None
    step_description: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    status: Optional[str] = Field(None, regex="^(pending|passed|failed|skipped|error)$")
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    execution_time_ms: Optional[int] = None
    screenshots: Optional[List[str]] = None
    logs: Optional[List[str]] = None
    data: Optional[Dict[str, Any]] = None
    executed_by: Optional[str] = None

class TestResultResponse(TestResultBase):
    id: str
    executed_at: datetime
    executed_by: str

    class Config:
        orm_mode = True