"""
Step Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class StepBase(BaseModel):
    name: str
    description: Optional[str] = None
    step_type: str = Field(..., regex="^(action|validation|wait|loop|condition|other)$")
    workflow_id: str
    order_index: int = Field(..., ge=0)  # Order of the step within the workflow
    configuration: Dict[str, Any] = {}  # Configuration specific to the step type
    created_by: str

class StepCreate(StepBase):
    pass  # created_at is set automatically by the model

class StepUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    step_type: Optional[str] = Field(None, regex="^(action|validation|wait|loop|condition|other)$")
    workflow_id: Optional[str] = None
    order_index: Optional[int] = Field(None, ge=0)
    configuration: Optional[Dict[str, Any]] = None
    updated_by: Optional[str] = None

class StepResponse(StepBase):
    id: str
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True