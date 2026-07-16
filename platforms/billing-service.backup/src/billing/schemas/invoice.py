from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class InvoiceBase(BaseModel):
    number: str
    amount: float
    currency: str
    status: str
    due_date: datetime
    period_start: datetime
    period_end: datetime
    subscription_id: UUID

class InvoiceCreate(InvoiceBase):
    pass

class InvoiceUpdate(BaseModel):
    status: Optional[str] = None

class InvoiceInDBBase(InvoiceBase):
    id: UUID
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class Invoice(InvoiceInDBBase):
    pass
