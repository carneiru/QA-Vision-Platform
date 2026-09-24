from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from src.auth.db.base import Base


class PendingRegistration(Base):
    __tablename__ = "pending_registrations"

    id = Column(Integer, primary_key=True, index=True)
    # UNIQUE: a second registration attempt for the same still-pending address rotates this
    # row (deleted and replaced) rather than creating a competing one or erroring -- nothing
    # is claimed yet, so refusing would only leak that someone already tried this address.
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
