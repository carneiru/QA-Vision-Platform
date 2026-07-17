from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_plugins: int
    active_plugins: int
    total_reports: int
    recent_activity_count: int
    timestamp: datetime


class DashboardResponse(BaseModel):
    success: bool
    data: DashboardStats
    message: str


@router.get("/stats", response_model=DashboardResponse)
async def get_dashboard_stats():
    """
    Get dashboard statistics
    """
    # TODO: Implement actual logic to gather statistics from various services
    stats = DashboardStats(
        total_users=150,
        active_users=125,
        total_plugins=42,
        active_plugins=38,
        total_reports=128,
        recent_activity_count=45,
        timestamp=datetime.utcnow()
    )
    
    return DashboardResponse(
        success=True,
        data=stats,
        message="Dashboard statistics retrieved successfully"
    )


@router.get("/widgets")
async def get_dashboard_widgets():
    """
    Get dashboard widgets configuration
    """
    # TODO: Implement actual widget configuration retrieval
    widgets = [
        {
            "id": "user_stats",
            "type": "statistic",
            "title": "User Statistics",
            "data": {"total": 150, "active": 125}
        },
        {
            "id": "plugin_stats",
            "type": "statistic",
            "title": "Plugin Statistics",
            "data": {"total": 42, "active": 38}
        },
        {
            "id": "activity_feed",
            "type": "activity_feed",
            "title": "Recent Activity",
            "data": []
        }
    ]
    
    return {"widgets": widgets}


__all__ = ["router"]
