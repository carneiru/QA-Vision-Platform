from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.ingestion.api.deps import EDIT_ROLES, READ_ROLES, ProjectAccess, get_db, require_project_role
from src.ingestion.models.notification_channel import NotificationChannel
from src.ingestion.schemas.notification import ChannelCreate, ChannelOut, ChannelUpdate, TestOutcome
from src.ingestion.service import notification_service
from src.ingestion.utils.notify_targets import mask_target

router = APIRouter()  # mounted at /projects/{project_id}/notification-channels


def _out(row: NotificationChannel) -> ChannelOut:
    return ChannelOut(
        id=row.id, name=row.name, kind=row.kind, target=mask_target(row.url, row.kind), branch=row.branch,
        enabled=row.enabled, last_status=row.last_status, last_error=row.last_error, last_sent_at=row.last_sent_at,
    )


def _channel_or_404(db: Session, access: ProjectAccess, channel_id: int) -> NotificationChannel:
    row = notification_service.get_channel(db, access.project_id, channel_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification channel not found")
    return row


@router.get("", response_model=list[ChannelOut])
def list_notification_channels(
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    return [_out(row) for row in notification_service.list_channels(db, access.project_id)]


@router.post("", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
def add_notification_channel(
    payload: ChannelCreate,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    try:
        row = notification_service.add_channel(
            db, access.project_id, payload.name, payload.kind, payload.url, payload.branch, access.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _out(row)


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_notification_channel(
    channel_id: int,
    payload: ChannelUpdate,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    row = _channel_or_404(db, access, channel_id)
    return _out(notification_service.update_channel(db, row, payload.model_dump(exclude_unset=True)))


@router.post("/{channel_id}/test", response_model=TestOutcome)
def send_test_notification(
    channel_id: int,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    status_, error = notification_service.send_test(db, _channel_or_404(db, access, channel_id))
    return TestOutcome(status=status_, error=error)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    notification_service.delete_channel(db, _channel_or_404(db, access, channel_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
