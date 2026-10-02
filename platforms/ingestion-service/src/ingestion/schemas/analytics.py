"""Response models for /projects/{id}/analytics/*. No class name may start with "Test":
pytest would try to collect it wherever a test module imports it."""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


class TrendDay(BaseModel):
    date: str
    runs: int
    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    pass_rate: Optional[float] = None
    avg_run_duration_ms: Optional[int] = None
    max_run_duration_ms: Optional[int] = None


class TrendsOut(BaseModel):
    tz: str
    days: List[TrendDay]


class CountsOut(BaseModel):
    runs: int
    passed: int
    failed: int
    errored: int
    skipped: int
    pass_rate: Optional[float] = None
    avg_duration_ms: Optional[int] = None


class StatsRowOut(CountsOut):
    test_key: str
    suite: str
    class_name: str
    name: str
    last_status: str
    last_seen: datetime


class ExecutionOut(BaseModel):
    run_id: int
    started_at: datetime
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    environment: Optional[str] = None
    status: str
    duration_ms: int
    message: Optional[str] = None


class HistoryOut(BaseModel):
    test_key: str
    suite: str
    class_name: str
    name: str
    summary: CountsOut
    executions: List[ExecutionOut]


class BranchStatsOut(BaseModel):
    branch: Optional[str] = None
    runs: int
    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    pass_rate: Optional[float] = None
    last_seen: datetime


class CommitRef(BaseModel):
    commit_sha: str
    environment: Optional[str] = None


class MuteIn(BaseModel):
    test_key: str


class FlakyOut(BaseModel):
    test_key: str
    muted: bool = False
    suite: str
    class_name: str
    name: str
    reason: Literal["same_commit", "flips"]
    commits: List[CommitRef]
    flips: Optional[int] = None
    flip_rate: Optional[float] = None
    runs: int
    last_status: str
    last_seen: datetime
