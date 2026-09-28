from qav_shared.db import make_get_db, make_session_factory

from src.project.core.config import settings

SessionLocal = make_session_factory(settings.database_url)
get_db = make_get_db(SessionLocal)
