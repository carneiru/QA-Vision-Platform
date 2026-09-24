from datetime import datetime, timedelta, timezone

from src.auth.models.pending_registration import PendingRegistration


def test_pending_registration_round_trips_through_the_orm(db):
    row = PendingRegistration(
        email="person@example.com",
        hashed_password="not-a-real-hash",
        full_name="A Person",
        token="test-token-value",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    fetched = db.query(PendingRegistration).filter(
        PendingRegistration.email == "person@example.com"
    ).first()
    assert fetched is not None
    assert fetched.token == "test-token-value"
    assert fetched.full_name == "A Person"
