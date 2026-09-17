from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field
from src.organization.models.member import OrganizationMember

Role = Literal[OrganizationMember.ROLES]  # type: ignore[valid-type]


class InvitationCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    role: Role = "member"


class InvitationOut(BaseModel):
    id: int
    organization_id: int
    email: str
    role: str
    invited_by_user_id: int
    token: str
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
