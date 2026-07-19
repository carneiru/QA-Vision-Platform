"""
Test Suite Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class TestSuite(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    title: str
    description: Optional[str] = None
    test_suite_type: str = "functional"  # functional, regression, smoke, sanity, etc.
    status: str = "active"  # active, inactive, archived
    version: str = "1.0"
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
                "title": "User Login Test Suite",
                "description": "Test suite for user login functionality",
                "test_suite_type": "functional",
                "status": "active",
                "version": "1.0",
                "tags": ["login", "authentication", "functional"],
                "created_by": "tester@example.com"
            }
        }