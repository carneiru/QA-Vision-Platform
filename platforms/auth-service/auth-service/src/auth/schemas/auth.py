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

class RefreshTokenRequest(BaseModel):
    # /auth/refresh-token and /auth/logout previously declared `refresh_token: str` as a bare
    # parameter, which FastAPI reads as a QUERY parameter -- so a JSON body could never
    # satisfy them and both always returned 422.
    refresh_token: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    password: str = Field(..., min_length=8)