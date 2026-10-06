from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.casebook.service.import_service import normalise_path


class ImportFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    content: str

    @field_validator("path", "content")
    @classmethod
    def _no_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("must not contain a NUL character")  # PostgreSQL text cannot store it
        return value

    @field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        return normalise_path(value)  # ValueError -> 422


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: List[ImportFile] = Field(min_length=1)
    full: bool = False
    allow_mass_archive: bool = False
    expected_plan_hash: Optional[str] = Field(None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("files")
    @classmethod
    def _unique_paths(cls, files: List[ImportFile]) -> List[ImportFile]:
        paths = [f.path for f in files]
        if len(paths) != len(set(paths)):
            raise ValueError("the same path appears twice")
        return files


class ImportIssueOut(BaseModel):
    path: str
    line: Optional[int] = None
    message: str


class ImportItemOut(BaseModel):
    action: Literal["create", "update", "unchanged", "move", "reactivate", "archive", "skip"]
    path: str
    scenario: Optional[str] = None
    case_number: Optional[int] = None


class ImportResult(BaseModel):
    plan_hash: str
    summary: dict
    items: List[ImportItemOut]
    errors: List[ImportIssueOut]
    warnings: List[ImportIssueOut]
