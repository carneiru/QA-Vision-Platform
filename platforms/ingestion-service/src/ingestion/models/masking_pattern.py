from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from src.ingestion.db.base import Base


class MaskingPattern(Base):
    """A project's own masking rule (RE2 syntax), applied after the built-in ones."""

    __tablename__ = "masking_patterns"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_masking_pattern_project_name"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False, index=True)
    name = Column(String(32), nullable=False)
    pattern = Column(String(256), nullable=False)
    created_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
