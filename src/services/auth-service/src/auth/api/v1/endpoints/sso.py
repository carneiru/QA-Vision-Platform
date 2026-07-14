from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.auth.api import deps
from auth.service.sso_service import SSOService
from auth.service.auth_service import AuthService
from auth.service.user_service import UserService
from auth.schemas.auth import GoogleLoginRequest, GitHubLoginRequest, AzureLoginRequest, Token
from auth.models.user import User
from auth.models.oauth import OAuthAccount
from auth.core.config import settings
from datetime import timedelta

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
    google_data = asyncio.run(SSOService.validate_google_token(request.credential))
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
        # User exists, check if OAuth account exists
        oauth_account = db.query(OAuthAccount).filter(
            OAuthAccount.user_id == user.id,
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id
        ).first()
        
        if not oauth_account:
            # Link existing account to OAuth
            oauth_account = OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id
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
    refresh_token = AuthService.create_refresh_token_for_user(user)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# Similar endpoints for GitHub and Azure would follow the same pattern
@router.post("/github", response_model=Token)
def github_login(
    *,
    db: Session = Depends(deps.get_db),
    request: GitHubLoginRequest
):
    # Implementation similar to Google but for GitHub
    # For now, return placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="GitHub SSO not yet implemented"
    )

@router.post("/azure", response_model=Token)
def azure_login(
    *,
    db: Session = Depends(deps.get_db),
    request: AzureLoginRequest
):
    # Implementation similar to Google but for Azure AD
    # For now, return placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Azure AD SSO not yet implemented"
    )
