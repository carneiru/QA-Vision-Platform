from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    PAUSED = "paused"

class SubscriptionBase(BaseModel):
    plan_id: str
    customer_id: UUID
    organization_id: UUID
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    cancel_at_period_end: bool = False

class SubscriptionCreate(SubscriptionBase):
    quantity: int = 1
    coupon_id: Optional[str] = None

class SubscriptionUpdate(BaseModel):
    plan_id: Optional[str] = None
    quantity: Optional[int] = None
    cancel_at_period_end: Optional[bool] = None
    trial_end: Optional[datetime] = None

class SubscriptionInDBBase(SubscriptionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class Subscription(SubscriptionInDBBase):
    pass
