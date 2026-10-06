from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.casebook.db.base import Base

PRIORITIES = ("low", "medium", "high", "critical")
STATUSES = ("draft", "ready", "archived")


class Case(Base):
    """A written test case. Not named TestCase: pytest would try to collect it."""

    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("project_id", "number", name="uq_cases_project_number"),
        CheckConstraint("priority IN ('low','medium','high','critical')", name="chk_cases_priority"),
        CheckConstraint("status IN ('draft','ready','archived')", name="chk_cases_status"),
        Index("ix_cases_project_status", "project_id", "status"),
        Index("uq_cases_project_source_key", "project_id", "source_key", unique=True),
    )

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False, index=True)
    # Per project, shown as TC-<number>; never reused (cases are archived, not deleted)
    number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    steps = Column(JSON, nullable=False, default=list)  # [{"action": str, "expected": str}]
    priority = Column(String(10), nullable=False, default="medium", server_default="medium")
    status = Column(String(10), nullable=False, default="draft", server_default="draft")
    # The automated test this case is implemented by: ingestion's test_key, and a label to show
    automated_test_key = Column(String(64), nullable=True, index=True)
    automated_name = Column(String(1500), nullable=True)
    # Imported from a .feature file (ADR-023): the repository owns title, gherkin and labels.
    # NULL source_key = a manual case. source_key = sha256(source_path \0 scenario name)
    source_path = Column(String(500), nullable=True)
    source_key = Column(String(64), nullable=True)
    gherkin = Column(Text, nullable=True)
    feature_name = Column(String(500), nullable=True)  # Gherkin "Feature:" of an imported case
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    labels = relationship("CaseLabel", cascade="all, delete-orphan", order_by="CaseLabel.label", lazy="selectin")


class CaseLabel(Base):
    __tablename__ = "case_labels"
    __table_args__ = (UniqueConstraint("case_id", "label", name="uq_case_labels_case_label"),)

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(40), nullable=False, index=True)
