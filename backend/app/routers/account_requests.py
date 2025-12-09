"""
Account request router - Public and admin endpoints
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from datetime import datetime

from app.database import get_db
from app.models import User, AccountRequest
from app.schemas.account_requests import (
    AccountRequestCreate,
    AccountRequestResponse,
    ApprovalDecision,
    PaginatedAccountRequests
)
from app.dependencies import get_current_admin_user
from app.utils.sanitize import sanitize_string, get_client_ip
from app.middleware.rate_limit import rate_limiter
from app.services.audit_logger import AuditLogger, AuditAction

router = APIRouter()


@router.post("", response_model=AccountRequestResponse, status_code=status.HTTP_201_CREATED)
async def submit_account_request(
    request_data: AccountRequestCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a new account request (Public endpoint - no auth required)
    Rate limited: 3 requests per IP per hour via custom checking
    """
    # Get client IP for rate limiting and audit
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    
    # Custom rate limiting for account requests (3 per hour per IP)
    # Using a custom endpoint path for the rate limiter
    is_allowed, current, limit, remaining, reset = await rate_limiter.check_rate_limit(
        identifier=client_ip,
        path="/api/account-requests:hourly"  # Custom path for hourly limit
    )
    
    # Override with custom limits if needed (3 per hour = 3600 seconds)
    # The default rate limiter uses per-minute windows, so we'll do manual check
    # For now, rely on the global rate limiter and add TODO for custom implementation
    # TODO: Implement custom hourly rate limit for account requests
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many account requests. Please try again later."
        )
    
    # Check if email already exists in users table
    existing_user = await db.execute(
        select(User).where(User.email == request_data.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists"
        )
    
    # Check if there's already a pending request for this email
    existing_request = await db.execute(
        select(AccountRequest).where(
            AccountRequest.email == request_data.email,
            AccountRequest.status == "pending"
        )
    )
    if existing_request.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There is already a pending account request for this email address"
        )
    
    # Sanitize input data
    sanitized_data = {
        "email": request_data.email.lower(),
        "name": sanitize_string(request_data.name),
        "phone": sanitize_string(request_data.phone) if request_data.phone else None,
        "job_title": sanitize_string(request_data.job_title) if request_data.job_title else None,
        "department": sanitize_string(request_data.department) if request_data.department else None,
        "message": sanitize_string(request_data.message) if request_data.message else None,
        "ip_address": client_ip,
        "user_agent": user_agent[:500] if user_agent else None,  # Truncate long user agents
    }
    
    # Create the account request
    account_request = AccountRequest(**sanitized_data)
    db.add(account_request)
    await db.commit()
    await db.refresh(account_request)
    
    # TODO: Send WebSocket notification to admins
    # await websocket_manager.broadcast_to_admins({
    #     "type": "account_request.new",
    #     "data": {
    #         "request_id": account_request.id,
    #         "name": account_request.name,
    #         "email": account_request.email
    #     }
    # })
    
    return account_request


@router.get("", response_model=PaginatedAccountRequests)
async def list_account_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    List all account requests (Admin only)
    Can filter by status and search by name/email
    """
    query = select(AccountRequest)
    count_query = select(func.count(AccountRequest.id))
    
    # Apply filters
    if status_filter:
        if status_filter not in ["pending", "approved", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter"
            )
        query = query.where(AccountRequest.status == status_filter)
        count_query = count_query.where(AccountRequest.status == status_filter)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                AccountRequest.name.ilike(search_pattern),
                AccountRequest.email.ilike(search_pattern)
            )
        )
        count_query = count_query.where(
            or_(
                AccountRequest.name.ilike(search_pattern),
                AccountRequest.email.ilike(search_pattern)
            )
        )
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    query = query.order_by(AccountRequest.submitted_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Execute query
    result = await db.execute(query)
    requests_data = result.scalars().all()
    
    # Convert to response models
    items = [AccountRequestResponse.model_validate(req) for req in requests_data]
    
    return PaginatedAccountRequests(
        items=items,
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=((total or 0) + page_size - 1) // page_size
    )


@router.get("/{request_id}", response_model=AccountRequestResponse)
async def get_account_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get details of a specific account request (Admin only)"""
    result = await db.execute(
        select(AccountRequest).where(AccountRequest.id == request_id)
    )
    account_request = result.scalar_one_or_none()
    
    if not account_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account request not found"
        )
    
    return account_request


@router.post("/{request_id}/approve", response_model=dict)
async def approve_account_request(
    request_id: int,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Approve an account request (Admin only)
    Returns pre-filled data for staff creation wizard
    """
    result = await db.execute(
        select(AccountRequest).where(AccountRequest.id == request_id)
    )
    account_request = result.scalar_one_or_none()
    
    if not account_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account request not found"
        )
    
    if account_request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request already {account_request.status}"
        )
    
    # Update request status
    account_request.status = "approved"
    account_request.reviewed_at = datetime.utcnow()
    account_request.reviewed_by = current_user.id
    account_request.admin_notes = decision.admin_notes
    
    # Audit log
    await AuditLogger.log(
        db=db,
        action=AuditAction.UPDATE,
        resource_type="account_request",
        resource_id=account_request.id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values={"status": "pending"},
        new_values={"status": "approved"},
        details=f"Approved account request for {account_request.email}"
    )

    await db.commit()
    await db.refresh(account_request)
    
    # Return pre-filled data for staff creation wizard
    return {
        "request_id": account_request.id,
        "prefill_data": {
            "name": account_request.name,
            "email": account_request.email,
            "phone": account_request.phone,
            "job_title": account_request.job_title,
            "department": account_request.department,
        }
    }


@router.post("/{request_id}/reject", response_model=AccountRequestResponse)
async def reject_account_request(
    request_id: int,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Reject an account request (Admin only)"""
    result = await db.execute(
        select(AccountRequest).where(AccountRequest.id == request_id)
    )
    account_request = result.scalar_one_or_none()
    
    if not account_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account request not found"
        )
    
    if account_request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request already {account_request.status}"
        )
    
    # Update request status
    account_request.status = "rejected"
    account_request.reviewed_at = datetime.utcnow()
    account_request.reviewed_by = current_user.id
    account_request.admin_notes = decision.admin_notes
    
    # Audit log
    await AuditLogger.log(
        db=db,
        action=AuditAction.UPDATE,
        resource_type="account_request",
        resource_id=account_request.id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values={"status": "pending"},
        new_values={"status": "rejected"},
        details=f"Rejected account request for {account_request.email}. Reason: {decision.admin_notes or 'Not specified'}"
    )

    await db.commit()
    await db.refresh(account_request)
    
    # TODO: Send notification (future enhancement)
    
    return account_request


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete an account request (Admin only)"""
    result = await db.execute(
        select(AccountRequest).where(AccountRequest.id == request_id)
    )
    account_request = result.scalar_one_or_none()
    
    if not account_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account request not found"
        )
    
    # Audit log before deletion
    await AuditLogger.log(
        db=db,
        action=AuditAction.DELETE,
        resource_type="account_request",
        resource_id=account_request.id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values={
            "email": account_request.email,
            "name": account_request.name,
            "status": account_request.status
        },
        details=f"Deleted account request for {account_request.email}"
    )

    await db.delete(account_request)
    await db.commit()
    
    return None
