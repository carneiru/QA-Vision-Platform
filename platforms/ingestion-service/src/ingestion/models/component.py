from sqlalchemy import Column, ForeignKey, Integer, String

from src.ingestion.db.base import Base


class RunComponent(Base):
    """One repo/version the run exercised (e.g. the product build an E2E
    suite ran against). Dormant data for cross-repo analysis: captured at
    ingest, correlated later."""

    __tablename__ = "run_components"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    sha = Column(String(40), nullable=False)
