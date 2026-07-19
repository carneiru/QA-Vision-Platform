from datetime import timedelta
from typing import Optional
from sqlalchemy.orm import Session
from src.administration-service.models.user import User
from src.administration-service.models.session import RefreshToken
from src.administration-service.utils.tokens import create_access_token, create_refresh_token, decode_token
from src.administration-service.utils.security import verify_password
from src.administration-service.service.user_service import UserService
from src.administration-service.config import settings
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
    def create_refresh_token_for_user(user: User) -> str:
        return create_refresh_token(data={"sub": str(user.id)})
    
    @staticmethod
    def create_user_session(db: Session, user: User, user_agent: str = None, ip_address: str = None) -> RefreshToken:
        # Generate a secure random token
        refresh_token = secrets.token_urlsafe(32)
        
        # Create refresh token record
        db_token = RefreshToken(
            token=refresh_token,
            user_id=user.id,
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
        return db_token
    
    @staticmethod
    def revoke_refresh_token(db: Session, token: str) -> bool:
        db_token = db.query(RefreshToken).filter(RefreshToken.token == token).first()
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
