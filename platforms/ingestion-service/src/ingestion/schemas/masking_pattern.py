from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MaskingPatternCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=64)
    pattern: str = Field(max_length=1024)  # the real limit (256) is checked with a readable reason


class MaskingPatternOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    pattern: str
    created_at: Optional[datetime] = None


class MaskingPreviewIn(MaskingPatternCreate):
    sample: str = Field(max_length=10_000)


class MaskingPreviewOut(BaseModel):
    masked: str
    matches: int
