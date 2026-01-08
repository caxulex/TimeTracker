"""
API Router for Pay Rates management
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas.payroll import (
    PayRateCreate,
    PayRateUpdate,
    PayRateResponse,
    PayRateWithUser,
    PayRateHistoryResponse
)
from app.services.payroll_service import PayRateService


router = APIRouter(prefix="/api/pay-rates", tags=["Pay Rates"])


@router.post("", response_model=PayRateResponse, status_code=status.HTTP_201_CREATED)
async def create_pay_rate(
    pay_rate_data: PayRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new pay rate for a user.
    Admin only.
    """
    service = PayRateService(db)
    pay_rate = await service.create_pay_rate(pay_rate_data, current_user.id)
    return pay_rate


@router.get("", response_model=dict)
async def list_pay_rates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    List all pay rates with pagination.
    Admin only.
    """
    service = PayRateService(db)
    pay_rates, total = await service.get_all_pay_rates(skip, limit, active_only)
    
    return {
        "items": [
            PayRateWithUser(
                id=pr.id,
                user_id=pr.user_id,
                rate_type=pr.rate_type,
                base_rate=pr.base_rate,
                currency=pr.currency,
                overtime_multiplier=pr.overtime_multiplier,
                effective_from=pr.effective_from,
                effective_to=pr.effective_to,
                is_active=pr.is_active,
                created_by=pr.created_by,
                created_at=pr.created_at,
                updated_at=pr.updated_at,
                user_name=pr.user.name if pr.user else None,
                user_email=pr.user.email if pr.user else None
            )
            for pr in pay_rates
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/user/{user_id}", response_model=List[PayRateResponse])
async def get_user_pay_rates(
    user_id: int,
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all pay rates for a specific user.
    Users can view their own rates, admins can view anyone's.
    """
    if current_user.role not in ["super_admin", "admin", "company_admin"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own pay rates"
        )
    
    service = PayRateService(db)
    pay_rates = await service.get_user_pay_rates(user_id, include_inactive)
    return pay_rates


@router.get("/user/{user_id}/current", response_model=Optional[PayRateResponse])
async def get_user_current_rate(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current active pay rate for a user.
    """
    if current_user.role not in ["super_admin", "admin", "company_admin"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own pay rates"
        )
    
    service = PayRateService(db)
    pay_rate = await service.get_user_active_rate(user_id)
    return pay_rate


@router.get("/{pay_rate_id}", response_model=PayRateResponse)
async def get_pay_rate(
    pay_rate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific pay rate by ID.
    """
    service = PayRateService(db)
    pay_rate = await service.get_pay_rate(pay_rate_id)
    
    if not pay_rate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pay rate not found"
        )
    
    if current_user.role not in ["super_admin", "admin", "company_admin"] and current_user.id != pay_rate.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own pay rates"
        )
    
    return pay_rate


@router.put("/{pay_rate_id}", response_model=PayRateResponse)
async def update_pay_rate(
    pay_rate_id: int,
    pay_rate_data: PayRateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update a pay rate.
    Admin only.
    """
    service = PayRateService(db)
    pay_rate = await service.update_pay_rate(pay_rate_id, pay_rate_data, current_user.id)
    
    if not pay_rate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pay rate not found"
        )
    
    return pay_rate


@router.delete("/{pay_rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pay_rate(
    pay_rate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Soft delete a pay rate (deactivate it).
    Admin only.
    """
    service = PayRateService(db)
    deleted = await service.delete_pay_rate(pay_rate_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pay rate not found"
        )


@router.get("/{pay_rate_id}/history", response_model=List[PayRateHistoryResponse])
async def get_pay_rate_history(
    pay_rate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get the change history for a pay rate.
    Admin only.
    """
    service = PayRateService(db)
    history = await service.get_pay_rate_history(pay_rate_id)
    return history





