from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    ci_provider: str
    ci_run_url: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    environment: Optional[str] = None
    agent_version: Optional[str] = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    total: int
    passed: int
    failed: int
    skipped: int
    errored: int
    created_at: datetime


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_key: str
    suite: str
    class_name: str
    name: str
    status: str
    duration_ms: int
    message: Optional[str] = None
    details: Optional[str] = None
    truncated: bool
    redacted: bool
    file: Optional[str] = None


class RunDetail(RunOut):
    results: list[ResultOut]
