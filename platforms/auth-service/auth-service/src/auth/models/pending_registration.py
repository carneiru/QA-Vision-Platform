from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from src.auth.db.base import Base


class PendingRegistration(Base):
    __tablename__ = "pending_registrations"

    id = Column(Integer, primary_key=True, index=True)
    # NOT unique: a second registration attempt for the same address creates an
    # independent row rather than rotating an existing one. Rotating in place let an
    # unauthenticated attacker overwrite a pending row's PASSWORD while its verification
    # link still reached the real mailbox -- see the spec's "Amendment: rotation allowed
    # credential injection". `token` (below) is still the only thing that must be unique.
    email = Column(String(255), index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
