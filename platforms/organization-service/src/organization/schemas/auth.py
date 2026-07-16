# src/services/auth-service/src/auth/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    credential: str

class GitHubLoginRequest(BaseModel):
    code: str

class AzureLoginRequest(BaseModel):
    code: str
    tenant_id: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    password: str = Field(..., min_length=8)