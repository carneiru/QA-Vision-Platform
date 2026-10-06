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


class GroupedTestOut(BaseModel):
    id: int
    test_key: str
    suite: str
    class_name: str
    name: str
    status: str


class CauseHistory(BaseModel):
    """The cause across this run and up to 19 earlier runs of the same branch."""

    window: int            # runs looked at, this one included
    seen_in: int           # of those, how many had this cause
    streak: int            # consecutive runs up to this one with it; 1 = it is new
    since_run_id: int      # where the streak started
    since_started_at: datetime


class FailureGroupOut(BaseModel):
    """Failed and errored tests that share one cause (analytics/signature.py)."""

    signature: str
    headline: Optional[str] = None  # the first message's first line; None when there is no message
    count: int
    failed: int
    errored: int
    tests: list[GroupedTestOut]  # the first MAX_GROUP_TESTS; `count` has them all
    history: CauseHistory


class FailureGroupsOut(BaseModel):
    total: int
    groups: list[FailureGroupOut]


class RunDetail(RunOut):
    results: list[ResultOut]
    changes: list[ChangedFileOut] = []
    components: list[ComponentOut] = []


class CompareItem(BaseModel):
    test_key: str
    suite: str
    class_name: str
    name: str
    base_status: Optional[str] = None  # None: not in the base run
    head_status: Optional[str] = None  # None: not in the head run
    base_duration_ms: Optional[int] = None
    head_duration_ms: Optional[int] = None
    message: Optional[str] = None  # the failing side's message, first line only


class RunComparison(BaseModel):
    """Head compared with base, test by test (each test's last attempt in each run)."""

    base: RunOut
    head: RunOut
    counts: dict[str, int]
    new_failures: list[CompareItem]
    fixed: list[CompareItem]
    still_failing: list[CompareItem]
    slower: list[CompareItem]
    added: list[CompareItem]
    removed: list[CompareItem]
