"""
Schedule Model
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ScheduleType(str, Enum):
    CRON = "cron"
    INTERVAL = "interval"
    ONE_TIME = "one_time"
    RULE = "rule"

class ScheduleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    COMPLETED = "completed"

class ScheduleBase(BaseModel):
    workflow_id: str
    name: str
    schedule_type: ScheduleType
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    config: Dict[str, Any] = {}
    description: Optional[str] = None

class ScheduleCreate(ScheduleBase):
    pass

class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    schedule_type: Optional[ScheduleType] = None
    status: Optional[ScheduleStatus] = None
    config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

class ScheduleResponse(ScheduleBase):
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None

    class Config:
        orm_mode = True
EOF