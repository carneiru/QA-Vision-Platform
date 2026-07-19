# src/services/auth-service/src/auth/utils/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from src.user.db.session import get_db
from src.user.models.user import User
from src.user.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")