"""
User management router (Admin only)
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import User
from app.schemas.auth import UserResponse, Message
from app.services.auth_service import auth_service
from app.dependencies import get_current_admin_user
from app.utils.password_validator import validate_password_strength
from app.services.audit_logger import AuditLogger, AuditAction
from pydantic import BaseModel, EmailStr, Field

router = APIRouter()


class UserCreate(BaseModel):
    # Basic Info
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="regular_user")
    
    # Contact Information
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = Field(None, max_length=255)
    emergency_contact_phone: Optional[str] = Field(None, max_length=50)
    
    # Employment Details
    job_title: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    employment_type: Optional[str] = Field(None, pattern="^(full_time|part_time|contractor)$")
    start_date: Optional[str] = None  # date as YYYY-MM-DD string
    expected_hours_per_week: Optional[float] = Field(None, ge=0, le=168)
    manager_id: Optional[int] = None
    
    # Payroll Information (optional during creation, will create PayRate)
    pay_rate: Optional[float] = Field(None, ge=0, description="Hourly/daily/monthly rate")
    pay_rate_type: Optional[str] = Field("hourly", pattern="^(hourly|daily|monthly|project_based)$")
    overtime_multiplier: Optional[float] = Field(1.5, ge=1.0, le=3.0)
    currency: Optional[str] = Field("USD", max_length=3)
    
    # Team Assignment (optional, can assign to teams immediately)
    team_ids: Optional[List[int]] = Field(default=[], description="List of team IDs to add user to")


class UserAdminUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class RoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(super_admin|regular_user)$")


class PaginatedUsers(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int


@router.get("", response_model=PaginatedUsers)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """List all users (admin only)"""
    query = select(User)
    count_query = select(func.count(User.id))
    
    if search:
        search_filter = f"%{search}%"
        query = query.where((User.email.ilike(search_filter)) | (User.name.ilike(search_filter)))
        count_query = count_query.where((User.email.ilike(search_filter)) | (User.name.ilike(search_filter)))
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(User.created_at.desc())
    result = await db.execute(query)
    users = result.scalars().all()
    
    return PaginatedUsers(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get user by ID (admin only)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    return user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Create a new user with comprehensive staff information (admin only)
    
    This endpoint creates a user and optionally:
    - Creates a pay rate if payroll info is provided
    - Assigns user to teams if team_ids are provided
    - Sets employment and contact details
    """
    from datetime import date as dt_date
    from app.models import PayRate, Team, TeamMember
    from app.schemas.payroll import RateTypeEnum
    
    # SEC-003: Validate password strength
    is_valid, password_errors = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password does not meet security requirements", "errors": password_errors}
        )
    
    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    # Parse start_date if provided
    parsed_start_date = None
    if user_data.start_date:
        try:
            from datetime import datetime
            parsed_start_date = datetime.strptime(user_data.start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid start_date format. Use YYYY-MM-DD")
    
    # Create user with all fields
    new_user = User(
        # Basic Info
        email=user_data.email,
        password_hash=auth_service.hash_password(user_data.password),
        name=user_data.name,
        role=user_data.role,
        is_active=True,
        
        # Contact Information
        phone=user_data.phone,
        address=user_data.address,
        emergency_contact_name=user_data.emergency_contact_name,
        emergency_contact_phone=user_data.emergency_contact_phone,
        
        # Employment Details
        job_title=user_data.job_title,
        department=user_data.department,
        employment_type=user_data.employment_type,
        start_date=parsed_start_date,
        expected_hours_per_week=user_data.expected_hours_per_week,
        manager_id=user_data.manager_id,
    )
    
    db.add(new_user)
    await db.flush()  # Flush to get user ID without committing
    
    # Create pay rate if payroll info provided
    if user_data.pay_rate is not None and user_data.pay_rate > 0:
        from decimal import Decimal
        pay_rate = PayRate(
            user_id=new_user.id,
            rate_type=user_data.pay_rate_type or "hourly",
            base_rate=Decimal(str(user_data.pay_rate)),
            currency=user_data.currency or "USD",
            overtime_multiplier=Decimal(str(user_data.overtime_multiplier or 1.5)),
            effective_from=parsed_start_date or dt_date.today(),
            is_active=True,
            created_by=current_user.id,
        )
        db.add(pay_rate)
    
    # Assign to teams if team_ids provided
    if user_data.team_ids:
        for team_id in user_data.team_ids:
            # Verify team exists
            team_result = await db.execute(select(Team).where(Team.id == team_id))
            team = team_result.scalar_one_or_none()
            if not team:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Team with ID {team_id} not found"
                )
            
            # Add user to team
            team_member = TeamMember(
                team_id=team_id,
                user_id=new_user.id,
                role="member"
            )
            db.add(team_member)
    
    await db.commit()
    await db.refresh(new_user)
    
    # Audit log
    await AuditLogger.log(
        db=db,
        action=AuditAction.CREATE,
        resource_type="user",
        resource_id=new_user.id,
        user_id=current_user.id,
        user_email=current_user.email,
        new_values={
            "email": new_user.email,
            "name": new_user.name,
            "role": new_user.role,
            "job_title": new_user.job_title,
            "department": new_user.department
        },
        details=f"Created user {new_user.email} with role {new_user.role}"
    )
    await db.commit()
    
    return new_user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update user (admin only)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Track old values for audit
    old_values = {
        "email": user.email,
        "name": user.name,
        "is_active": user.is_active
    }
    
    if user_data.email and user_data.email != user.email:
        email_check = await db.execute(select(User).where(User.email == user_data.email))
        if email_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
        user.email = user_data.email
    
    if user_data.name:
        user.name = user_data.name
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    # Audit log
    new_values = {
        "email": user.email,
        "name": user.name,
        "is_active": user.is_active
    }
    await AuditLogger.log(
        db=db,
        action=AuditAction.UPDATE,
        resource_type="user",
        resource_id=user.id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values=old_values,
        new_values=new_values,
        details=f"Updated user {user.email}"
    )
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/{user_id}", response_model=Message)
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Deactivate user (admin only)"""
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user.is_active = False
    
    # Audit log
    await AuditLogger.log(
        db=db,
        action=AuditAction.DELETE,
        resource_type="user",
        resource_id=user.id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values={"is_active": True},
        new_values={"is_active": False},
        details=f"Deactivated user {user.email}"
    )
    
    await db.commit()
    
    return {"message": "User deactivated successfully"}


@router.delete("/{user_id}/permanent", response_model=Message)
async def permanently_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Permanently delete a user and all associated data (admin only).
    
    WARNING: This action cannot be undone. Use with caution.
    This will delete:
    - The user account
    - All time entries
    - All pay rates
    - Team memberships (but not the teams themselves)
    - Payroll entries
    """
    from app.models import TimeEntry, PayRate, TeamMember, PayrollEntry
    
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Cannot delete yourself"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Prevent deletion of super_admin users (safety check)
    if user.role == "super_admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot permanently delete super admin users"
        )
    
    user_email = user.email
    user_name = user.name
    
    # Delete associated records in correct order (foreign key constraints)
    from sqlalchemy import delete, update
    from app.models import Team
    
    # 1. Delete time entries
    await db.execute(delete(TimeEntry).where(TimeEntry.user_id == user_id))
    
    # 2. Delete pay rates
    await db.execute(delete(PayRate).where(PayRate.user_id == user_id))
    
    # 3. Delete team memberships
    await db.execute(delete(TeamMember).where(TeamMember.user_id == user_id))
    
    # 4. Delete payroll entries
    await db.execute(delete(PayrollEntry).where(PayrollEntry.user_id == user_id))
    
    # 5. Transfer ownership of teams to the admin performing deletion
    await db.execute(
        update(Team).where(Team.owner_id == user_id).values(owner_id=current_user.id)
    )
    
    # 6. Update manager_id references to NULL for users managed by this user
    await db.execute(
        update(User).where(User.manager_id == user_id).values(manager_id=None)
    )
    
    # 7. Finally delete the user
    await db.delete(user)
    
    # Audit log (before commit so we can capture it)
    await AuditLogger.log(
        db=db,
        action=AuditAction.DELETE,
        resource_type="user",
        resource_id=user_id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values={"email": user_email, "name": user_name},
        new_values=None,
        details=f"Permanently deleted user {user_email} and all associated data"
    )
    
    await db.commit()
    
    return {"message": f"User {user_email} permanently deleted"}


@router.put("/{user_id}/role", response_model=UserResponse)
async def change_user_role(
    user_id: int,
    role_data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Change user role (admin only)"""
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    old_role = user.role
    user.role = role_data.role
    
    # Audit log
    await AuditLogger.log(
        db=db,
        action=AuditAction.ROLE_CHANGE,
        resource_type="user",
        resource_id=user.id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values={"role": old_role},
        new_values={"role": user.role},
        details=f"Changed role for {user.email} from {old_role} to {user.role}"
    )
    
    await db.commit()
    await db.refresh(user)
    
    return user
