"""
API Router for Payroll Periods management
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas.payroll import (
    PayrollPeriodCreate,
    PayrollPeriodUpdate,
    PayrollPeriodResponse,
    PayrollPeriodWithEntries,
    PayrollEntryCreate,
    PayrollEntryUpdate,
    PayrollEntryWithAdjustments,
    PayrollEntryResponse,
    PayrollAdjustmentCreate,
    PayrollAdjustmentUpdate,
    PayrollAdjustmentResponse,
    PeriodStatusEnum
)
from app.services.payroll_service import (
    PayrollPeriodService,
    PayrollEntryService,
    PayrollAdjustmentService,
    PayRateService
)


router = APIRouter(prefix="/api/payroll", tags=["Payroll"])


# ============================================
# PAYROLL PERIODS
# ============================================

@router.post("/periods", response_model=PayrollPeriodResponse, status_code=status.HTTP_201_CREATED)
async def create_payroll_period(
    period_data: PayrollPeriodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new payroll period.
    Admin only.
    """
    service = PayrollPeriodService(db)
    period = await service.create_period(period_data)
    return PayrollPeriodResponse(
        id=period.id,
        name=period.name,
        period_type=period.period_type,
        start_date=period.start_date,
        end_date=period.end_date,
        status=period.status,
        total_amount=period.total_amount,
        approved_by=period.approved_by,
        approved_at=period.approved_at,
        created_at=period.created_at,
        updated_at=period.updated_at,
        entries_count=0
    )


@router.get("/periods", response_model=dict)
async def list_payroll_periods(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[PeriodStatusEnum] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    List all payroll periods with pagination.
    Admin only.
    """
    service = PayrollPeriodService(db)
    periods, total = await service.get_periods(skip, limit, status)
    
    return {
        "items": [
            PayrollPeriodResponse(
                id=p.id,
                name=p.name,
                period_type=p.period_type,
                start_date=p.start_date,
                end_date=p.end_date,
                status=p.status,
                total_amount=p.total_amount,
                approved_by=p.approved_by,
                approved_at=p.approved_at,
                created_at=p.created_at,
                updated_at=p.updated_at,
                entries_count=0  # Entries not loaded for list view
            )
            for p in periods
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/periods/{period_id}", response_model=PayrollPeriodWithEntries)
async def get_payroll_period(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get a payroll period with all its entries.
    Admin only.
    """
    service = PayrollPeriodService(db)
    period = await service.get_period_with_entries(period_id)
    
    if not period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payroll period not found"
        )
    
    # Get pay rate service for rate_type lookup
    pay_rate_service = PayRateService(db)
    
    # Transform entries to include user information
    entries_with_users = []
    for entry in period.entries:
        # Get user's pay rate to determine rate_type
        rate_type = None
        if entry.user:
            pay_rate = await pay_rate_service.get_user_active_rate(entry.user_id, period.end_date)
            rate_type = pay_rate.rate_type if pay_rate else None
        
        entry_dict = {
            "id": entry.id,
            "payroll_period_id": entry.payroll_period_id,
            "user_id": entry.user_id,
            "regular_hours": entry.regular_hours,
            "overtime_hours": entry.overtime_hours,
            "regular_rate": entry.regular_rate,
            "overtime_rate": entry.overtime_rate,
            "gross_amount": entry.gross_amount,
            "adjustments_amount": entry.adjustments_amount,
            "net_amount": entry.net_amount,
            "status": entry.status,
            "notes": entry.notes,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
            "user_name": entry.user.name if entry.user else None,
            "user_email": entry.user.email if entry.user else None,
            "rate_type": rate_type,
        }
        entries_with_users.append(entry_dict)
    
    return {
        "id": period.id,
        "name": period.name,
        "period_type": period.period_type,
        "start_date": period.start_date,
        "end_date": period.end_date,
        "status": period.status,
        "total_amount": period.total_amount,
        "approved_by": period.approved_by,
        "approved_at": period.approved_at,
        "created_at": period.created_at,
        "updated_at": period.updated_at,
        "entries_count": len(period.entries),
        "entries": entries_with_users,
    }


@router.put("/periods/{period_id}", response_model=PayrollPeriodResponse)
async def update_payroll_period(
    period_id: int,
    period_data: PayrollPeriodUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update a payroll period.
    Admin only.
    """
    service = PayrollPeriodService(db)
    period = await service.update_period(period_id, period_data)
    
    if not period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payroll period not found"
        )
    
    return period


@router.post("/periods/{period_id}/process", response_model=PayrollPeriodResponse)
async def process_payroll_period(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Process a payroll period - calculate hours and amounts for all users.
    Admin only.
    """
    service = PayrollPeriodService(db)
    period = await service.process_period(period_id)
    
    if not period:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot process period. Make sure it exists and is in draft status."
        )
    
    return period


