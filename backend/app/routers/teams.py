"""
Teams management router
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.models import User, Team, TeamMember
from app.dependencies import get_current_active_user, get_company_filter
from app.schemas.auth import Message
from app.routers.websocket import manager as ws_manager
from app.services.audit_logger import AuditLogger, AuditAction

router = APIRouter()


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class MemberAdd(BaseModel):
    user_id: int
    role: str = Field(default="member", pattern="^(owner|admin|member)$")


class MemberUpdate(BaseModel):
    role: str = Field(..., pattern="^(owner|admin|member)$")


class UserBasicInfo(BaseModel):
    """Basic user info for team member display"""
    id: int
    name: str
    email: str
    role: str
    
    class Config:
        from_attributes = True


class MemberResponse(BaseModel):
    user_id: int
    team_id: int
    role: str
    joined_at: datetime
    user: Optional[UserBasicInfo] = None

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime]
    member_count: Optional[int] = None

    class Config:
        from_attributes = True


class TeamDetailResponse(TeamResponse):
    members: List[MemberResponse] = []


class PaginatedTeams(BaseModel):
    items: List[TeamResponse]
    total: int
    page: int
    page_size: int
    pages: int


@router.get("", response_model=PaginatedTeams)
async def list_teams(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List teams (user sees their teams, admin sees all within company)"""
    base_query = select(Team)
    count_query = select(func.count(Team.id))

    # Multi-tenancy: filter by company
    company_id = get_company_filter(current_user)
    if company_id is not None:
        base_query = base_query.where(Team.company_id == company_id)
        count_query = count_query.where(Team.company_id == company_id)

    # Non-admin users only see teams they're members of
    if current_user.role not in ["super_admin", "admin"]:
        member_subquery = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
        base_query = base_query.where(Team.id.in_(member_subquery))
        count_query = count_query.where(Team.id.in_(member_subquery))

    if search:
        search_filter = f"%{search}%"
        base_query = base_query.where(Team.name.ilike(search_filter))
        count_query = count_query.where(Team.name.ilike(search_filter))

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    offset = (page - 1) * page_size
    query = base_query.offset(offset).limit(page_size).order_by(Team.created_at.desc())
    result = await db.execute(query)
    teams = result.scalars().all()

    # Get member counts
    team_ids = [t.id for t in teams]
    member_counts = {}
    if team_ids:
        count_result = await db.execute(
            select(TeamMember.team_id, func.count(TeamMember.user_id))
            .where(TeamMember.team_id.in_(team_ids))
            .group_by(TeamMember.team_id)
        )
        member_counts = dict(count_result.all())

    items = []
    for team in teams:
        items.append(TeamResponse(
            id=team.id,
            name=team.name,
            owner_id=team.owner_id,
            created_at=team.created_at,
            updated_at=team.updated_at,
            member_count=member_counts.get(team.id, 0)
        ))

    return PaginatedTeams(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 1
    )


@router.get("/{team_id}", response_model=TeamDetailResponse)
async def get_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get team details with members"""
    query = select(Team).where(Team.id == team_id)
    
    # Multi-tenancy: filter by company
    company_id = get_company_filter(current_user)
    if company_id is not None:
        query = query.where(Team.company_id == company_id)
    
    result = await db.execute(query)
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    # Check access
    if current_user.role != "super_admin":
        member_check = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user.id
            )
        )
        if not member_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Get members
    members_result = await db.execute(
        select(TeamMember, User)
        .join(User, TeamMember.user_id == User.id)
        .where(TeamMember.team_id == team_id)
    )
    members_data = members_result.all()

    members = []
    for member, user in members_data:
        members.append(MemberResponse(
            user_id=member.user_id,
            team_id=member.team_id,
            role=member.role,
            joined_at=member.joined_at,
            user=UserBasicInfo(
                id=user.id,
                name=user.name,
                email=user.email,
                role=user.role
            )
        ))

    return TeamDetailResponse(
        id=team.id,
        name=team.name,
        owner_id=team.owner_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=len(members),
        members=members
    )


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_data: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new team"""
    # Multi-tenancy: new teams inherit the company of the creating user
    team = Team(
        name=team_data.name,
        owner_id=current_user.id,
        company_id=current_user.company_id
    )

    db.add(team)
    await db.commit()
    await db.refresh(team)

    # Add creator as owner member
    member = TeamMember(
        team_id=team.id,
        user_id=current_user.id,
        role="owner"
    )
    db.add(member)
    await db.commit()
    
    # Audit log
    await AuditLogger.log(
        db=db,
        action=AuditAction.CREATE,
        resource_type="team",
        resource_id=team.id,
        user_id=current_user.id,
        user_email=current_user.email,
        new_values={"name": team.name, "owner_id": team.owner_id},
        details=f"Created team '{team.name}'"
    )
    await db.commit()

    return TeamResponse(
        id=team.id,
        name=team.name,
        owner_id=team.owner_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=1
    )


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int,
    team_data: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update team (owner/admin only)"""
    query = select(Team).where(Team.id == team_id)
    
    # Multi-tenancy: filter by company
    company_id = get_company_filter(current_user)
    if company_id is not None:
        query = query.where(Team.company_id == company_id)
    
    result = await db.execute(query)
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    # Check permission
    if current_user.role != "super_admin":
        member = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user.id,
                TeamMember.role.in_(["owner", "admin"])
            )
        )
        if not member.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    # Track old values
    old_name = team.name
    
    # Update fields
    if team_data.name:
        team.name = team_data.name
    
    # Audit log if name changed
    if team_data.name and team_data.name != old_name:
        await AuditLogger.log(
            db=db,
            action=AuditAction.UPDATE,
            resource_type="team",
            resource_id=team.id,
            user_id=current_user.id,
            user_email=current_user.email,
            old_values={"name": old_name},
            new_values={"name": team.name},
            details=f"Updated team name from '{old_name}' to '{team.name}'"
        )

    await db.commit()
    await db.refresh(team)

    # Get member count
    count_result = await db.execute(
        select(func.count(TeamMember.user_id)).where(TeamMember.team_id == team_id)
    )
    member_count = count_result.scalar() or 0

    return TeamResponse(
        id=team.id,
        name=team.name,
        owner_id=team.owner_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=member_count
    )


@router.delete("/{team_id}", response_model=Message)
async def delete_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete team (owner only)"""
    query = select(Team).where(Team.id == team_id)
    
    # Multi-tenancy: filter by company
    company_id = get_company_filter(current_user)
    if company_id is not None:
        query = query.where(Team.company_id == company_id)
    
    result = await db.execute(query)
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    # Check permission
    if current_user.role != "super_admin":
        member = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user.id,
                TeamMember.role == "owner"
            )
        )
        if not member.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only team owner can delete")
    
    # Audit log before deletion
    await AuditLogger.log(
        db=db,
        action=AuditAction.DELETE,
        resource_type="team",
        resource_id=team.id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values={"name": team.name, "owner_id": team.owner_id},
        details=f"Deleted team '{team.name}'"
    )

    await db.delete(team)
    await db.commit()

    return Message(message="Team deleted successfully")


