from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
import logging
from src.auth.api import deps
from src.auth.service.auth_service import AuthService
from src.auth.service.user_service import UserService
from src.auth.schemas.auth import LoginRequest, Token, PasswordResetRequest, PasswordResetConfirm, RefreshTokenRequest
from src.auth.schemas.user import UserCreate, RegisterRequest, User
from src.auth.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=User)
def register_user(
    user_in: RegisterRequest,
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
    refresh_token = AuthService.create_user_session(db, user).token
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh-token", response_model=Token)
def refresh_access_token(
    *,
    db: Session = Depends(deps.get_db),
    request: RefreshTokenRequest
):
    """
    Refresh access token using refresh token.
    """
    db_token, outcome = AuthService.claim_refresh_token(db, request.refresh_token)

    if outcome == "replayed":
        # An already-rotated token is being presented. Rotation alone does not help here: if
        # a token was stolen, the thief rotates it and the owner's next refresh is what
        # fails, leaving the thief's chain live and the owner locked out. Treat any replay as
        # a compromised chain and end every session for that user, so both parties have to
        # authenticate again and only the one who knows the password gets back in.
        logger.warning("Refresh token replay for user %s; revoking all sessions", db_token.user_id)
        AuthService.revoke_all_user_sessions(db, db_token.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token was already used; all sessions have been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if outcome != "claimed":
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

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )


    # Issue new tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token_for_user(user, expires_delta=access_token_expires)
    new_refresh_token = AuthService.create_user_session(db, user).token
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@router.post("/logout")
def logout_user(
    *,
    db: Session = Depends(deps.get_db),
    request: RefreshTokenRequest,
    current_user: dict = Depends(deps.get_current_active_user)
):
    """
    Logout user by revoking refresh token.
    """
    success = AuthService.revoke_refresh_token(db, request.refresh_token, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )
    return {"message": "Successfully logged out"}


# Password reset is not implemented. There is no reset-token model, no issuance, no
# validation and no mail transport. Both handlers used to return success anyway:
# /forgot-password promised a link it never sent, and /reset-password answered "Password has
# been reset successfully" without touching the password. That is the worse half -- a user
# told their password was reset stops treating the old one as live, and an operator reading
# the endpoint list believes account recovery exists. They now fail honestly, the same way
# the GitHub and Azure SSO handlers do.


@router.post("/forgot-password")
def initiate_password_reset(request: PasswordResetRequest):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset is not implemented",
    )


@router.post("/reset-password")
def reset_password(request: PasswordResetConfirm):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset is not implemented",
    )
