# src/services/auth-service/src/auth/utils/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from src.integration-service.db.session import get_db
from src.integration-service.models.user import User
from src.integration-service.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")