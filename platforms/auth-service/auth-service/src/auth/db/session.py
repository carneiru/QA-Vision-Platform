# src/services/auth-service/src/auth/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# This was a hardcoded placeholder that ignored settings entirely, so the service always
# pointed at postgres://...@db/auth_db regardless of configuration -- and it is what the
# test suite silently connected to while its get_db override was being shadowed.
from src.auth.config import settings

SQLALCHEMY_DATABASE_URL = str(settings.database_url)  # PostgresDsn -> str for create_engine

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
