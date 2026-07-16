"""
Workflow Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class Workflow(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    description: Optional[str] = None
    category: str  # e.g., functional, performance, security, etc.
    version: str = "1.0"
    tags: List[str] = []
    is_template: bool = False
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "name": "user-login-workflow",
                "description": "Workflow for testing user login functionality",
                "category": "functional",
                "version": "1.0",
                "tags": ["login", "authentication", "user"],
                "is_template": false,
                "created_by": "workflow-designer",
                "updated_by": "workflow-designer"
            }
        }