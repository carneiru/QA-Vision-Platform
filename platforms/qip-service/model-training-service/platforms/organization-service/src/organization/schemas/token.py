# src/services/auth-service/src/auth/schemas/token.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None

class TokenPayload(BaseModel):
    sub: str
    exp: int
