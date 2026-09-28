from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Branch = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255, pattern=r"^\S+$")]


class RepositoryCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    default_branch: Optional[Branch] = None


class RepositoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    provider: str
    owner: str
    name: str
    url: str
    default_branch: str
    default_branch_is_user_set: bool
    verification_status: str
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
