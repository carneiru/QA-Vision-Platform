"""Running tests from QA Vision: the CI target and run requests."""
import re
from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

REPO_PATTERN = r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$"
WORKFLOW_PATTERN = r"^[A-Za-z0-9._-]{1,100}\.ya?ml$"
TOKEN = re.compile(r"^[A-Za-z0-9_]{20,255}$")
# git check-ref-format: no whitespace or control characters (DEL included), none of ~ ^ : ? * [ and backslash
BRANCH_FORBIDDEN = re.compile(r"[\x00-\x20\x7f~^:?*\[\\]")
DEFAULT_WORKFLOW = "qa-vision-run.yml"


class CiTargetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo: Annotated[str, StringConstraints(strip_whitespace=True, pattern=REPO_PATTERN)]
    workflow: Annotated[str, StringConstraints(strip_whitespace=True, pattern=WORKFLOW_PATTERN)] = DEFAULT_WORKFLOW
    ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] = "main"
    # Checked by clean_token in the endpoint, never by pydantic: pydantic's 422 echoes the input back
    token: Optional[str] = None

    @field_validator("repo")
    @classmethod
    def _not_dots(cls, value: str) -> str:
        if value.split("/")[1] in (".", ".."):
            raise ValueError("not a repository name")
        return value

    @field_validator("ref")
    @classmethod
    def _branch_name(cls, value: str) -> str:
        if (BRANCH_FORBIDDEN.search(value) or ".." in value or "@{" in value or "//" in value
                or value.startswith(("/", "-")) or value.endswith(("/", "."))
                or any(part.endswith(".lock") for part in value.split("/"))):
            raise ValueError("not a branch name (see git check-ref-format)")
        return value


def clean_token(raw: Optional[str]) -> Optional[str]:
    """Strip what a paste adds (spaces, a newline). None or empty means 'keep the stored token'.
    The error message never contains the value."""
    if raw is None or not raw.strip():
        return None
    token = raw.strip()
    if not TOKEN.match(token):
        raise ValueError("token: not a GitHub token (letters, digits and _ only)")
    return token


class CiTargetChange(BaseModel):
    action: str
    user_id: int
    at: datetime


class CiTargetOut(BaseModel):
    available: bool
    configured: bool
    provider: Optional[str] = None
    repo: Optional[str] = None
    workflow: Optional[str] = None
    ref: Optional[str] = None
    token_last4: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_change: Optional[CiTargetChange] = None


MAX_RUN_CASES = 200


class RunRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_numbers: Optional[Annotated[List[Annotated[int, Field(ge=1)]], Field(min_length=1, max_length=MAX_RUN_CASES)]] = None
    suite_id: Optional[int] = Field(None, ge=1)

    @model_validator(mode="after")
    def _one_of(self):
        if (self.case_numbers is None) == (self.suite_id is None):
            raise ValueError("send case_numbers or suite_id, not both")
        return self


class SelectedCase(BaseModel):
    case_number: int
    path: str
    name: str


class RunRequestOut(BaseModel):
    id: int
    requested_by: int
    requested_at: datetime
    selection: List[SelectedCase]
    case_count: int
    suite_id: Optional[int] = None
    status: str
    conclusion: Optional[str] = None
    github_run_id: Optional[int] = None
    github_run_url: Optional[str] = None
    stopped_by: Optional[int] = None
    stopped_at: Optional[datetime] = None
    error: Optional[str] = None
    checked_at: Optional[datetime] = None
    skipped_manual: int = 0  # manual cases a whole-suite run left out
    refreshing: bool  # true while the server still checks GitHub for it: poll


class RunRequestList(BaseModel):
    total: int
    items: List[RunRequestOut]
