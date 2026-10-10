from sqlalchemy import Column, DateTime, String, Text

from src.ingestion.db.base import Base


class JobHeartbeat(Base):
    """One row per loop job: its last successful pass and its last failed one (migration 017)."""

    __tablename__ = "job_heartbeats"

    job = Column(String(50), primary_key=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)  # first line, at most 500 characters, no secrets
