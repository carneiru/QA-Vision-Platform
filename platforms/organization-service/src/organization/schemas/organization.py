from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    plan_tier: str = "free"


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    plan_tier: Optional[str] = None


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str
    plan_tier: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
