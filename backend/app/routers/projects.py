"""
Projects management router
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    FILTER_NULL_COMPANY,
    apply_company_filter,
    get_company_filter,
    get_current_active_user,
)
from app.models import (
    Project,
    ProjectBudgetHistory,
    Task,
    Team,
    TeamMember,
    TimeEntry,
    User,
)
from app.routers.websocket import manager as ws_manager
from app.schemas.auth import Message
from app.services.audit_logger import AuditAction, AuditLogger

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    team_id: int
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    # Budget fields (admin only)
    budget_amount: Optional[float] = Field(None, ge=0, description="Project budget in USD")
    deadline: Optional[date] = Field(None, description="Project deadline date")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    is_archived: Optional[bool] = None
    team_id: Optional[int] = None
    # Budget fields (admin only)
    budget_amount: Optional[float] = Field(None, ge=0, description="Project budget in USD")
    deadline: Optional[date] = Field(None, description="Project deadline date")
    budget_change_reason: Optional[str] = Field(None, max_length=500, description="Reason for budget change")


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
    # Budget fields (only populated for admins)
    budget_amount: Optional[float] = None
    deadline: Optional[date] = None

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
            select(Team).where(Team.id == team_id, Team.deleted_at.is_(None))
        )
    elif company_id == FILTER_NULL_COMPANY:
        # Platform user - can only access teams with NULL company_id
        team_result = await db.execute(
            select(Team).where(
                Team.id == team_id,
                Team.company_id.is_(None),
                Team.deleted_at.is_(None),
            )
        )
    else:
        # Company-scoped user
        team_result = await db.execute(
            select(Team).where(
                Team.id == team_id,
                Team.company_id == company_id,
                Team.deleted_at.is_(None),
            )
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
        # Keep this enrichment unfiltered: project rows remain valid even when
        # a parent team is soft-deleted, and responses should still show the
        # historical team label.
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

    # Check if user is admin for budget visibility
    is_admin = current_user.role in ["super_admin", "admin", "company_admin"]

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
            task_count=task_counts.get(project.id, 0),
            budget_amount=float(project.budget_amount) if project.budget_amount and is_admin else None,
            deadline=project.deadline if is_admin else None
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
    is_admin = current_user.role in ["super_admin", "admin", "company_admin"]
    if not is_admin:
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
        task_count=task_count,
        budget_amount=float(project.budget_amount) if project.budget_amount and is_admin else None,
        deadline=project.deadline if is_admin else None
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new project.

    Open to any authenticated user who has access to the target team
    via :func:`check_team_access`:

    - ``super_admin`` / ``admin`` / ``company_admin``: any team in
      their company (super_admin: any team, any company).
    - Regular users: only teams they are a ``TeamMember`` of.

    Mirrors the staff task-creation relaxation made on 2026-05-14
    (PR #23 / option ``a``): creation is gated by visibility, not by
    role. Editing, archiving, and deleting existing projects remain
    admin-only (see :func:`update_project` and friends).

    Admin-only fields (``budget_amount`` and ``deadline``) are
    silently dropped when submitted by a non-admin, so the UI can
    safely hide them without the backend rejecting the request.
    """
    # Check team access
    has_access = await check_team_access(db, project_data.team_id, current_user)
    if not has_access:
        company_id = get_company_filter(current_user)
        deleted_team_query = select(Team).where(
            Team.id == project_data.team_id,
            Team.deleted_at.is_not(None),
        )
        deleted_team_query = apply_company_filter(
            deleted_team_query,
            Team.company_id,
            company_id,
        )
        deleted_team = (await db.execute(deleted_team_query)).scalar_one_or_none()
        if deleted_team is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Target team has been deleted. Restore it first.",
            )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this team")

    # Only admins can set budget fields
    is_admin = current_user.role in ["super_admin", "admin", "company_admin"]

    project = Project(
        name=project_data.name,
        description=project_data.description,
        team_id=project_data.team_id,
        color=project_data.color or "#3B82F6",
        budget_amount=Decimal(str(project_data.budget_amount)) if project_data.budget_amount is not None and is_admin else None,
        deadline=project_data.deadline if is_admin else None
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    # If budget was set, log initial budget history
    if is_admin and (project_data.budget_amount is not None or project_data.deadline is not None):
        budget_history = ProjectBudgetHistory(
            project_id=project.id,
            changed_by_id=current_user.id,
            old_budget_amount=None,
            new_budget_amount=project.budget_amount,
            old_deadline=None,
            new_deadline=project.deadline,
            change_reason="Initial budget set on project creation"
        )
        db.add(budget_history)
        await db.commit()

    # Audit log
    audit_values = {"name": project.name, "team_id": project.team_id, "color": project.color}
    if is_admin:
        audit_values["budget_amount"] = float(project.budget_amount) if project.budget_amount else None
        audit_values["deadline"] = str(project.deadline) if project.deadline else None

    await AuditLogger.log(
        db=db,
        action=AuditAction.CREATE,
        resource_type="project",
        resource_id=project.id,
        user_id=current_user.id,
        user_email=current_user.email,
        new_values=audit_values,
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
        task_count=0,
        budget_amount=float(project.budget_amount) if project.budget_amount and is_admin else None,
        deadline=project.deadline if is_admin else None
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
    is_admin = current_user.role in ["super_admin", "admin", "company_admin"]
    if not is_admin:
        has_access = await check_team_access(db, project.team_id, current_user)
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # If team_id is being changed, validate the new team
    if project_data.team_id is not None and project_data.team_id != project.team_id:
        # Verify new team exists and user has access
        new_team_query = select(Team).where(
            Team.id == project_data.team_id,
            Team.deleted_at.is_(None),
        )
        company_id = get_company_filter(current_user)
        new_team_query = apply_company_filter(new_team_query, Team.company_id, company_id)
        new_team_result = await db.execute(new_team_query)
        new_team = new_team_result.scalar_one_or_none()
        if not new_team:
            deleted_team_query = select(Team).where(
                Team.id == project_data.team_id,
                Team.deleted_at.is_not(None),
            )
            deleted_team_query = apply_company_filter(
                deleted_team_query,
                Team.company_id,
                company_id,
            )
            deleted_team = (await db.execute(deleted_team_query)).scalar_one_or_none()
            if deleted_team is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Target team has been deleted. Restore it first.",
                )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid team_id")

    # Track old values
    old_values = {"name": project.name, "color": project.color, "is_archived": project.is_archived, "team_id": project.team_id}
    old_budget_amount = project.budget_amount
    old_deadline = project.deadline

    # Update fields - exclude budget fields for non-admins
    update_data = project_data.model_dump(exclude_unset=True)

    # Remove budget fields from update if not admin
    budget_change_reason = update_data.pop("budget_change_reason", None)
    if not is_admin:
        update_data.pop("budget_amount", None)
        update_data.pop("deadline", None)
    else:
        # Convert budget_amount to Decimal for database
        if "budget_amount" in update_data and update_data["budget_amount"] is not None:
            update_data["budget_amount"] = Decimal(str(update_data["budget_amount"]))

    for key, value in update_data.items():
        setattr(project, key, value)

    # Track budget changes for history (admin only)
    budget_changed = False
    if is_admin:
        new_budget_amount = project.budget_amount
        new_deadline = project.deadline

        if old_budget_amount != new_budget_amount or old_deadline != new_deadline:
            budget_changed = True
            budget_history = ProjectBudgetHistory(
                project_id=project.id,
                changed_by_id=current_user.id,
                old_budget_amount=old_budget_amount,
                new_budget_amount=new_budget_amount,
                old_deadline=old_deadline,
                new_deadline=new_deadline,
                change_reason=budget_change_reason
            )
            db.add(budget_history)

    # Audit log
    new_values = {
        "name": project.name,
        "color": project.color,
        "is_archived": project.is_archived,
        "team_id": project.team_id,
    }
    if is_admin:
        old_values["budget_amount"] = float(old_budget_amount) if old_budget_amount else None
        old_values["deadline"] = str(old_deadline) if old_deadline else None
        new_values["budget_amount"] = float(project.budget_amount) if project.budget_amount else None
        new_values["deadline"] = str(project.deadline) if project.deadline else None

    if old_values != new_values or budget_changed:
        await AuditLogger.log(
            db=db,
            action=AuditAction.UPDATE,
            resource_type="project",
            resource_id=project.id,
            user_id=current_user.id,
            user_email=current_user.email,
            old_values=old_values,
            new_values=new_values,
            details=f"Updated project '{project.name}'" + (" (budget changed)" if budget_changed else "")
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
        task_count=task_count,
        budget_amount=float(project.budget_amount) if project.budget_amount and is_admin else None,
        deadline=project.deadline if is_admin else None
    )


@router.delete("/{project_id}", response_model=Message)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Permanently delete a project (hard delete)"""
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

    # Check if there are any time entries associated with this project
    time_entries_count = await db.execute(
        select(func.count()).select_from(TimeEntry).where(TimeEntry.project_id == project_id)
    )
    if time_entries_count.scalar() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete project with existing time entries. Archive it instead."
        )

    project_name = project.name

    # Delete associated tasks first
    await db.execute(delete(Task).where(Task.project_id == project_id))

    # Permanently delete the project
    await db.delete(project)

    # Audit log
    await AuditLogger.log(
        db=db,
        action=AuditAction.DELETE,
        resource_type="project",
        resource_id=project_id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values={"name": project_name},
        new_values=None,
        details=f"Permanently deleted project '{project_name}'"
    )

    await db.commit()

    return Message(message="Project deleted permanently")


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

