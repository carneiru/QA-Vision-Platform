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
    commit_author: Optional[str] = None
    commit_message: Optional[str] = None
    pr_number: Optional[int] = None
    base_branch: Optional[str] = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    total: int
    passed: int
    failed: int
    skipped: int
    errored: int
    change_base_ref: Optional[str] = None
    changed_files: Optional[int] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None
    changes_truncated: Optional[bool] = None
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
    owner: Optional[str] = None


class ChangedFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: str
    status: str
    additions: Optional[int] = None
    deletions: Optional[int] = None


class ComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    sha: str


class RunDetail(RunOut):
    results: list[ResultOut]
    changes: list[ChangedFileOut] = []
    components: list[ComponentOut] = []
