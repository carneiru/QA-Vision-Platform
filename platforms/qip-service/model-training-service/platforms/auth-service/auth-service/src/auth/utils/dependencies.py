# src/services/auth-service/src/auth/utils/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from src.auth.db.session import get_db
from src.auth.models.user import User
from src.auth.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")