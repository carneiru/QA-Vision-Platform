from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field
from src.organization.models.member import OrganizationMember

Role = Literal[OrganizationMember.ROLES]  # type: ignore[valid-type]


class InvitationCreate(BaseModel):
    email: EmailStr
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


class InvitationSummary(BaseModel):
    """Same fields as InvitationOut minus the raw token.

    Used for the list endpoint so a plain admin can't read a pending invitation's token
    and hand it to an account they control to mint a role they couldn't grant directly
    (see finding #1 in the final-review-fix report). The token is returned ONLY in the
    create (201) response.
    """

    id: int
    organization_id: int
    email: str
    role: str
    invited_by_user_id: int
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
