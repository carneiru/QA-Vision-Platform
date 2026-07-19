"""
Test Results API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.test_execution.schemas.test_result import TestResultCreate, TestResultUpdate, TestResultResponse
from src.test_execution.service.test_result_service import TestResultService

router = APIRouter()


@router.post("/", response_model=TestResultResponse, status_code=status.HTTP_201_CREATED)
async def create_test_result(
    test_result: TestResultCreate,
    service: TestResultService = Depends()
):
    """Create a new test result"""
    return await service.create_test_result(test_result)


@router.get("/", response_model=List[TestResultResponse])
async def list_test_results(
    skip: int = 0,
    limit: int = 100,
    service: TestResultService = Depends()
):
    """List test results with pagination"""
    return await service.get_test_results(skip=skip, limit=limit)


@router.get("/{test_result_id}", response_model=TestResultResponse)
async def get_test_result(
    test_result_id: str,
    service: TestResultService = Depends()
):
    """Get a specific test result by ID"""
    test_result = await service.get_test_result(test_result_id)
    if not test_result:
        raise HTTPException(status_code=404, detail="Test result not found")
    return test_result


@router.put("/{test_result_id}", response_model=TestResultResponse)
async def update_test_result(
    test_result_id: str,
    test_result: TestResultUpdate,
    service: TestResultService = Depends()
):
    """Update a test result"""
    updated_test_result = await service.update_test_result(test_result_id, test_result)
    if not updated_test_result:
        raise HTTPException(status_code=404, detail="Test result not found")
    return updated_test_result


@router.delete("/{test_result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_result(
    test_result_id: str,
    service: TestResultService = Depends()
):
    """Delete a test result"""
    deleted = await service.delete_test_result(test_result_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Test result not found")
    return None


@router.get("/run/{test_run_id}", response_model=List[TestResultResponse])
async def get_test_results_by_run(
    test_run_id: str,
    service: TestResultService = Depends()
):
    """Get all test results for a specific test run"""
    return await service.get_test_results_by_run(test_run_id)