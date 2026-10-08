"""Request body of POST /projects/{id}/analytics/report. No class name may start with "Test"."""
from datetime import date
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from src.ingestion.models.run import CI_PROVIDERS

NO_NUL = r"^[^\x00]*$"
SECTIONS = ("summary", "failure_causes", "regressions", "tests", "duration")
MAX_KEYS = 20_000
MAX_URLS = 5_000

Key = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{64}$")]
Url = Annotated[str, StringConstraints(max_length=2048, pattern=NO_NUL)]


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: date = Field(alias="from")
    to: date
    tz: str = Field("UTC", min_length=1, max_length=64)
    branch: Optional[Annotated[str, StringConstraints(max_length=255, pattern=NO_NUL)]] = None
    environment: Optional[Annotated[str, StringConstraints(max_length=100, pattern=NO_NUL)]] = None
    ci_provider: Optional[str] = None
    origin: Literal["any", "ci", "qeos"] = "any"
    requested_run_urls: Optional[List[Url]] = Field(None, max_length=MAX_URLS)
    test_keys: Optional[List[Key]] = Field(None, min_length=1, max_length=MAX_KEYS)
    sections: List[Literal["summary", "failure_causes", "regressions", "tests", "duration"]] = Field(
        min_length=1, max_length=len(SECTIONS))
    bucket: Literal["auto", "day", "week"] = "auto"

    @field_validator("ci_provider")
    @classmethod
    def known_provider(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in CI_PROVIDERS:
            raise ValueError(f"ci_provider must be one of {', '.join(CI_PROVIDERS)}")
        return value

    @field_validator("sections")
    @classmethod
    def unique_sections(cls, value: List[str]) -> List[str]:
        if len(set(value)) != len(value):
            raise ValueError("sections must be unique")
        return value

    @model_validator(mode="after")
    def urls_with_origin(self) -> "ReportIn":
        if self.origin != "any" and self.requested_run_urls is None:
            raise ValueError("requested_run_urls is required with origin")
        return self
