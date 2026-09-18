from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from src.auth.models.user import User
from src.auth.models.session import RefreshToken
from src.auth.utils.tokens import create_access_token, decode_token
from src.auth.utils.security import verify_password
from src.auth.service.user_service import UserService
from src.auth.config import settings
import secrets

class AuthService:
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        return UserService.authenticate_user(db, email, password)
    
    @staticmethod
    def create_access_token_for_user(user: User, expires_delta: Optional[timedelta] = None) -> str:
        return create_access_token(
            data={"sub": str(user.id)}, expires_delta=expires_delta
        )
    
    @staticmethod
    def create_user_session(db: Session, user: User, user_agent: str = None, ip_address: str = None) -> RefreshToken:
        # Generate a secure random token
        refresh_token = secrets.token_urlsafe(32)
        
        # Create refresh token record. expires_at is NOT NULL and was never populated, so
        # every session insert failed its constraint.
        db_token = RefreshToken(
            token=refresh_token,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip_address
        )
        db.add(db_token)
        db.commit()
        db.refresh(db_token)
        return db_token
    
    @staticmethod
    def verify_refresh_token(db: Session, token: str) -> RefreshToken:
        db_token = db.query(RefreshToken).filter(
            RefreshToken.token == token,
            RefreshToken.is_revoked == False
        ).first()
        if not db_token:
            return None
        # Expiry was stored but never checked, so a refresh token would have been accepted
        # forever. SQLite returns naive datetimes for timezone-aware columns; normalize
        # before comparing.
        expires_at = db_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None
        return db_token
    
    @staticmethod
    def claim_refresh_token(db: Session, token: str):
        """Atomically consume a refresh token for rotation.

        Returns (row_or_None, outcome) where outcome is one of "claimed", "replayed",
        "expired" or "unknown".

        Rotation used to be verify-then-revoke across two statements, so two concurrent uses
        of one token could both pass verification and each be issued a live chain. The
        revocation here is a conditional UPDATE: exactly one caller can move a row from
        not-revoked to revoked, and whoever loses that race is told the token was replayed.

        "replayed" is reported separately because it is not an ordinary failure. A token that
        exists but is already revoked means someone is presenting a token that was rotated
        out -- the signature of a stolen token being used alongside its owner's. The caller
        decides what to do about it; this returns the fact.
        """
        db_token = db.query(RefreshToken).filter(RefreshToken.token == token).first()
        if db_token is None:
            return None, "unknown"
        if db_token.is_revoked:
            return db_token, "replayed"

        expires_at = db_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return db_token, "expired"

        claimed = db.query(RefreshToken).filter(
            RefreshToken.token == token,
            RefreshToken.is_revoked == False,
        ).update({RefreshToken.is_revoked: True}, synchronize_session=False)
        db.commit()
        if claimed != 1:
            return db_token, "replayed"
        return db_token, "claimed"

    @staticmethod
    def revoke_refresh_token(db: Session, token: str, user_id: Optional[int]) -> bool:
        # user_id is required rather than defaulting: passing None is the unscoped form,
        # which rotation legitimately needs (it already located the row by value), but a
        # caller must state that intent instead of getting it by forgetting an argument.
        query = db.query(RefreshToken).filter(RefreshToken.token == token)
        if user_id is not None:
            query = query.filter(RefreshToken.user_id == user_id)
        db_token = query.first()
        if db_token:
            db_token.is_revoked = True
            db.commit()
            return True
        return False
    
    @staticmethod
    def revoke_all_user_sessions(db: Session, user_id: int) -> int:
        result = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        ).update({RefreshToken.is_revoked: True})
        db.commit()
        return result
