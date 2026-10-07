from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from src.ingestion.db.base import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    # No FKs: projects and organizations live in other services' databases
    project_id = Column(Integer, nullable=False, index=True)
    organization_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(16), nullable=False)  # "qeos_" + 8 (legacy "qav_" + 8), shown in listings
    key_hash = Column(String(64), nullable=False)    # SHA-256 hex of the full key
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),)
