"""
Test Runs API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.test_execution.schemas.test_run import TestRunCreate, TestRunUpdate, TestRunResponse
from src.test_execution.service.test_run_service import TestRunService

router = APIRouter()


@router.post("/", response_model=TestRunResponse, status_code=status.HTTP_201_CREATED)
async def create_test_run(
    test_run: TestRunCreate,
    service: TestRunService = Depends()
):
    """Create a new test run"""
    return await service.create_test_run(test_run)


@router.get("/", response_model=List[TestRunResponse])
async def list_test_runs(
    skip: int = 0,
    limit: int = 100,
    service: TestRunService = Depends()
):
    """List test runs with pagination"""
    return await service.get_test_runs(skip=skip, limit=limit)


@router.get("/{test_run_id}", response_model=TestRunResponse)
async def get_test_run(
    test_run_id: str,
    service: TestRunService = Depends()
):
    """Get a specific test run by ID"""
    test_run = await service.get_test_run(test_run_id)
    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return test_run


@router.put("/{test_run_id}", response_model=TestRunResponse)
async def update_test_run(
    test_run_id: str,
    test_run: TestRunUpdate,
    service: TestRunService = Depends()
):
    """Update a test run"""
    updated_test_run = await service.update_test_run(test_run_id, test_run)
    if not updated_test_run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return updated_test_run


@router.delete("/{test_run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_run(
    test_run_id: str,
    service: TestRunService = Depends()
):
    """Delete a test run"""
    deleted = await service.delete_test_run(test_run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Test run not found")
    return None


@router.post("/{test_run_id}/execute", response_model=TestRunResponse)
async def execute_test_run(
    test_run_id: str,
    service: TestRunService = Depends()
):
    """Execute a test run"""
    executed_test_run = await service.execute_test_run(test_run_id)
    if not executed_test_run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return executed_test_run


@router.get("/{test_run_id}/results", response_model=List[dict])
async def get_test_run_results(
    test_run_id: str,
    service: TestRunService = Depends()
):
    """Get all results for a test run"""
    return await service.get_test_run_results(test_run_id)