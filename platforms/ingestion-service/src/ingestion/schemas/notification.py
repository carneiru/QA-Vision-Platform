from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Branch = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]


class ChannelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    kind: Literal["slack", "teams", "webhook"]
    url: str = Field(max_length=2048)
    branch: Optional[Branch] = None


class ChannelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[Name] = None
    enabled: Optional[bool] = None
    branch: Optional[Branch] = None


class ChannelOut(BaseModel):
    """Never the URL: it is a bearer secret. `target` shows its host and last 4 characters."""

    id: int
    name: str
    kind: str
    target: str
    branch: Optional[str] = None
    enabled: bool
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    last_sent_at: Optional[datetime] = None


class TestOutcome(BaseModel):
    status: str
    error: Optional[str] = None
