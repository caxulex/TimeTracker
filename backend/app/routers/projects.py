"""
Projects management router
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.models import User, Team, TeamMember, Project, Task
from app.dependencies import get_current_active_user, get_company_filter, apply_company_filter, FILTER_NULL_COMPANY
from app.schemas.auth import Message
from app.routers.websocket import manager as ws_manager
from app.services.audit_logger import AuditLogger, AuditAction

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    team_id: int
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    is_archived: Optional[bool] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    team_id: int
    team_name: Optional[str] = None
    color: str
    is_archived: bool
    created_at: datetime
    updated_at: Optional[datetime]
    task_count: Optional[int] = None

    class Config:
        from_attributes = True


class PaginatedProjects(BaseModel):
    items: List[ProjectResponse]
    total: int
    page: int
    page_size: int
    pages: int


async def check_team_access(db: AsyncSession, team_id: int, user: User, require_admin: bool = False) -> bool:
    """Check if user has access to team (within their company)"""
    # Multi-tenancy: first verify team belongs to user's company
    company_id = get_company_filter(user)
    
    # Build the query based on company filter
    if company_id is None:
        # Super admin - can access any team
        team_result = await db.execute(
            select(Team).where(Team.id == team_id)
        )
    elif company_id == FILTER_NULL_COMPANY:
        # Platform user - can only access teams with NULL company_id
        team_result = await db.execute(
            select(Team).where(Team.id == team_id, Team.company_id.is_(None))
        )
    else:
        # Company-scoped user
        team_result = await db.execute(
            select(Team).where(Team.id == team_id, Team.company_id == company_id)
        )
    
    if not team_result.scalar_one_or_none():
        return False
    
    if user.role in ["super_admin", "admin", "company_admin"]:
        return True
    
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user.id
        )
    )
    return result.scalar_one_or_none() is not None


@router.get("", response_model=PaginatedProjects)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    team_id: Optional[int] = None,
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List projects (user sees projects from their teams within their company)"""
    base_query = select(Project).join(Team, Project.team_id == Team.id)
    count_query = select(func.count(Project.id)).join(Team, Project.team_id == Team.id)
    
    # Multi-tenancy: filter by company through team
    company_id = get_company_filter(current_user)
    base_query = apply_company_filter(base_query, Team.company_id, company_id)
    count_query = apply_company_filter(count_query, Team.company_id, company_id)
    
    # Filter by accessible teams for non-admin users
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        user_teams = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
        access_filter = Project.team_id.in_(user_teams)
        base_query = base_query.where(access_filter)
        count_query = count_query.where(access_filter)
    
    if team_id:
        base_query = base_query.where(Project.team_id == team_id)
        count_query = count_query.where(Project.team_id == team_id)
    
    if not include_archived:
        base_query = base_query.where(Project.is_archived == False)
        count_query = count_query.where(Project.is_archived == False)
    
    if search:
        search_filter = f"%{search}%"
        base_query = base_query.where(Project.name.ilike(search_filter))
        count_query = count_query.where(Project.name.ilike(search_filter))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * page_size
    query = base_query.offset(offset).limit(page_size).order_by(Project.created_at.desc())
    result = await db.execute(query)
    projects = result.scalars().all()
    
    # Get team names
    team_ids = [p.team_id for p in projects]
    team_names = {}
    if team_ids:
        teams_result = await db.execute(select(Team.id, Team.name).where(Team.id.in_(team_ids)))
        team_names = dict(teams_result.all())
    
    # Get task counts
    task_counts = {}
    project_ids = [p.id for p in projects]
    if project_ids:
        task_count_result = await db.execute(
            select(Task.project_id, func.count(Task.id))
            .where(Task.project_id.in_(project_ids))
            .group_by(Task.project_id)
        )
        task_counts = dict(task_count_result.all())
    
    items = []
    for project in projects:
        item = ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            team_id=project.team_id,
            team_name=team_names.get(project.team_id),
            color=project.color,
            is_archived=project.is_archived,
            created_at=project.created_at,
            updated_at=project.updated_at,
            task_count=task_counts.get(project.id, 0)
        )
        items.append(item)
    
    return PaginatedProjects(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 1
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get project details"""
    # Multi-tenancy: join with team to filter by company
    query = select(Project).join(Team, Project.team_id == Team.id).where(Project.id == project_id)
    company_id = get_company_filter(current_user)
    query = apply_company_filter(query, Team.company_id, company_id)
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    # Check access (team membership for non-admins)
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        has_access = await check_team_access(db, project.team_id, current_user)
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Get team name
    team_result = await db.execute(select(Team.name).where(Team.id == project.team_id))
    team_name = team_result.scalar()
    
    # Get task count
    task_count_result = await db.execute(
        select(func.count(Task.id)).where(Task.project_id == project_id)
    )
    task_count = task_count_result.scalar() or 0
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        team_id=project.team_id,
        team_name=team_name,
        color=project.color,
        is_archived=project.is_archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
        task_count=task_count
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new project"""
    # Check team access
    has_access = await check_team_access(db, project_data.team_id, current_user)
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this team")
    
    project = Project(
        name=project_data.name,
        description=project_data.description,
        team_id=project_data.team_id,
        color=project_data.color or "#3B82F6"
    )
    
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    # Audit log
    await AuditLogger.log(
        db=db,
        action=AuditAction.CREATE,
        resource_type="project",
        resource_id=project.id,
        user_id=current_user.id,
        user_email=current_user.email,
        new_values={"name": project.name, "team_id": project.team_id, "color": project.color},
        details=f"Created project '{project.name}' in team {project.team_id}"
    )
    await db.commit()
    
    # Get team name
    team_result = await db.execute(select(Team.name).where(Team.id == project.team_id))
    team_name = team_result.scalar()
    
    # Notify all team members about new project
    await ws_manager.broadcast_to_team(
        {
            "type": "project_created",
            "data": {
                "project_id": project.id,
                "project_name": project.name,
                "team_id": project.team_id,
                "team_name": team_name,
                "color": project.color,
                "created_by": current_user.name
            }
        },
        project.team_id
    )
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        team_id=project.team_id,
        team_name=team_name,
        color=project.color,
        is_archived=project.is_archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
        task_count=0
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a project"""
    # Multi-tenancy: join with team to filter by company
    query = select(Project).join(Team, Project.team_id == Team.id).where(Project.id == project_id)
    company_id = get_company_filter(current_user)
    query = apply_company_filter(query, Team.company_id, company_id)
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    # Check access (team membership for non-admins)
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        has_access = await check_team_access(db, project.team_id, current_user)
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Track old values
    old_values = {"name": project.name, "color": project.color, "is_archived": project.is_archived}
    
    # Update fields
    update_data = project_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    
    # Audit log
    new_values = {"name": project.name, "color": project.color, "is_archived": project.is_archived}
    if old_values != new_values:
        await AuditLogger.log(
            db=db,
            action=AuditAction.UPDATE,
            resource_type="project",
            resource_id=project.id,
            user_id=current_user.id,
            user_email=current_user.email,
            old_values=old_values,
            new_values=new_values,
            details=f"Updated project '{project.name}'"
        )

    await db.commit()
    await db.refresh(project)
    
    # Get team name
    team_result = await db.execute(select(Team.name).where(Team.id == project.team_id))
    team_name = team_result.scalar()
    
    # Get task count
    task_count_result = await db.execute(
        select(func.count(Task.id)).where(Task.project_id == project_id)
    )
    task_count = task_count_result.scalar() or 0
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        team_id=project.team_id,
        team_name=team_name,
        color=project.color,
        is_archived=project.is_archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
        task_count=task_count
    )


@router.delete("/{project_id}", response_model=Message)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a project (archive it)"""
    # Multi-tenancy: join with team to filter by company
    query = select(Project).join(Team, Project.team_id == Team.id).where(Project.id == project_id)
    company_id = get_company_filter(current_user)
    query = apply_company_filter(query, Team.company_id, company_id)
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    # Check access (team membership for non-admins)
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        has_access = await check_team_access(db, project.team_id, current_user)
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Archive instead of hard delete
    project.is_archived = True
    
    # Audit log
    await AuditLogger.log(
        db=db,
        action=AuditAction.DELETE,
        resource_type="project",
        resource_id=project.id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values={"is_archived": False},
        new_values={"is_archived": True},
        details=f"Archived project '{project.name}'"
    )
    
    await db.commit()
    
    return Message(message="Project archived successfully")


@router.post("/{project_id}/restore", response_model=ProjectResponse)
async def restore_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Restore an archived project"""
    # Multi-tenancy: join with team to filter by company
    query = select(Project).join(Team, Project.team_id == Team.id).where(Project.id == project_id)
    company_id = get_company_filter(current_user)
    query = apply_company_filter(query, Team.company_id, company_id)
    
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    
    # Check access (team membership for non-admins)
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        has_access = await check_team_access(db, project.team_id, current_user)
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    project.is_archived = False
    await db.commit()
    await db.refresh(project)
    
    # Get team name
    team_result = await db.execute(select(Team.name).where(Team.id == project.team_id))
    team_name = team_result.scalar()
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        team_id=project.team_id,
        team_name=team_name,
        color=project.color,
        is_archived=project.is_archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
        task_count=0
    )

