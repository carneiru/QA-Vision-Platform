from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

router = APIRouter()


class NotificationType(str, Enum):
    MENTION = "mention"
    COMMENT = "comment"
    DISCUSSION_REPLY = "discussion_reply"
    SYSTEM = "system"
    REMINDER = "reminder"


class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class NotificationBase(BaseModel):
    recipient_id: str
    sender_id: Optional[str] = None
    type: NotificationType
    title: str
    message: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    action_url: Optional[str] = None


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(BaseModel):
    status: Optional[NotificationStatus] = None


class NotificationResponse(NotificationBase):
    id: str
    status: NotificationStatus
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    success: bool
    data: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    size: int
    message: str


@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    recipient_id: str,
    status: Optional[NotificationStatus] = None,
    notification_type: Optional[NotificationType] = None,
    include_read: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get notifications for a user with optional filtering
    """
    # TODO: Implement actual database query
    notifications = []
    unread_count = 0  # TODO: Calculate actual unread count
    
    return NotificationListResponse(
        success=True,
        data=notifications,
        total=len(notifications),
        unread_count=unread_count,
        page=skip // limit + 1 if limit > 0 else 1,
        size=len(notifications),
        message="Notifications retrieved successfully"
    )


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(notification: NotificationCreate):
    """
    Create a new notification
    """
    # TODO: Implement actual notification creation
    from uuid import uuid4
    from datetime import datetime
    
    notification_response = NotificationResponse(
        id=str(uuid4()),
        recipient_id=notification.recipient_id,
        sender_id=notification.sender_id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        related_entity_type=notification.related_entity_type,
        related_entity_id=notification.related_entity_id,
        action_url=notification.action_url,
        status=NotificationStatus.UNREAD,
        is_read=False,
        created_at=datetime.utcnow()
    )
    
    return notification_response


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(notification_id: str):
    """
    Get a specific notification by ID
    """
    # TODO: Implement actual database lookup
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Notification with ID {notification_id} not found"
    )


@router.put("/{notification_id}", response_model=NotificationResponse)
async def update_notification(notification_id: str, notification_update: NotificationUpdate):
    """
    Update an existing notification
    """
    # TODO: Implement actual notification update
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Notification with ID {notification_id} not found"
    )


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(notification_id: str):
    """
    Delete a notification
    """
    # TODO: Implement actual notification deletion
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Notification with ID {notification_id} not found"
    )


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(notification_id: str):
    """
    Mark a notification as read
    """
    # TODO: Implement marking notification as read
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Notification with ID {notification_id} not found"
    )


@router.patch("/{notification_id}/unread", response_model=NotificationResponse)
async def mark_notification_as_unread(notification_id: str):
    """
    Mark a notification as unread
    """
    # TODO: Implement marking notification as unread
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Notification with ID {notification_id} not found"
    )


@router.post("/mark-all-read", status_code=status.HTTP_200_OK)
async def mark_all_notifications_as_read(recipient_id: str):
    """
    Mark all notifications for a user as read
    """
    # TODO: Implement marking all notifications as read
    return {"message": f"All notifications for user {recipient_id} marked as read"}


@router.get("/unread-count/{recipient_id}")
async def get_unread_notification_count(recipient_id: str):
    """
    Get the count of unread notifications for a user
    """
    # TODO: Implement actual unread count calculation
    return {"recipient_id": recipient_id, "unread_count": 0}


__all__ = ["router"]
