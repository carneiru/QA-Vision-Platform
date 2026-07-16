"""
Workflow Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class WorkflowBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: str = Field(..., regex="^(functional|performance|security|usability|compatibility)$")
    version: str = "1.0"
    tags: List[str] = []
    is_template: bool = False

class WorkflowCreate(WorkflowBase):
    created_by: str

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = Field(None, regex="^(functional|performance|security|usability|compatibility)$")
    version: Optional[str] = None
    tags: Optional[List[str]] = None
    is_template: Optional[bool] = None
    updated_by: Optional[str] = None

class WorkflowResponse(WorkflowBase):
    id: str
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True