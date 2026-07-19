"""
Schedule Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
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
    COMPLETED = "completed"

class ScheduleBase(BaseModel):
    workflow_id: str
    schedule_type: ScheduleType
    name: str
    description: Optional[str] = None
    config: Dict[str, Any] = {}  # Schedule-specific configuration (cron expression, interval, etc.)
    timezone: str = "UTC"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    max_executions: Optional[int] = None  # None means unlimited
    execution_count: int = 0

class ScheduleCreate(ScheduleBase):
    pass

class ScheduleUpdate(BaseModel):
    workflow_id: Optional[str] = None
    schedule_type: Optional[ScheduleType] = None
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[ScheduleStatus] = None
    max_executions: Optional[int] = None

class ScheduleResponse(ScheduleBase):
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    last_executed: Optional[datetime] = None
    next_execution: Optional[datetime] = None

    class Config:
        orm_mode = True
