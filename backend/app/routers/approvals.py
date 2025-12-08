"""
Time Entry Approval Router - TASK-028
Handles time entry approval workflow
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from enum import Enum

from app.database import get_db
from app.models import User
from app.models import TimeEntry
from app.dependencies import get_current_user, require_role

router = APIRouter()


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalUpdate(BaseModel):
    status: ApprovalStatus
    rejection_reason: Optional[str] = None


class BulkApprovalRequest(BaseModel):
    entry_ids: List[int]
    status: ApprovalStatus
    rejection_reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: int
    status: str
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    
    class Config:
        from_attributes = True


@router.get("/pending", response_model=List[dict])
async def get_pending_approvals(
    user_id: Optional[int] = Query(None, description="Filter by user"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Get all pending time entries for approval (managers/admins only)"""
    query = select(TimeEntry).where(TimeEntry.approval_status == "pending")
    
    if user_id:
        query = query.where(TimeEntry.user_id == user_id)
    if project_id:
        query = query.where(TimeEntry.project_id == project_id)
    
    query = query.offset(skip).limit(limit).order_by(TimeEntry.start_time.desc())
    
    result = await db.execute(query)
    entries = result.scalars().all()
    
    return [
        {
            "id": entry.id,
            "user_id": entry.user_id,
            "project_id": entry.project_id,
            "task_id": entry.task_id,
            "description": entry.description,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "duration_seconds": entry.duration_seconds,
            "approval_status": entry.approval_status,
        }
        for entry in entries
    ]


@router.patch("/{entry_id}/approve")
async def approve_time_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Approve a single time entry"""
    result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")
    
    if entry.approval_status == "approved":
        raise HTTPException(status_code=400, detail="Entry already approved")
    
    entry.approval_status = "approved"
    entry.approved_by = current_user.id
    entry.approved_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(entry)
    
    return {
        "message": "Time entry approved",
        "entry_id": entry_id,
        "status": "approved",
        "approved_by": current_user.id,
        "approved_at": entry.approved_at.isoformat()
    }


@router.patch("/{entry_id}/reject")
async def reject_time_entry(
    entry_id: int,
    rejection_reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Reject a single time entry"""
    result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")
    
    if entry.approval_status == "rejected":
        raise HTTPException(status_code=400, detail="Entry already rejected")
    
    entry.approval_status = "rejected"
    entry.approved_by = current_user.id
    entry.approved_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(entry)
    
    return {
        "message": "Time entry rejected",
        "entry_id": entry_id,
        "status": "rejected",
        "rejected_by": current_user.id,
        "rejected_at": entry.approved_at.isoformat(),
        "reason": rejection_reason
    }


@router.post("/bulk")
async def bulk_approval(
    request: BulkApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Approve or reject multiple time entries at once"""
    if not request.entry_ids:
        raise HTTPException(status_code=400, detail="No entry IDs provided")
    
    # Verify all entries exist
    result = await db.execute(
        select(TimeEntry).where(TimeEntry.id.in_(request.entry_ids))
    )
    entries = result.scalars().all()
    
    if len(entries) != len(request.entry_ids):
        found_ids = {e.id for e in entries}
        missing_ids = set(request.entry_ids) - found_ids
        raise HTTPException(
            status_code=404, 
            detail=f"Some entries not found: {list(missing_ids)}"
        )
    
    # Update all entries
    now = datetime.utcnow()
    updated_count = 0
    
    for entry in entries:
        if entry.approval_status != request.status.value:
            entry.approval_status = request.status.value
            entry.approved_by = current_user.id
            entry.approved_at = now
            updated_count += 1
    
    await db.commit()
    
    return {
        "message": f"Bulk {request.status.value} completed",
        "total_entries": len(request.entry_ids),
        "updated_count": updated_count,
        "status": request.status.value,
        "processed_by": current_user.id,
        "processed_at": now.isoformat()
    }


@router.get("/stats")
async def get_approval_stats(
    user_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Get approval statistics"""
    from sqlalchemy import func
    
    base_query = select(TimeEntry.approval_status, func.count(TimeEntry.id))
    
    if user_id:
        base_query = base_query.where(TimeEntry.user_id == user_id)
    
    base_query = base_query.group_by(TimeEntry.approval_status)
    
    result = await db.execute(base_query)
    stats = {status: count for status, count in result.all()}
    
    return {
        "pending": stats.get("pending", 0),
        "approved": stats.get("approved", 0),
        "rejected": stats.get("rejected", 0),
        "total": sum(stats.values())
    }


@router.patch("/{entry_id}/reset")
async def reset_approval_status(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Reset an entry back to pending status (admin only)"""
    result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")
    
    entry.approval_status = "pending"
    entry.approved_by = None
    entry.approved_at = None
    
    await db.commit()
    
    return {
        "message": "Approval status reset to pending",
        "entry_id": entry_id,
        "status": "pending"
    }




