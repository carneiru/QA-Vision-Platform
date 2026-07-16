"""
Test Suites API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.test_management.schemas.test_suite import TestSuiteCreate, TestSuiteUpdate, TestSuiteResponse
from src.test_management.service.test_suite_service import TestSuiteService

router = APIRouter()


@router.post("/", response_model=TestSuiteResponse, status_code=status.HTTP_201_CREATED)
async def create_test_suite(
    test_suite: TestSuiteCreate,
    service: TestSuiteService = Depends()
):
    """Create a new test suite"""
    return await service.create_test_suite(test_suite)


@router.get("/", response_model=List[TestSuiteResponse])
async def list_test_suites(
    skip: int = 0,
    limit: int = 100,
    service: TestSuiteService = Depends()
):
    """List test suites with pagination"""
    return await service.get_test_suites(skip=skip, limit=limit)


@router.get("/{test_suite_id}", response_model=TestSuiteResponse)
async def get_test_suite(
    test_suite_id: str,
    service: TestSuiteService = Depends()
):
    """Get a specific test suite by ID"""
    test_suite = await service.get_test_suite(test_suite_id)
    if not test_suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    return test_suite


@router.put("/{test_suite_id}", response_model=TestSuiteResponse)
async def update_test_suite(
    test_suite_id: str,
    test_suite: TestSuiteUpdate,
    service: TestSuiteService = Depends()
):
    """Update a test suite"""
    updated_test_suite = await service.update_test_suite(test_suite_id, test_suite)
    if not updated_test_suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    return updated_test_suite


@router.delete("/{test_suite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_suite(
    test_suite_id: str,
    service: TestSuiteService = Depends()
):
    """Delete a test suite"""
    deleted = await service.delete_test_suite(test_suite_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Test suite not found")
    return None