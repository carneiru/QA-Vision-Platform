from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.ingestion.api.deps import ProjectAccess
from src.ingestion.models import ApiKey
from src.ingestion.utils.keys import display_prefix, generate_key, hash_key


def create_key(db: Session, access: ProjectAccess, name: str) -> tuple[ApiKey, str]:
    key = generate_key()
    row = ApiKey(
        project_id=access.project_id,
        organization_id=access.organization_id,
        name=name,
        key_prefix=display_prefix(key),
        key_hash=hash_key(key),
        created_by=access.user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, key


def list_keys(db: Session, project_id: int) -> list[ApiKey]:
    return db.query(ApiKey).filter(ApiKey.project_id == project_id).order_by(ApiKey.id).all()


def revoke_key(db: Session, project_id: int, key_id: int) -> bool:
    """False if the key does not exist in this project. Revoking twice keeps the first time."""
    row = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.project_id == project_id).first()
    if row is None:
        return False
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return True
