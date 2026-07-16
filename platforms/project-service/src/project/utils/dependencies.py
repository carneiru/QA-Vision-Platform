# src/services/auth-service/src/auth/utils/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from src.project.db.session import get_db
from src.project.models.user import User
from src.project.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")