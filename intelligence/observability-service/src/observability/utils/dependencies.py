# src/services/auth-service/src/auth/utils/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from src.observability-service.db.session import get_db
from src.observability-service.models.user import User
from src.observability-service.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")