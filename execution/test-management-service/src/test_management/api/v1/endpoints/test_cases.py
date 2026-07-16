"""
Test Cases API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.test_management.schemas.test_case import TestCaseCreate, TestCaseUpdate, TestCaseResponse
from src.test_management.service.test_case_service import TestCaseService

router = APIRouter()


@router.post("/", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_test_case(
    test_case: TestCaseCreate,
    service: TestCaseService = Depends()
):
    """Create a new test case"""
    return await service.create_test_case(test_case)


@router.get("/", response_model=List[TestCaseResponse])
async def list_test_cases(
    skip: int = 0,
    limit: int = 100,
    service: TestCaseService = Depends()
):
    """List test cases with pagination"""
    return await service.get_test_cases(skip=skip, limit=limit)


@router.get("/{test_case_id}", response_model=TestCaseResponse)
async def get_test_case(
    test_case_id: str,
    service: TestCaseService = Depends()
):
    """Get a specific test case by ID"""
    test_case = await service.get_test_case(test_case_id)
    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")
    return test_case


@router.put("/{test_case_id}", response_model=TestCaseResponse)
async def update_test_case(
    test_case_id: str,
    test_case: TestCaseUpdate,
    service: TestCaseService = Depends()
):
    """Update a test case"""
    updated_test_case = await service.update_test_case(test_case_id, test_case)
    if not updated_test_case:
        raise HTTPException(status_code=404, detail="Test case not found")
    return updated_test_case


@router.delete("/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_case(
    test_case_id: str,
    service: TestCaseService = Depends()
):
    """Delete a test case"""
    deleted = await service.delete_test_case(test_case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Test case not found")
    return None