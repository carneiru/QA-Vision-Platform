"""
Database connection and session management
"""


from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker

from .config import get_settings


# Global engine variable
_engine: AsyncEngine = None
_async_session_maker = None


def get_database_url() -> str:
    """Get database URL from settings."""
    settings = get_settings()
    return str(settings.DATABASE_URL)


def create_db_engine() -> AsyncEngine:
    """Create database engine."""
    global _engine
    if _engine is None:
        database_url = get_database_url()
        # Convert postgresql:// to postgresql+asyncpg:// for async
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        _engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_async_session_maker():
    """Get or create async session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_database_engine()
        _async_session_maker = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_maker


def get_database_engine() -> AsyncEngine:
    """Get database engine instance."""
    return create_db_engine()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get async database session."""
    async_session_maker = get_async_session_maker()
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Alias for backward compatibility
get_db = get_async_session