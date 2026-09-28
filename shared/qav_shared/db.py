"""Database session wiring shared by every QA Vision Platform service.

Note what is NOT here: the declarative Base. A declarative base is a mutable global
registry of mapped classes, so one shared instance would put separate services'
databases into a single Base.metadata -- and a create_all() in one service's test suite
would start creating another service's tables. Each service keeps its own three-line
db/base.py.
"""
from typing import Callable, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_session_factory(database_url: str) -> sessionmaker:
    """Build the engine and session factory for one service's database.

    create_engine does not open a connection; the first connect happens on first use.
    That laziness is load-bearing: both services' conftest.py import their db.session
    module (to get get_db) while settings still point at a Postgres URL that does not
    exist in the test environment.
    """
    engine = create_engine(database_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_get_db(
    session_factory: sessionmaker,
) -> Callable[[], Generator[Session, None, None]]:
    """Build the FastAPI dependency that yields a session and always closes it."""

    def get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    return get_db
