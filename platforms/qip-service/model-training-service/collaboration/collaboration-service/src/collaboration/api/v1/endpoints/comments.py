from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

router = APIRouter()


class CommentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SPAM = "spam"


class CommentBase(BaseModel):
    content: str
    author_id: str
    parent_id: Optional[str] = None
    entity_type: str  # e.g., "plugin", "report", "discussion"
    entity_id: str


class CommentCreate(CommentBase):
    pass


class CommentUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[CommentStatus] = None


class CommentResponse(CommentBase):
    id: str
    status: CommentStatus
    created_at: datetime
    updated_at: datetime
    is_edited: bool = False
    reply_count: int = 0


class CommentListResponse(BaseModel):
    success: bool
    data: List[CommentResponse]
    total: int
    page: int
    size: int
    message: str


@router.get("/", response_model=CommentListResponse)
async def get_comments(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    author_id: Optional[str] = None,
    status: Optional[CommentStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Get comments with optional filtering
    """
    # TODO: Implement actual database query with filtering
    comments = []
    
    return CommentListResponse(
        success=True,
        data=comments,
        total=0,
        page=skip // limit + 1 if limit > 0 else 1,
        size=len(comments),
        message="Comments retrieved successfully"
    )


@router.post("/", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(comment: CommentCreate):
    """
    Create a new comment
    """
    # TODO: Implement actual comment creation
    from uuid import uuid4
    from datetime import datetime
    
    comment_response = CommentResponse(
        id=str(uuid4()),
        content=comment.content,
        author_id=comment.author_id,
        parent_id=comment.parent_id,
        entity_type=comment.entity_type,
        entity_id=comment.entity_id,
        status=CommentStatus.PENDING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    return comment_response


@router.get("/{comment_id}", response_model=CommentResponse)
async def get_comment(comment_id: str):
    """
    Get a specific comment by ID
    """
    # TODO: Implement actual database lookup
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Comment with ID {comment_id} not found"
    )


@router.put("/{comment_id}", response_model=CommentResponse)
async def update_comment(comment_id: str, comment_update: CommentUpdate):
    """
    Update an existing comment
    """
    # TODO: Implement actual comment update
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Comment with ID {comment_id} not found"
    )


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: str):
    """
    Delete a comment
    """
    # TODO: Implement actual comment deletion
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Comment with ID {comment_id} not found"
    )


@router.post("/{comment_id}/approve")
async def approve_comment(comment_id: str):
    """
    Approve a comment
    """
    # TODO: Implement comment approval
    return {"message": f"Comment {comment_id} approved"}


@router.post("/{comment_id}/reject")
async def reject_comment(comment_id: str):
    """
    Reject a comment
    """
    # TODO: Implement comment rejection
    return {"message": f"Comment {comment_id} rejected"}


__all__ = ["router"]
