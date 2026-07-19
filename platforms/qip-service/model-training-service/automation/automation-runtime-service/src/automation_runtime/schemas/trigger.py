"""
Trigger Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class TriggerType(str, Enum):
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    FILE_WATCHER = "file_watcher"
    API_CALL = "api_call"
    MANUAL = "manual"
    EVENT = "event"

class TriggerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"

class TriggerBase(BaseModel):
    workflow_id: str
    trigger_type: TriggerType
    name: str
    description: Optional[str] = None
    config: Dict[str, Any] = {}  # Trigger-specific configuration
    status: TriggerStatus = TriggerStatus.ACTIVE
    is_enabled: bool = True

class TriggerCreate(TriggerBase):
    pass

class TriggerUpdate(BaseModel):
    workflow_id: Optional[str] = None
    trigger_type: Optional[TriggerType] = None
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[TriggerStatus] = None
    is_enabled: Optional[bool] = None

class TriggerResponse(TriggerBase):
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0

    class Config:
        orm_mode = True
