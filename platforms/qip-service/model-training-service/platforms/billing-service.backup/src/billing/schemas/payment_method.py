from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

class PaymentMethodType(str, Enum):
    CARD = "card"
    BANK_ACCOUNT = "bank_account"
    PAYPAL = "paypal"

class PaymentMethodBase(BaseModel):
    customer_id: UUID
    type: PaymentMethodType
    token: Optional[str] = None  # For Stripe/PayPal tokens

class PaymentMethodCreate(PaymentMethodBase):
    # Card details (alternative to token)
    brand: Optional[str] = None
    last4: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None

class PaymentMethodUpdate(BaseModel):
    is_default: Optional[bool] = None

class PaymentMethodInDBBase(PaymentMethodBase):
    id: UUID
    provider: str
    provider_id: Optional[str] = None
    last4: Optional[str] = None
    brand: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    is_default: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class PaymentMethod(PaymentMethodInDBBase):
    pass
