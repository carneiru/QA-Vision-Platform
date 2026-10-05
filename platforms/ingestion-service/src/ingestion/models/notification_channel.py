from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String, true
from sqlalchemy.sql import func

from src.ingestion.db.base import Base


class NotificationChannel(Base):
    """Where a project's failed runs are announced. `url` is a webhook URL (a bearer secret: never
    returned) or, for email, the recipient addresses."""

    __tablename__ = "notification_channels"
    __table_args__ = (CheckConstraint("kind IN ('slack','teams','webhook','email')", name="chk_notification_kind"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    kind = Column(String(10), nullable=False)
    url = Column(String(2048), nullable=False)
    # Exact branch to announce; null announces every branch
    branch = Column(String(255), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True, server_default=true())
    last_status = Column(String(10), nullable=True)  # delivered / failed
    last_error = Column(String(500), nullable=True)
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
