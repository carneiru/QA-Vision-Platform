from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class ApiKeyCreated(BaseModel):
    """The only response that ever carries the full key."""

    id: int
    name: str
    key_prefix: str
    key: str
    created_at: datetime
