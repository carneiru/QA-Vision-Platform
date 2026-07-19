"""
Test Result Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

class TestResult(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    test_run_id: str
    test_case_id: Optional[str] = None
    test_suite_id: Optional[str] = None
    step_number: int
    step_description: str
    expected_result: str
    actual_result: Optional[str] = None
    status: str = "pending"  # pending, passed, failed, skipped, error
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    execution_time_ms: Optional[int] = None
    screenshots: List[str] = []  # paths or URLs to screenshots
    logs: List[str] = []  # log entries
    data: Dict[str, Any] = {}  # additional data
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    executed_by: str  # user or system that executed the step

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "test_run_id": "tr_789",
                "test_case_id": "tc_123",
                "step_number": 1,
                "step_description": "Navigate to login page",
                "expected_result": "Login page is displayed",
                "actual_result": "Login page is displayed",
                "status": "passed",
                "execution_time_ms": 1250,
                "screenshots": ["screenshots/step1.png"],
                "logs": ["Navigated to https://example.com/login"],
                "executed_by": "automation_user"
            }
        }
}