"""
Step Model
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

class Step(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    description: Optional[str] = None
    step_type: str  # e.g., action, validation, wait, loop, etc.
    workflow_id: str  # Reference to the workflow this step belongs to
    order_index: int  # Order of the step within the workflow
    configuration: Dict[str, Any] = {}  # Configuration specific to the step type
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "name": "click-login-button",
                "description": "Click the login button on the login page",
                "step_type": "action",
                "workflow_id": "workflow_123",
                "order_index": 1,
                "configuration": {
                    "element_selector": "#login-button",
                    "action_type": "click",
                    "timeout": 5000
                },
                "created_by": "workflow-designer",
                "updated_by": "workflow-designer"
            }
        }