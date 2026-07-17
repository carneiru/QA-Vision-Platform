"""
Trigger Model
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class TriggerType(str, Enum):
    WEBHOOK = "webhook"
    FILE_SYSTEM = "file_system"
    EMAIL = "email"
    MESSAGE_QUEUE = "message_queue"
    API = "api"
    MANUAL = "manual"
    SCHEDULE = "schedule"

class TriggerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    ERROR = "error"

class TriggerBase(BaseModel):
    workflow_id: str
    name: str
    trigger_type: TriggerType
    status: TriggerStatus = TriggerStatus.ACTIVE
    config: Dict[str, Any] = {}
    description: Optional[str] = None

class TriggerCreate(TriggerBase):
    pass

class TriggerUpdate(BaseModel):
    name: Optional[str] = None
    trigger_type: Optional[TriggerType] = None
    status: Optional[TriggerStatus] = None
    config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

class TriggerResponse(TriggerBase):
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
EOF