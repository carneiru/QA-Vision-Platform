from qeos_shared.db import make_get_db, make_session_factory

from src.auth.config import settings

# This module previously hardcoded a postgres:// URL that ignored settings entirely, and
# later carried its own engine/sessionmaker/get_db boilerplate. Both now come from the
# shared package; settings.database_url is already a str, so the old str() wrapper and the
# SQLALCHEMY_DATABASE_URL constant it fed are gone (nothing imported that name).
SessionLocal = make_session_factory(settings.database_url)
get_db = make_get_db(SessionLocal)
