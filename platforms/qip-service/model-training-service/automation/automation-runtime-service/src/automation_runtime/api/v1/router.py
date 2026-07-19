"""
Automation Runtime API Router
"""
from fastapi import APIRouter
from src.automation_runtime.api.v1.endpoints import executions, triggers, schedules

api_router = APIRouter()
api_router.include_router(executions.router, prefix="/executions", tags=["executions"])
api_router.include_router(triggers.router, prefix="/triggers", tags=["triggers"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
