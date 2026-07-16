"""
Configuration Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ConfigurationBase(BaseModel):
    environment_id: str
    name: str
    description: Optional[str] = None
    configuration_type: str = Field(..., regex="^(database|network|security|application|infrastructure|other)$")
    configuration_data: dict = {}
    version: str = "1.0"
    status: str = Field(default="active", regex="^(active|inactive|archived)$")
    tags: List[str] = []

class ConfigurationCreate(ConfigurationBase):
    created_by: str

class ConfigurationUpdate(BaseModel):
    environment_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    configuration_type: Optional[str] = Field(None, regex="^(database|network|security|application|infrastructure|other)$")
    configuration_data: Optional[dict] = None
    version: Optional[str] = None
    status: Optional[str] = Field(None, regex="^(active|inactive|archived)$")
    tags: Optional[List[str]] = None
    updated_by: Optional[str] = None

class ConfigurationResponse(ConfigurationBase):
    id: str
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True