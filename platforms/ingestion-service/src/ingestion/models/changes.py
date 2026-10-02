from sqlalchemy import Column, ForeignKey, Integer, String

from src.ingestion.db.base import Base


class RunChangedFile(Base):
    """One file the uploaded run's commit changed against its base ref."""

    __tablename__ = "run_changed_files"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    path = Column(String(1000), nullable=False)
    status = Column(String(1), nullable=False)  # A/M/D/R/C/T/U, git name-status letters
    additions = Column(Integer, nullable=True)  # null for binary files (numstat "-")
    deletions = Column(Integer, nullable=True)
