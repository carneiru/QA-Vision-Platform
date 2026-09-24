from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import logging
import secrets
from src.auth.api import deps
from src.auth.service.auth_service import AuthService
from src.auth.service.user_service import UserService
from src.auth.service.email_sender import EmailSender
from src.auth.schemas.auth import (
    LoginRequest, Token, PasswordResetRequest, PasswordResetConfirm, RefreshTokenRequest,
    ResendVerificationRequest,
)
from src.auth.schemas.user import RegisterRequest
from src.auth.models.pending_registration import PendingRegistration
from src.auth.models.user import User
from src.auth.utils.password import get_password_hash
from src.auth.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
def register_user(
    user_in: RegisterRequest,
    db: Session = Depends(deps.get_db)
):
    """
    Begin registration. Creates a PendingRegistration rather than a User -- the address is
    not claimed until the verification link is used. See
    docs/superpowers/specs/2026-09-24-auth-service-email-verification-design.md.

    Each attempt is its own independent row (email is not UNIQUE on this table). A prior
    version rotated an existing pending row in place on a second attempt -- that let an
    unauthenticated attacker overwrite a pending registration's PASSWORD while its
    verification link kept going to the real mailbox. See the spec's "Amendment: rotation
    allowed credential injection" for the exploit this closes.
    """
    if UserService.get_user_by_email(db, user_in.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    token = secrets.token_urlsafe(32)
    pending = PendingRegistration(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        token=token,
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS),
    )
    db.add(pending)
    db.commit()

    verification_link = (
        f"{settings.BASE_URL}{settings.API_V1_STR}/auth/verify-email?token={token}"
    )
    EmailSender.send_verification_email(user_in.email, verification_link)

    return {"message": "Check your email to complete registration"}


@router.get("/verify-email", response_model=Token)
def verify_email(token: str, db: Session = Depends(deps.get_db)):
    """
    Complete registration: turn a valid, unexpired PendingRegistration into a User and
    auto-login.
    """
    pending = db.query(PendingRegistration).filter(
        PendingRegistration.token == token
    ).first()
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    expires_at = pending.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        # Worthless once expired -- deleting it releases the address for a clean retry
        # rather than leaving a dead row a future registration has to keep rotating past.
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    if UserService.get_user_by_email(db, pending.email) is not None:
        # The address was claimed by another path -- most likely Google SSO, whose
        # email_verified claim is already equivalent proof -- while this registration sat
        # unverified. The stale attempt is discarded; the real account is untouched.
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered",
        )

    user = User(
        email=pending.email,
        hashed_password=pending.hashed_password,
        full_name=pending.full_name,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.delete(pending)
    # Every OTHER attempt for this address (an attacker's separate registration, or an
    # earlier one the registrant abandoned) is now moot. Clean them up so none of them can
    # be independently clicked later -- excluded by id since `pending` is already staged
    # for deletion above and this must not touch that same row twice.
    db.query(PendingRegistration).filter(
        PendingRegistration.email == pending.email,
        PendingRegistration.id != pending.id,
    ).delete(synchronize_session=False)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race against a concurrent claim of this email between the check above and
        # this commit.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered",
        )
    db.refresh(user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token_for_user(
        user, expires_delta=access_token_expires
    )
    refresh_token = AuthService.create_user_session(db, user).token

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/resend-verification")
def resend_verification(request: ResendVerificationRequest, db: Session = Depends(deps.get_db)):
    """
    Resend a verification link. Always answers the same way regardless of whether a
    pending registration exists, matching /forgot-password's enumeration-prevention.

    Serves the OLDEST still-unexpired attempt for the address, never the newest. Since
    registration no longer rotates (see the spec's Amendment), more than one attempt can
    exist for one address at once; picking the newest would hand the mailbox owner a link
    for whichever attempt happened most recently -- which could be an attacker's. Picking
    the oldest means the original registrant's own attempt is always what gets resent,
    since nothing an attacker registers afterward is ever older than it.
    """
    now = datetime.now(timezone.utc)
    # Fetched and filtered in Python, not in the SQL WHERE clause: this codebase's other
    # expiry checks (verify_refresh_token, claim_refresh_token, verify_email's own check)
    # all normalize SQLite's naive datetimes in Python before comparing, because comparing
    # a timezone-aware Python value against a SQLite column in the query itself is
    # unreliable. Matching that pattern here rather than introducing a new one.
    candidates = db.query(PendingRegistration).filter(
        PendingRegistration.email == request.email
    ).order_by(PendingRegistration.created_at.asc()).all()

    pending = None
    for candidate in candidates:
        expires_at = candidate.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at > now:
            pending = candidate
            break

    if pending is not None:
        pending.token = secrets.token_urlsafe(32)
        pending.expires_at = now + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS)
        db.commit()
        verification_link = (
            f"{settings.BASE_URL}{settings.API_V1_STR}/auth/verify-email?token={pending.token}"
        )
        EmailSender.send_verification_email(request.email, verification_link)

    return {
        "message": "If a pending registration exists for this email, a new verification link has been sent"
    }


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
