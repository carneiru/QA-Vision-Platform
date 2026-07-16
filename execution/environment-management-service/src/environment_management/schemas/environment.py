"""
Environment Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class EnvironmentBase(BaseModel):
    name: str
    description: Optional[str] = None
    environment_type: str = Field(..., regex="^(dev|test|staging|prod|local|other)$")
    status: str = Field(default="available", regex="^(available|provisioning|provisioned|deprovisioning|deprovisioned|maintenance|failed)$")
    infrastructure_as_code: Optional[str] = Field(None, regex="^(terraform|cloudformation|ansible|pulumi|other)$")
    configuration: dict = {}
    tags: List[str] = []

class EnvironmentCreate(EnvironmentBase):
    created_by: str

class EnvironmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    environment_type: Optional[str] = Field(None, regex="^(dev|test|staging|prod|local|other)$")
    status: Optional[str] = Field(None, regex="^(available|provisioning|provisioned|deprovisioning|deprovisioned|maintenance|failed)$")
    infrastructure_as_code: Optional[str] = Field(None, regex="^(terraform|cloudformation|ansible|pulumi|other)$")
    configuration: Optional[dict] = None
    tags: Optional[List[str]] = None
    updated_by: Optional[str] = None

class EnvironmentResponse(EnvironmentBase):
    id: str
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    provisioned_at: Optional[datetime] = None
    deprovisioned_at: Optional[datetime] = None

    class Config:
        orm_mode = True