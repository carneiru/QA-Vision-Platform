from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.auth.api import deps
import logging
from src.auth.service.sso_service import SSOService, SSOConfigurationError
from src.auth.service.auth_service import AuthService
from src.auth.service.user_service import UserService
from src.auth.schemas.auth import GoogleLoginRequest, Token
from src.auth.schemas.user import UserCreate  # used when SSO creates a first-time user
from src.auth.models.oauth import OAuthAccount
from src.auth.config import settings
from datetime import timedelta

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/google", response_model=Token)
def google_login(
    *,
    db: Session = Depends(deps.get_db),
    request: GoogleLoginRequest
):
    """
    Authenticate with Google ID token.
    """
    # Import here to avoid circular imports
    import asyncio
    
    # Validate Google token
    google_data = None
    try:
        google_data = asyncio.run(SSOService.validate_google_token(request.credential))
    except SSOConfigurationError:
        # Our misconfiguration, not the caller's bad input.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google SSO is not configured",
        )
    except Exception:
        # Deliberately opaque: the underlying text carries JWKS URLs and internal state, and
        # this endpoint answers unauthenticated callers.
        logger.warning("Google ID token verification failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Google token",
        )
    
    if not google_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Google token"
        )
    
    # Check if user exists with this email/provider
    email = google_data["email"]
    provider = google_data["provider"]
    provider_user_id = google_data["provider_user_id"]
    
    # Try to find existing user by email
    user = UserService.get_user_by_email(db, email)
    
    if user:
        # A verified Google email proves control of the mailbox, not ownership of whatever
        # local account happens to share that address. Linking on email alone is a
        # pre-registration takeover: an attacker registers victim@corp.com with a password
        # before the victim ever signs up, the victim then arrives via Google, gets attached
        # to that row, and the attacker keeps password access to everything they do there.
        existing_link = db.query(OAuthAccount).filter(
            OAuthAccount.user_id == user.id,
            OAuthAccount.provider == provider,
        ).first()

        if existing_link:
            if existing_link.provider_user_id != provider_user_id:
                # Same address, different Google identity -- a recycled or aliased mailbox.
                # Whoever is already linked keeps the account.
                logger.warning(
                    "Google sub mismatch for user %s: linked %s, presented %s",
                    user.id, existing_link.provider_user_id, provider_user_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This account is linked to a different Google identity",
                )
        elif user.hashed_password is not None:
            # There is a password on this account, so it has an owner who is not necessarily
            # the caller. Auto-linking is only safe for a passwordless row, which has no
            # independent credential to hijack.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An account with this email already exists. Sign in with your password "
                    "to link Google to it."
                ),
            )
        else:
            oauth_account = OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
            )
            db.add(oauth_account)
            db.commit()
    else:
        # Create new user
        user_in = UserCreate(
            email=email,
            full_name=google_data.get("full_name"),
            password=None  # SSO user - no password
        )
        user = UserService.create_user(db, user_in)
        
        # Create OAuth account link
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id
        )
        db.add(oauth_account)
        db.commit()
    
    # Generate tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token_for_user(user, expires_delta=access_token_expires)
    refresh_token = AuthService.create_user_session(db, user).token
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }



# GitHub and Azure SSO are not implemented. They previously called SSOService methods that
# did not exist (validate_github_token / validate_azure_token vs. the service's
# exchange_github_code / exchange_azure_code), and the GitHub handler additionally contained
# a syntax error, so this module never imported. Rather than resurrect mock handlers that
# returned hardcoded identities, both now fail honestly until real OAuth exchanges are built.


@router.post("/github", response_model=Token)
def github_login():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="GitHub SSO is not implemented",
    )


@router.post("/azure", response_model=Token)
def azure_login():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Azure SSO is not implemented",
    )