@router.post("/{team_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    team_id: int,
    member_data: MemberAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Add member to team (owner/admin only)"""
    # Multi-tenancy: filter by company
    company_id = get_company_filter(current_user)
    
    # Verify team exists and belongs to company
    team_query = select(Team).where(Team.id == team_id)
    if company_id is not None:
        team_query = team_query.where(Team.company_id == company_id)
    team_result = await db.execute(team_query)
    team = team_result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    # Check permission
    if current_user.role != "super_admin":
        member = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user.id,
                TeamMember.role.in_(["owner", "admin"])
            )
        )
        if not member.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    # Check user exists and belongs to same company
    user_query = select(User).where(User.id == member_data.user_id)
    if company_id is not None:
        user_query = user_query.where(User.company_id == company_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check not already member
    existing = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == member_data.user_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already a member")

    new_member = TeamMember(
        team_id=team_id,
        user_id=member_data.user_id,
        role=member_data.role
    )
    db.add(new_member)
    await db.commit()
    await db.refresh(new_member)

    # Send real-time notification to the new member
    await ws_manager.send_personal_message(
        {
            "type": "team_added",
            "data": {
                "team_id": team_id,
                "team_name": team.name,
                "role": member_data.role,
                "message": f"You've been added to team '{team.name}'"
            }
        },
        member_data.user_id
    )

    # Broadcast to existing team members
    await ws_manager.broadcast_to_team(
        {
            "type": "member_added",
            "data": {
                "team_id": team_id,
                "user_id": member_data.user_id,
                "user_name": user.name,
                "role": member_data.role
            }
        },
        team_id,
        exclude_user=member_data.user_id
    )

    return MemberResponse(
        user_id=new_member.user_id,
        team_id=new_member.team_id,
        role=new_member.role,
        joined_at=new_member.joined_at,
        user_name=user.name,
        user_email=user.email
    )


@router.put("/{team_id}/members/{user_id}", response_model=MemberResponse)
async def update_member_role(
    team_id: int,
    user_id: int,
    role_data: MemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update member role (owner only)"""
    # Check permission
    if current_user.role != "super_admin":
        owner_check = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user.id,
                TeamMember.role == "owner"
            )
        )
        if not owner_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only team owner can change roles")

    # Get member
    member_result = await db.execute(
        select(TeamMember, User)
        .join(User, TeamMember.user_id == User.id)
        .where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
    )
    result = member_result.first()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    member, user = result

    member.role = role_data.role
    await db.commit()
    await db.refresh(member)

    return MemberResponse(
        user_id=member.user_id,
        team_id=member.team_id,
        role=member.role,
        joined_at=member.joined_at,
        user_name=user.name,
        user_email=user.email
    )


@router.delete("/{team_id}/members/{user_id}", response_model=Message)
async def remove_member(
    team_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Remove member from team"""
    # Get member
    member_result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id
        )
    )
    member = member_result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Self-removal allowed, otherwise need admin
    if user_id != current_user.id and current_user.role not in ["super_admin", "admin"]:
        admin_check = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user.id,
                TeamMember.role.in_(["owner", "admin"])
            )
        )
        if not admin_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    # Prevent removing last owner
    if member.role == "owner":
        owner_count = await db.execute(
            select(func.count(TeamMember.user_id)).where(
                TeamMember.team_id == team_id,
                TeamMember.role == "owner"
            )
        )
        if owner_count.scalar() <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove last owner")

    await db.delete(member)
    await db.commit()

    return Message(message="Member removed successfully")
