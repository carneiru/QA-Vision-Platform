import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from qav_shared.db import make_get_db, make_session_factory

SQLITE_URL = "sqlite://"  # in-memory, no file, no cleanup


def test_make_session_factory_produces_usable_sessions():
    factory = make_session_factory(SQLITE_URL)
    session = factory()
    try:
        assert isinstance(session, Session)
    finally:
        session.close()


def test_make_session_factory_does_not_connect_eagerly():
    """Both services' conftest.py import their db.session module while settings point at a
    Postgres URL that does not exist in the test environment. That only works because
    create_engine is lazy -- nothing may connect until first use."""
    factory = make_session_factory("postgresql://nobody:nothing@127.0.0.1:1/nowhere")
    assert factory is not None


def test_get_db_yields_a_session_and_closes_it():
    factory = make_session_factory(SQLITE_URL)
    get_db = make_get_db(factory)

    generator = get_db()
    session = next(generator)
    session.execute(text("SELECT 1"))
    assert session.in_transaction()
    assert isinstance(session, Session)
    assert session.is_active

    with pytest.raises(StopIteration):
        next(generator)
    # after the generator finishes, the finally block has closed the session
    assert not session.in_transaction()


def test_get_db_closes_the_session_when_the_consumer_raises():
    factory = make_session_factory(SQLITE_URL)
    get_db = make_get_db(factory)

    generator = get_db()
    session = next(generator)
    session.execute(text("SELECT 1"))
    assert session.in_transaction()

    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("consumer blew up"))

    assert not session.in_transaction()
