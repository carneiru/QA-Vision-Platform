from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from src.casebook.db.base import Base


class Suite(Base):
    """A named, ordered list of a project's cases."""

    __tablename__ = "suites"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_suites_project_name"),)

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=True)


class SuiteCase(Base):
    __tablename__ = "suite_cases"
    __table_args__ = (UniqueConstraint("suite_id", "case_id", name="uq_suite_cases_suite_case"),)

    id = Column(Integer, primary_key=True)
    suite_id = Column(Integer, ForeignKey("suites.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
