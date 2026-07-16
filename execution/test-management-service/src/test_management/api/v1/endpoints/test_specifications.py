"""
Test Specifications API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.test_management.schemas.test_specification import TestSpecificationCreate, TestSpecificationUpdate, TestSpecificationResponse
from src.test_management.service.test_specification_service import TestSpecificationService

router = APIRouter()


@router.post("/", response_model=TestSpecificationResponse, status_code=status.HTTP_201_CREATED)
async def create_test_specification(
    test_spec: TestSpecificationCreate,
    service: TestSpecificationService = Depends()
):
    """Create a new test specification"""
    return await service.create_test_specification(test_spec)


@router.get("/", response_model=List[TestSpecificationResponse])
async def list_test_specifications(
    skip: int = 0,
    limit: int = 100,
    service: TestSpecificationService = Depends()
):
    """List test specifications with pagination"""
    return await service.get_test_specifications(skip=skip, limit=limit)


@router.get("/{test_spec_id}", response_model=TestSpecificationResponse)
async def get_test_specification(
    test_spec_id: str,
    service: TestSpecificationService = Depends()
):
    """Get a specific test specification by ID"""
    test_spec = await service.get_test_specification(test_spec_id)
    if not test_spec:
        raise HTTPException(status_code=404, detail="Test specification not found")
    return test_spec


@router.put("/{test_spec_id}", response_model=TestSpecificationResponse)
async def update_test_specification(
    test_spec_id: str,
    test_spec: TestSpecificationUpdate,
    service: TestSpecificationService = Depends()
):
    """Update a test specification"""
    updated_test_spec = await service.update_test_specification(test_spec_id, test_spec)
    if not updated_test_spec:
        raise HTTPException(status_code=404, detail="Test specification not found")
    return updated_test_spec


@router.delete("/{test_spec_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_specification(
    test_spec_id: str,
    service: TestSpecificationService = Depends()
):
    """Delete a test specification"""
    deleted = await service.delete_test_specification(test_spec_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Test specification not found")
    return None