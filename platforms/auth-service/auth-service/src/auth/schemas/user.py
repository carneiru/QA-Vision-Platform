# src/services/auth-service/src/auth/schemas/user.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False

class UserCreate(UserBase):
    # Optional because SSO creates users with no password at all (the column is nullable for
    # exactly that case, and authenticate_user refuses password login when no hash exists).
    # Registration still enforces a password -- see RegisterRequest below.
    password: Optional[str] = Field(None, min_length=8)

class RegisterRequest(UserBase):
    # Self-registration must always set a password. UserCreate allows None so the SSO path
    # can create passwordless accounts; without this split, /auth/register would accept a
    # passwordless signup that can never be logged into -- letting anyone squat an address
    # its real owner could then never register.
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class UserSelfUpdate(BaseModel):
    # What a user may change about their own account. Deliberately excludes is_active and
    # is_superuser: PUT /users/me accepted the full UserUpdate, and update_user setattr'd
    # whatever arrived, so any user could POST {"is_superuser": true} and promote themselves.
    email: Optional[EmailStr] = None
    # Same floor registration enforces. Without it this route accepted a one-character
    # password, which is a way to downgrade an account's credential rather than change it.
    password: Optional[str] = Field(None, min_length=8)
    # Required when `password` is set. A stolen access token is bearer-only and lives for
    # days; without this, holding one for a minute is enough to take the account permanently
    # by replacing the password the real owner logs in with.
    current_password: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None

class UserInDB(UserBase):
    id: int
    hashed_password: str
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class User(UserBase):
    id: int
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
