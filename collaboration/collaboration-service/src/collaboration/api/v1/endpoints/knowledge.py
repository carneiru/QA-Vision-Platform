from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

router = APIRouter()


class ArticleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class KnowledgeBase(BaseModel):
    title: str
    content: str
    summary: Optional[str] = None
    author_id: str
    category: str
    tags: List[str] = []
    is_public: bool = True


class KnowledgeBaseCreate(KnowledgeBase):
    pass


class KnowledgeBaseUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    status: Optional[ArticleStatus] = None


class KnowledgeBaseResponse(KnowledgeBase):
    id: str
    status: ArticleStatus
    view_count: int = 0
    rating_average: float = 0.0
    rating_count: int = 0
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class KnowledgeBaseListResponse(BaseModel):
    success: bool
    data: List[KnowledgeBaseResponse]
    total: int
    page: int
    size: int
    message: str


@router.get("/", response_model=KnowledgeBaseListResponse)
async def get_knowledge_base(
    category: Optional[str] = None,
    author_id: Optional[str] = None,
    status: Optional[ArticleStatus] = None,
    tags: Optional[List[str]] = Query(None),
    is_public: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Get knowledge base articles with optional filtering and search
    """
    # TODO: Implement actual database query with filtering and search
    articles = []
    
    return KnowledgeBaseListResponse(
        success=True,
        data=articles,
        total=0,
        page=skip // limit + 1 if limit > 0 else 1,
        size=len(articles),
        message="Knowledge base articles retrieved successfully"
    )


@router.post("/", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_article(article: KnowledgeBaseCreate):
    """
    Create a new knowledge base article
    """
    # TODO: Implement actual article creation
    from uuid import uuid4
    from datetime import datetime
    
    article_response = KnowledgeBaseResponse(
        id=str(uuid4()),
        title=article.title,
        content=article.content,
        summary=article.summary,
        author_id=article.author_id,
        category=article.category,
        tags=article.tags,
        is_public=article.is_public,
        status=ArticleStatus.DRAFT,
        view_count=0,
        rating_average=0.0,
        rating_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    return article_response


@router.get("/{article_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_article(article_id: str):
    """
    Get a specific knowledge base article by ID
    """
    # TODO: Implement actual database lookup
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Knowledge base article with ID {article_id} not found"
    )


@router.put("/{article_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_article(article_id: str, article_update: KnowledgeBaseUpdate):
    """
    Update an existing knowledge base article
    """
    # TODO: Implement actual article update
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Knowledge base article with ID {article_id} not found"
    )


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_article(article_id: str):
    """
    Delete a knowledge base article
    """
    # TODO: Implement actual article deletion
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Knowledge base article with ID {article_id} not found"
    )


@router.post("/{article_id}/publish")
async def publish_knowledge_article(article_id: str):
    """
    Publish a knowledge base article
    """
    # TODO: Implement article publishing
    return {"message": f"Knowledge base article {article_id} published"}


@router.post("/{article_id}/archive")
async def archive_knowledge_article(article_id: str):
    """
    Archive a knowledge base article
    """
    # TODO: Implement article archiving
    return {"message": f"Knowledge base article {article_id} archived"}


@router.post("/{article_id}/rate")
async def rate_knowledge_article(article_id: str, rating: int):
    """
    Rate a knowledge base article (1-5)
    """
    # TODO: Implement article rating
    if rating < 1 or rating > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be between 1 and 5"
        )
    return {"message": f"Knowledge base article {article_id} rated {rating}/5"}


__all__ = ["router"]
