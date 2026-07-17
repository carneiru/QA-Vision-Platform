from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

router = APIRouter()


class MentionType(str, Enum):
    COMMENT = "comment"
    DISCUSSION = "discussion"
    DOCUMENT = "document"
    TASK = "task"


class MentionBase(BaseModel):
    mentioned_user_id: str
    mentioned_by_user_id: str
    entity_type: MentionType
    entity_id: str
    content_excerpt: str
    context: Optional[str] = None


class MentionCreate(MentionBase):
    pass


class MentionResponse(MentionBase):
    id: str
    is_read: bool = False
    created_at: datetime


class MentionListResponse(BaseModel):
    success: bool
    data: List[MentionResponse]
    total: int
    unread_count: int
    page: int
    size: int
    message: str


@router.get("/", response_model=MentionListResponse)
async def get_mentions(
    user_id: str,
    entity_type: Optional[MentionType] = None,
    is_read: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get mentions for a user with optional filtering
    """
    # TODO: Implement actual database query
    mentions = []
    unread_count = 0  # TODO: Calculate actual unread count
    
    return MentionListResponse(
        success=True,
        data=mentions,
        total=len(mentions),
        unread_count=unread_count,
        page=skip // limit + 1 if limit > 0 else 1,
        size=len(mentions),
        message="Mentions retrieved successfully"
    )


@router.post("/", response_model=MentionResponse, status_code=status.HTTP_201_CREATED)
async def create_mention(mention: MentionCreate):
    """
    Create a new mention
    """
    # TODO: Implement actual mention creation
    from uuid import uuid4
    from datetime import datetime
    
    mention_response = MentionResponse(
        id=str(uuid4()),
        mentioned_user_id=mention.mentioned_user_id,
        mentioned_by_user_id=mention.mentioned_by_user_id,
        entity_type=mention.entity_type,
        entity_id=mention.entity_id,
        content_excerpt=mention.content_excerpt,
        context=mention.context,
        created_at=datetime.utcnow()
    )
    
    return mention_response


@router.get("/{mention_id}", response_model=MentionResponse)
async def get_mention(mention_id: str):
    """
    Get a specific mention by ID
    """
    # TODO: Implement actual database lookup
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Mention with ID {mention_id} not found"
    )


@router.put("/{mention_id}/read")
async def mark_mention_as_read(mention_id: str):
    """
    Mark a mention as read
    """
    # TODO: Implement marking mention as read
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Mention with ID {mention_id} not found"
    )


@router.get("/unread-count/{user_id}")
async def get_unread_mention_count(user_id: str):
    """
    Get the count of unread mentions for a user
    """
    # TODO: Implement actual unread count calculation
    return {"user_id": user_id, "unread_count": 0}


__all__ = ["router"]
