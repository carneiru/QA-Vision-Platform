"""
Workflow Runtime Schemas - Extends the workflow service with runtime fields
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

# Import the base workflow from workflow service (we'll reference it)
class WorkflowBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: str  # e.g., functional, performance, security, etc.
    version: str = "1.0"
    tags: List[str] = []
    is_template: bool = False

class WorkflowCreate(WorkflowBase):
    created_by: str

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    tags: Optional[List[str]] = None
    is_template: Optional[bool] = None
    updated_by: Optional[str] = None

class WorkflowResponse(WorkflowBase):
    id: str
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
