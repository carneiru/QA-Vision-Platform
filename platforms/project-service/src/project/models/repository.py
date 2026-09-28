from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, false,
)
from sqlalchemy.sql import func

from src.project.db.base import Base


class Repository(Base):
    __tablename__ = "repositories"

    PROVIDERS = ("github", "gitlab")
    STATUSES = ("verified", "not_found", "unchecked")

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(20), nullable=False)
    owner = Column(String(255), nullable=False)          # as displayed; GitLab: full namespace
    name = Column(String(255), nullable=False)           # as displayed
    full_name_key = Column(String(511), nullable=False)  # lower(owner/name), for uniqueness
    url = Column(Text, nullable=False)                   # canonical https URL
    default_branch = Column(String(255), nullable=False)
    default_branch_is_user_set = Column(Boolean, nullable=False, default=False, server_default=false())
    verification_status = Column(String(20), nullable=False, default="unchecked", server_default="unchecked")
    verified_at = Column(DateTime(timezone=True), nullable=True)  # last check, whatever its result
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", "provider", "full_name_key", name="uq_repo_project_provider_key"),
        CheckConstraint("provider IN ('github','gitlab')", name="chk_repo_provider"),
        CheckConstraint(
            "verification_status IN ('verified','not_found','unchecked')", name="chk_repo_verification_status"
        ),
    )
