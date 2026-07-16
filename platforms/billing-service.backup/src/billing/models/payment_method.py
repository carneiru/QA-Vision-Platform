from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import enum
import uuid
from src.billing.db.base import Base

class PaymentMethodType(str, enum.Enum):
    CARD = "card"
    BANK_ACCOUNT = "bank_account"
    PAYPAL = "paypal"

class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    type = Column(Enum(PaymentMethodType), nullable=False)
    provider = Column(String(50), nullable=False)  # stripe, paypal, etc.
    provider_id = Column(String(255), nullable=True)  # ID in payment gateway
    last4 = Column(String(4), nullable=True)  # last 4 digits for card
    brand = Column(String(50), nullable=True)  # visa, mastercard, etc. for card
    exp_month = Column(Integer, nullable=True)  # for card
    exp_year = Column(Integer, nullable=True)  # for card
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
