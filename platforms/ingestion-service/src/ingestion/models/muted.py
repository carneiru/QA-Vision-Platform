from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from src.ingestion.db.base import Base


class MutedTest(Base):
    """A flaky test someone acknowledged: hidden from the default flaky list."""

    __tablename__ = "muted_tests"
    __table_args__ = (UniqueConstraint("project_id", "test_key", name="uq_muted_project_test"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False, index=True)
    test_key = Column(String(500), nullable=False)
    muted_by_user_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
