"""
Test Specification Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class TestSpecification(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    title: str
    description: Optional[str] = None
    specification_type: str = "functional"  # functional, performance, security, usability, etc.
    status: str = "active"  # active, inactive, archived, deprecated
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
                "title": "User Login Specification",
                "description": "Specification for user login functionality covering valid and invalid credentials",
                "specification_type": "functional",
                "status": "active",
                "version": "1.0",
                "tags": ["login", "authentication", "functional"],
                "created_by": "tester@example.com"
            }
        }