@router.post("/periods/{period_id}/approve", response_model=PayrollPeriodResponse)
async def approve_payroll_period(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Approve a payroll period.
    Admin only.
    """
    service = PayrollPeriodService(db)
    period = await service.approve_period(period_id, current_user.id)
    
    if not period:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve period. Make sure it exists and is in draft/processing status."
        )
    
    return period


@router.post("/periods/{period_id}/mark-paid", response_model=PayrollPeriodResponse)
async def mark_period_as_paid(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Mark a payroll period as paid.
    Admin only.
    """
    service = PayrollPeriodService(db)
    period = await service.mark_as_paid(period_id)
    
    if not period:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mark period as paid. Make sure it exists and is approved."
        )
    
    return period


@router.delete("/periods/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payroll_period(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete a payroll period (only if in draft status).
    Admin only.
    """
    service = PayrollPeriodService(db)
    deleted = await service.delete_period(period_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete period. Make sure it exists and is in draft status."
        )


# ============================================
# PAYROLL ENTRIES
# ============================================

@router.post("/entries", response_model=PayrollEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_payroll_entry(
    entry_data: PayrollEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new payroll entry manually.
    Admin only.
    """
    service = PayrollEntryService(db)
    entry = await service.create_entry(entry_data)
    return entry


@router.get("/entries/{entry_id}", response_model=PayrollEntryWithAdjustments)
async def get_payroll_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific payroll entry.
    Users can view their own entries, admins can view anyone's.
    """
    service = PayrollEntryService(db)
    entry = await service.get_entry(entry_id)
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payroll entry not found"
        )
    
    if current_user.role != "super_admin" and current_user.id != entry.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own payroll entries"
        )
    
    return entry


@router.get("/periods/{period_id}/entries", response_model=list)
async def get_period_entries(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get all entries for a payroll period.
    Admin only.
    """
    service = PayrollEntryService(db)
    entries = await service.get_entries_by_period(period_id)
    return entries


@router.get("/user/{user_id}/entries", response_model=dict)
async def get_user_payroll_entries(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all payroll entries for a user.
    Users can view their own entries, admins can view anyone's.
    """
    if current_user.role not in ["super_admin", "admin"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own payroll entries"
        )
    
    service = PayrollEntryService(db)
    entries, total = await service.get_user_entries(user_id, skip, limit)
    
    return {
        "items": entries,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.put("/entries/{entry_id}", response_model=PayrollEntryWithAdjustments)
async def update_payroll_entry(
    entry_id: int,
    entry_data: PayrollEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update a payroll entry.
    Admin only.
    """
    service = PayrollEntryService(db)
    entry = await service.update_entry(entry_id, entry_data)
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payroll entry not found"
        )
    
    return entry


# ============================================
# PAYROLL ADJUSTMENTS
# ============================================

@router.post("/adjustments", response_model=PayrollAdjustmentResponse, status_code=status.HTTP_201_CREATED)
async def create_payroll_adjustment(
    adjustment_data: PayrollAdjustmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new payroll adjustment.
    Admin only.
    """
    service = PayrollAdjustmentService(db)
    adjustment = await service.create_adjustment(adjustment_data, current_user.id)
    return adjustment


@router.get("/entries/{entry_id}/adjustments", response_model=list)
async def get_entry_adjustments(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all adjustments for a payroll entry.
    """
    # First check if user has access to this entry
    entry_service = PayrollEntryService(db)
    entry = await entry_service.get_entry(entry_id)
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payroll entry not found"
        )
    
    if current_user.role != "super_admin" and current_user.id != entry.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own payroll adjustments"
        )
    
    service = PayrollAdjustmentService(db)
    adjustments = await service.get_entry_adjustments(entry_id)
    return adjustments


@router.put("/adjustments/{adjustment_id}", response_model=PayrollAdjustmentResponse)
async def update_payroll_adjustment(
    adjustment_id: int,
    adjustment_data: PayrollAdjustmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update a payroll adjustment.
    Admin only.
    """
    service = PayrollAdjustmentService(db)
    adjustment = await service.update_adjustment(adjustment_id, adjustment_data)
    
    if not adjustment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payroll adjustment not found"
        )
    
    return adjustment


@router.delete("/adjustments/{adjustment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payroll_adjustment(
    adjustment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete a payroll adjustment.
    Admin only.
    """
    service = PayrollAdjustmentService(db)
    deleted = await service.delete_adjustment(adjustment_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payroll adjustment not found"
        )








