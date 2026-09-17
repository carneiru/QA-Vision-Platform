from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from src.organization.models.member import OrganizationMember as OrganizationMemberModel


class MemberCreate(BaseModel):
    user_id: int
    role: str = Field(default="member")


class MemberOut(BaseModel):
    id: int
    organization_id: int
    user_id: int
    role: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
