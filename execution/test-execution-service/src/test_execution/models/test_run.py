"""
Test Run Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class TestRun(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    test_case_id: Optional[str] = None
    test_suite_id: Optional[str] = None
    environment: str = "default"
    status: str = "pending"  # pending, running, completed, failed, cancelled
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    triggered_by: str  # user or system that triggered the run
    configuration: dict = {}  # any configuration specific to this run
    tags: List[str] = []
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "test_case_id": "tc_123",
                "test_suite_id": "ts_456",
                "environment": "chrome-windows10",
                "status": "pending",
                "triggered_by": "scheduler",
                "configuration": {
                    "browser": "chrome",
                    "version": "91.0",
                    "platform": "Windows 10"
                },
                "tags": ["smoke", "regression"],
                "created_by": "tester@example.com"
            }
        }
}