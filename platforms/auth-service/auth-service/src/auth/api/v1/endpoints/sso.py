from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
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


def _link_or_create_user(db: Session, google_data: dict, email: str, provider: str,
                         provider_user_id: str):
    """Resolve a Google identity that is not yet linked to any account.

    Reached only when no OAuthAccount matches this provider and `sub`.
    """
    user = UserService.get_user_by_email(db, email)

    if user is None:
        user_in = UserCreate(
            email=email,
            full_name=google_data.get("full_name"),
            password=None,  # SSO user -- no password
        )
        # One transaction. These used to be two commits, so a failure on the link left a
        # committed passwordless user with no link -- and since SSO no longer auto-links to
        # an existing account, that orphan answers 409 for its own address forever. A
        # transient database error would have locked an address out permanently.
        user = UserService.create_user(db, user_in, commit=False)
        db.add(OAuthAccount(
            user_id=user.id, provider=provider, provider_user_id=provider_user_id,
        ))
        try:
            db.commit()
        except IntegrityError:
            # Another request created this identity between our lookup and our commit.
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Google account is already linked",
            )
        db.refresh(user)
        return user

    # An account holds this address. A verified Google email proves control of the mailbox,
    # not ownership of whatever local account happens to share it. Linking on email alone is
    # a pre-registration takeover: an attacker registers victim@corp.com with a password
    # before the victim ever signs up, the victim then arrives via Google, gets attached to
    # that row, and the attacker keeps password access to everything they do there.
    existing_link = db.query(OAuthAccount).filter(
        OAuthAccount.user_id == user.id,
        OAuthAccount.provider == provider,
    ).order_by(OAuthAccount.id).first()

    if existing_link:
        # Same address, a different Google identity -- a recycled or aliased mailbox.
        # Whoever is already linked keeps the account.
        logger.warning(
            "Google sub mismatch for user %s: linked %s, presented %s",
            user.id, existing_link.provider_user_id, provider_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is linked to a different Google identity",
        )

    # An unlinked account already holds this address, and nothing here proves the caller owns
    # it. This used to auto-link when the row had no password, on the reasoning that a
    # passwordless row has no credential to hijack. That reasoning was wrong: a passwordless,
    # unlinked row is exactly what pre-provisioning produces -- an administrator seeds
    # ceo@corp.com ahead of time, possibly with is_superuser set -- and auto-linking handed
    # that account to whoever presented a Google token for the address first. Every producer
    # of such a row is either that seeding or a half-failed create, so there is no legitimate
    # case left to serve. Adopting SSO on an existing account needs an authenticated link
    # endpoint, which is not built.
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "An account with this email already exists. Linking Google to an existing "
            "account is not supported yet."
        ),
    )


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
    
    # Resolve by the provider identity first. (provider, provider_user_id) is UNIQUE, so the
    # Google `sub` is the actual identity key here; the email is a mutable attribute of it.
    # Looking up by email first meant a user whose Google address had changed fell through to
    # the create branch, which committed a new user row and only then hit uix_provider_user
    # -- a 500 with an orphaned account left behind.
    linked = db.query(OAuthAccount).filter(
        OAuthAccount.provider == provider,
        OAuthAccount.provider_user_id == provider_user_id,
    ).first()

    if linked:
        # Known identity. The address on the token may have changed since; that does not
        # matter, and is deliberately not written back onto the account.
        user = UserService.get_user_by_id(db, linked.user_id)
        if not user:
            logger.error("OAuth link %s points at missing user %s", linked.id, linked.user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Account is in an inconsistent state",
            )
    else:
        user = _link_or_create_user(db, google_data, email, provider, provider_user_id)
    
    # Password login refuses a deactivated account; SSO did not, so disabling someone left
    # them a working way in for as long as their Google account existed.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

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
