# ============================================
# TIME TRACKER - EMAIL LOGS ROUTER
# ============================================
# API endpoints for viewing email delivery logs and statistics.
# Admin only access for monitoring email delivery status.
# ============================================

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_admin_user
from app.models import User, EmailLog
from app.schemas.email_log import (
    EmailLogResponse,
    EmailLogSummary,
    PaginatedEmailLogs,
    EmailStatusEnum
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/email-logs", tags=["Email Logs"])


@router.get("/summary", response_model=EmailLogSummary)
async def get_email_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to include in summary"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get summary statistics of email delivery.
    Shows totals and success rate for the specified period.
    Admin only.
    """
    from datetime import timedelta
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Build base query with company filter for non-super admins
    base_filter = EmailLog.created_at >= start_date
    if current_user.role != "super_admin" and current_user.company_id:
        base_filter = and_(base_filter, EmailLog.company_id == current_user.company_id)
    
    # Get counts by status
    result = await db.execute(
        select(
            EmailLog.status,
            func.count(EmailLog.id).label("count")
        )
        .where(base_filter)
        .group_by(EmailLog.status)
    )
    
    status_counts = {row.status: row.count for row in result.fetchall()}
    
    total = sum(status_counts.values())
    sent = status_counts.get("sent", 0)
    delivered = status_counts.get("delivered", 0)
    failed = status_counts.get("failed", 0)
    pending = status_counts.get("pending", 0)
    bounced = status_counts.get("bounced", 0)
    
    # Calculate success rate (sent + delivered / total non-pending)
    completed = sent + delivered + failed + bounced
    success_rate = ((sent + delivered) / completed * 100) if completed > 0 else 100.0
    
    return EmailLogSummary(
        total_emails=total,
        sent_count=sent,
        delivered_count=delivered,
        failed_count=failed,
        pending_count=pending,
        bounced_count=bounced,
        success_rate=round(success_rate, 2)
    )


@router.get("", response_model=PaginatedEmailLogs)
async def list_email_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    email_type: Optional[str] = Query(None),
    to_email: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    List email logs with filtering and pagination.
    Admin only.
    """
    # Build base query
    query = select(EmailLog)
    count_query = select(func.count(EmailLog.id))
    
    # Company filter for non-super admins
    if current_user.role != "super_admin" and current_user.company_id:
        query = query.where(EmailLog.company_id == current_user.company_id)
        count_query = count_query.where(EmailLog.company_id == current_user.company_id)
    
    # Apply filters
    if status_filter:
        query = query.where(EmailLog.status == status_filter)
        count_query = count_query.where(EmailLog.status == status_filter)
    
    if email_type:
        query = query.where(EmailLog.email_type == email_type)
        count_query = count_query.where(EmailLog.email_type == email_type)
    
    if to_email:
        query = query.where(EmailLog.to_email.ilike(f"%{to_email}%"))
        count_query = count_query.where(EmailLog.to_email.ilike(f"%{to_email}%"))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination and ordering
    offset = (page - 1) * page_size
    query = query.order_by(EmailLog.created_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    total_pages = (total + page_size - 1) // page_size
    
    return PaginatedEmailLogs(
        items=[EmailLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/types")
async def get_email_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get list of distinct email types in the logs.
    Useful for filtering.
    """
    query = select(EmailLog.email_type).distinct()
    
    if current_user.role != "super_admin" and current_user.company_id:
        query = query.where(EmailLog.company_id == current_user.company_id)
    
    result = await db.execute(query)
    types = [row[0] for row in result.fetchall()]
    
    return {"email_types": types}


@router.get("/{log_id}", response_model=EmailLogResponse)
async def get_email_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get a specific email log entry.
    Admin only.
    """
    query = select(EmailLog).where(EmailLog.id == log_id)
    
    if current_user.role != "super_admin" and current_user.company_id:
        query = query.where(EmailLog.company_id == current_user.company_id)
    
    result = await db.execute(query)
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email log not found"
        )
    
    return log
