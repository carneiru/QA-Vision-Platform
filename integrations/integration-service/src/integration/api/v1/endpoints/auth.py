from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from src.integration-service.api import deps
from src.integration-service.service.auth_service import AuthService
from src.integration-service.service.user_service import UserService
from src.integration-service.schemas.auth import LoginRequest, Token, PasswordResetRequest, PasswordResetConfirm
from src.integration-service.schemas.user import UserCreate, User
from src.integration-service.config import settings

router = APIRouter()


@router.post("/register", response_model=User)
def register_user(
    user_in: UserCreate,
    db: Session = Depends(deps.get_db)
):
    """
    Create new user account.
    """
    user = UserService.create_user(db, user_in)
    return user


@router.post("/login", response_model=Token)
def login_access_token(
    *,
    db: Session = Depends(deps.get_db),
    form_data: LoginRequest
):
    """
    OAuth2 compatible token login, get an access and refresh token.
    """
    user = AuthService.authenticate_user(db, form_data.email, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token_for_user(user, expires_delta=access_token_expires)
    refresh_token = AuthService.create_refresh_token_for_user(user)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh-token", response_model=Token)
def refresh_access_token(
    *,
    db: Session = Depends(deps.get_db),
    refresh_token: str
):
    """
    Refresh access token using refresh token.
    """
    db_token = AuthService.verify_refresh_token(db, refresh_token)
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = UserService.get_user_by_id(db, db_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Revoke old refresh token
    AuthService.revoke_refresh_token(db, refresh_token)
    
    # Issue new tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token_for_user(user, expires_delta=access_token_expires)
    new_refresh_token = AuthService.create_refresh_token_for_user(user)
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@router.post("/logout")
def logout_user(
    *,
    db: Session = Depends(deps.get_db),
    refresh_token: str,
    current_user: dict = Depends(deps.get_current_active_user)
):
    """
    Logout user by revoking refresh token.
    """
    success = AuthService.revoke_refresh_token(db, refresh_token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )
    return {"message": "Successfully logged out"}


@router.post("/forgot-password")
def initiate_password_reset(
    *,
    db: Session = Depends(deps.get_db),
    request: PasswordResetRequest
):
    """
    Initiate password reset process.
    """
    user = UserService.get_user_by_email(db, request.email)
    if user:
        # In a real application, we would send an email here
        # For now, we just return a success message to avoid revealing whether an email exists
        pass
    # Always return the same message to prevent email enumeration
    return {"message": "If the email exists in our system, you will receive a password reset link"}


@router.post("/reset-password")
def reset_password(
    *,
    db: Session = Depends(deps.get_db),
    request: PasswordResetConfirm
):
    """
    Reset password using reset token.
    """
    # In a real application, we would validate the token and reset the password
    # For now, we just return a success message
    return {"message": "Password has been reset successfully"}
