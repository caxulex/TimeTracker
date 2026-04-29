# ============================================
# TIME TRACKER - AUDIT LOGS ROUTER
# ============================================
# API endpoints for viewing audit logs.
# Admin only access for security monitoring.
# ============================================

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.dependencies import get_current_admin_user
from app.models import User
from app.services.audit_log import AuditEventType, audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/audit-logs", tags=["Audit Logs"])


# ============================================
# RESPONSE SCHEMAS
# ============================================

class AuditLogEntry(BaseModel):
    """Schema for a single audit log entry"""
    id: str
    timestamp: str
    event_type: str
    severity: str
    success: bool
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    details: Optional[dict] = None


class AuditLogListResponse(BaseModel):
    """Schema for audit log list response"""
    items: List[AuditLogEntry]
    total: int


class AuditLogSummary(BaseModel):
    """Schema for audit log summary"""
    total_events: int
    login_success: int
    login_failed: int
    user_events: int
    admin_actions: int
    security_events: int
    time_range_hours: int


# ============================================
# API ENDPOINTS
# ============================================

@router.get("", response_model=AuditLogListResponse)
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of logs to return"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get recent audit logs.
    Optionally filter by event type.
    Admin only.
    """
    try:
        # Convert event_type string to enum if provided
        filter_type = None
        if event_type:
            try:
                filter_type = AuditEventType(event_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid event type: {event_type}"
                )

        logs = await audit_log.get_recent_logs(event_type=filter_type, limit=limit)

        return AuditLogListResponse(
            items=[AuditLogEntry(**log) for log in logs],
            total=len(logs)
        )
    except Exception as e:
        logger.error(f"Failed to get audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs"
        )


@router.get("/user/{user_id}", response_model=AuditLogListResponse)
async def get_user_audit_logs(
    user_id: int,
    limit: int = Query(100, ge=1, le=500, description="Maximum number of logs to return"),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get audit logs for a specific user.
    Admin only.
    """
    try:
        logs = await audit_log.get_user_logs(user_id=user_id, limit=limit)

        return AuditLogListResponse(
            items=[AuditLogEntry(**log) for log in logs],
            total=len(logs)
        )
    except Exception as e:
        logger.error(f"Failed to get user audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs"
        )


@router.get("/summary", response_model=AuditLogSummary)
async def get_audit_summary(
    hours: int = Query(24, ge=1, le=168, description="Number of hours to include in summary"),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get summary statistics of audit events.
    Admin only.
    """
    try:
        # Get logs for time period
        all_logs = await audit_log.get_recent_logs(limit=1000)

        # Filter by time range
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_logs = [
            log for log in all_logs
            if datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00')) >= cutoff_time
        ]

        # Calculate statistics
        login_success = sum(1 for log in recent_logs if log['event_type'] == AuditEventType.LOGIN_SUCCESS.value)
        login_failed = sum(1 for log in recent_logs if log['event_type'] == AuditEventType.LOGIN_FAILED.value)
        user_events = sum(1 for log in recent_logs if log['event_type'].startswith('user.'))
        admin_actions = sum(1 for log in recent_logs if log['event_type'].startswith('admin.'))
        security_events = sum(1 for log in recent_logs if log['event_type'].startswith('security.'))

        return AuditLogSummary(
            total_events=len(recent_logs),
            login_success=login_success,
            login_failed=login_failed,
            user_events=user_events,
            admin_actions=admin_actions,
            security_events=security_events,
            time_range_hours=hours
        )
    except Exception as e:
        logger.error(f"Failed to get audit summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit summary"
        )


@router.get("/event-types")
async def get_event_types(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get list of available audit event types.
    Admin only.
    """
    return {
        "event_types": [
            {"value": e.value, "name": e.name}
            for e in AuditEventType
        ]
    }
