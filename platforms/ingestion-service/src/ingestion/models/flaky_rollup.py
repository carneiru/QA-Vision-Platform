from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint

from src.ingestion.db.base import Base


class FlakyDaily(Base):
    """One day of one test on one branch: everything flaky detection needs,
    recombinable across days without rescanning executions."""

    __tablename__ = "flaky_daily"
    __table_args__ = (
        UniqueConstraint("project_id", "day", "branch", "test_key", name="uq_flaky_daily"),
    )

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    branch = Column(String(255), nullable=True)
    test_key = Column(String(500), nullable=False)
    suite = Column(String(500), nullable=False)
    class_name = Column(String(500), nullable=False)
    name = Column(String(1000), nullable=False)
    runs = Column(Integer, nullable=False)      # non-skipped executions that day
    flips = Column(Integer, nullable=False)     # outcome changes within the day
    failures = Column(Integer, nullable=False)  # failed + errored that day
    first_status = Column(String(20), nullable=False)  # pass/fail outcome of the day's first execution
    last_status = Column(String(20), nullable=False)   # raw status of the day's last execution
    last_outcome = Column(String(10), nullable=False)  # pass/fail outcome of the day's last execution
    last_seen = Column(DateTime(timezone=True), nullable=False)



class FlakyRollupDay(Base):
    """Marker: this project-day was computed (even when it produced no rows)."""

    __tablename__ = "flaky_rollup_days"
    __table_args__ = (UniqueConstraint("project_id", "day", name="uq_flaky_rollup_days"),)

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False, index=True)
    day = Column(Date, nullable=False)
