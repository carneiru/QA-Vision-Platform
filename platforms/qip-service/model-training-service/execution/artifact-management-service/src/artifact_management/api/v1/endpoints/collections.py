"""
Collections API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.artifact_management.schemas.collection import CollectionCreate, CollectionUpdate, CollectionResponse
from src.artifact_management.service.collection_service import CollectionService

router = APIRouter()


@router.post("/", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    collection: CollectionCreate,
    service: CollectionService = Depends()
):
    """Create a new collection"""
    return await service.create_collection(collection)


@router.get("/", response_model=List[CollectionResponse])
async def list_collections(
    skip: int = 0,
    limit: int = 100,
    service: CollectionService = Depends()
):
    """List collections with pagination"""
    return await service.get_collections(skip=skip, limit=limit)


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    service: CollectionService = Depends()
):
    """Get a specific collection by ID"""
    collection = await service.get_collection(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    collection: CollectionUpdate,
    service: CollectionService = Depends()
):
    """Update a collection"""
    updated_collection = await service.update_collection(collection_id, collection)
    if not updated_collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return updated_collection


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: str,
    service: CollectionService = Depends()
):
    """Delete a collection"""
    deleted = await service.delete_collection(collection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Collection not found")
    return None


@router.get("/type/{collection_type}", response_model=List[CollectionResponse])
async def get_collections_by_type(
    collection_type: str,
    service: CollectionService = Depends()
):
    """Get all collections of a specific type"""
    return await service.get_collections_by_type(collection_type)