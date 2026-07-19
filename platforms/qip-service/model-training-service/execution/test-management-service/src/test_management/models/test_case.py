"""
Test Case Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class TestCase(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    title: str
    description: Optional[str] = None
    test_suite_id: Optional[str] = None
    test_specification_id: Optional[str] = None
    priority: str = "medium"  # low, medium, high, critical
    severity: str = "medium"  # low, medium, high, critical
    status: str = "draft"  # draft, ready, in_progress, passed, failed, blocked
    test_type: str = "functional"  # functional, performance, security, usability, etc.
    test_level: str = "component"  # unit, component, integration, system, acceptance
    test_type_design_technique: Optional[str] = None  # boundary value, equivalence partitioning, etc.
    precondition: Optional[str] = None
    postcondition: Optional[str] = None
    test_steps: List[dict] = []  # List of steps with description, expected result, etc.
    test_data: Optional[str] = None
    environment: Optional[str] = None
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
                "title": "Valid User Login",
                "description": "Test valid user login with correct credentials",
                "test_suite_id": "suite_123",
                "test_specification_id": "spec_456",
                "priority": "high",
                "severity": "critical",
                "status": "ready",
                "test_type": "functional",
                "test_level": "system",
                "precondition": "User is on the login page",
                "test_steps": [
                    {
                        "step_number": 1,
                        "action": "Enter valid username",
                        "expected_result": "Username is accepted"
                    },
                    {
                        "step_number": 2,
                        "action": "Enter valid password",
                        "expected_result": "Password is accepted"
                    },
                    {
                        "step_number": 3,
                        "action": "Click login button",
                        "expected_result": "User is logged in and redirected to dashboard"
                    }
                ],
                "test_data": "username: testuser, password: TestPass123!",
                "environment": "Chrome 91.0, Windows 10",
                "tags": ["login", "authentication", "positive"],
                "created_by": "tester@example.com"
            }
        }