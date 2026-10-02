"""TOTP MFA: enrollment, the five-minute login-challenge token, code checks.

The challenge token is a JWT signed with the service key, marked
purpose="mfa" so an access-token can never stand in for it (and vice versa:
decode_token paths that expect "sub" only won't mint sessions from it).
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
import pyotp
from sqlalchemy.orm import Session

from src.auth.config import settings
from src.auth.models.mfa import MfaRecoveryCode
from src.auth.models.user import User
from src.auth.utils.password import get_password_hash, verify_password

MFA_TOKEN_MINUTES = 5
RECOVERY_CODES = 8
ISSUER = "QA Vision"


def start_enrollment(db: Session, user: User) -> tuple[str, str]:
    """A fresh secret, pending until confirm; re-enrolling replaces it."""
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    user.mfa_enabled = False
    db.commit()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=ISSUER)
    return secret, uri


def _totp_ok(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def confirm_enrollment(db: Session, user: User, code: str) -> Optional[List[str]]:
    if not user.mfa_secret or not _totp_ok(user.mfa_secret, code):
        return None
    db.query(MfaRecoveryCode).filter(MfaRecoveryCode.user_id == user.id).delete()
    plaintexts = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(RECOVERY_CODES)]
    for plain in plaintexts:
        db.add(MfaRecoveryCode(user_id=user.id, code_hash=get_password_hash(plain)))
    user.mfa_enabled = True
    db.commit()
    return plaintexts


def check_code(db: Session, user: User, code: str) -> bool:
    """A current TOTP code, or an unused recovery code (consumed on success)."""
    if user.mfa_secret and _totp_ok(user.mfa_secret, code):
        return True
    rows = (
        db.query(MfaRecoveryCode)
        .filter(MfaRecoveryCode.user_id == user.id, MfaRecoveryCode.used_at.is_(None))
        .all()
    )
    for row in rows:
        if verify_password(code, row.code_hash):
            row.used_at = datetime.now(timezone.utc)
            db.commit()
            return True
    return False


def disable(db: Session, user: User, code: str) -> bool:
    if not check_code(db, user, code):
        return False
    user.mfa_secret = None
    user.mfa_enabled = False
    db.query(MfaRecoveryCode).filter(MfaRecoveryCode.user_id == user.id).delete()
    db.commit()
    return True


def create_mfa_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "purpose": "mfa",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=MFA_TOKEN_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_mfa_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != "mfa":
        return None
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
