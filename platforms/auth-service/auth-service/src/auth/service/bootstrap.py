"""One-time superuser bootstrap.

Nothing in this service could ever grant is_superuser through the API: update_user's
allow_privileged=True guard has zero callers, and there never was one. A fresh deployment
had no way to reach GET /users/ at all.

bootstrap_first_superuser runs at startup and closes that, using FIRST_SUPERUSER /
FIRST_SUPERUSER_PASSWORD -- settings that already existed in config.py, marked "nothing
reads these today."

Two rules keep this from becoming its own privilege-escalation path:

- It acts only once, ever: if any superuser already exists in the database, it is a no-op
  regardless of what the environment says. A later redeploy carrying the same env vars
  cannot mint a second superuser.
- It never promotes an account it did not create. FIRST_SUPERUSER's email is an operator
  choice, not a secret -- an env var, readable by anyone who can read the deployment config.
  If someone registered that address before bootstrap ran, silently promoting that row would
  let them choose their own superuser email ahead of the operator. Refusing and logging is
  the same shape as the account-linking guards in sso.py: an existing row's provenance is
  unknown, so it is not touched.
"""
import logging

from sqlalchemy.orm import Session

from src.auth.config import settings
from src.auth.models.user import User
from src.auth.utils.password import get_password_hash

logger = logging.getLogger(__name__)


def bootstrap_first_superuser(db: Session) -> None:
    if not settings.FIRST_SUPERUSER or not settings.FIRST_SUPERUSER_PASSWORD:
        return

    if db.query(User).filter(User.is_superuser == True).first() is not None:  # noqa: E712
        return

    existing = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
    if existing is not None:
        logger.warning(
            "FIRST_SUPERUSER bootstrap skipped: a user with email %s already exists and "
            "was not created by this bootstrap. Promote it manually if that is intended -- "
            "it is not done automatically, since the email is not a secret and anyone who "
            "read it could have registered that address first.",
            settings.FIRST_SUPERUSER,
        )
        return

    user = User(
        email=settings.FIRST_SUPERUSER,
        hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
        full_name="First Superuser",
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    logger.info("Bootstrapped first superuser %s", settings.FIRST_SUPERUSER)
