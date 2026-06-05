"""
Projects management router
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import selectinload
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
    ProjectTeam,
    Task,
    Team,
    TeamMember,
    TimeEntry,
    User,
)
from app.routers.websocket import manager as ws_manager
from app.schemas.auth import Message
from app.services.audit_logger import AuditAction, AuditLogger
from app.services.project_service import (
    delete_project_with_cascade,
    get_merge_preview,
    merge_projects,
)
from app.services.project_team_service import (
    add_team_to_project,
    build_project_visibility_filter,
    list_project_teams,
    remove_team_from_project,
)

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


class ProjectTeamAssociationResponse(BaseModel):
    team_id: int
    team_name: str
    is_primary: bool
    added_by_name: Optional[str] = None
    added_at: Optional[datetime] = None


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
    team_associations: list[ProjectTeamAssociationResponse] = Field(default_factory=list)
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


class ProjectTeamAddRequest(BaseModel):
    team_id: int


class ProjectArchiveRequest(BaseModel):
    is_archived: bool


class ProjectDeleteResponse(BaseModel):
    deleted_tasks: int
    deleted_entries: int


class ProjectDeletePreviewResponse(BaseModel):
    tasks: int
    entries: int


class ProjectMergeRequest(BaseModel):
    target_project_id: int


class ProjectMergeResponse(BaseModel):
    moved_tasks: int
    moved_entries: int
    renamed_tasks: list[str]
    archived_source: bool


class ProjectMergePreviewResponse(BaseModel):
    tasks_to_move: int
    entries_to_move: int
    task_name_conflicts: list[str]
    target_existing_tasks: int
    source_will_be_archived: bool


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


async def check_project_visibility(db: AsyncSession, project_id: int, user: User) -> bool:
    """Return True when a user can see a project via primary or associated team."""
    if user.role in ["super_admin", "admin", "company_admin"]:
        return True

    # Visibility rule: regular users can access projects from either
    # their primary teams (projects.team_id) or shared associations
    # in project_teams.
    visibility_query = select(Project.id).where(
        Project.id == project_id,
        build_project_visibility_filter(user.id),
    )
    return (await db.execute(visibility_query)).scalar_one_or_none() is not None


def _serialize_project_team_associations(
    *,
    project: Project,
    primary_team_name: Optional[str],
) -> list[ProjectTeamAssociationResponse]:
    """Build team association rows with primary team first."""
    details_by_team_id: dict[int, ProjectTeamAssociationResponse] = {}

    for assoc in project.team_associations:
        team_name = assoc.team.name if assoc.team is not None else None
        if team_name is None and assoc.team_id == project.team_id:
            team_name = primary_team_name

        details_by_team_id[assoc.team_id] = ProjectTeamAssociationResponse(
            team_id=assoc.team_id,
            team_name=team_name or "Unknown",
            is_primary=assoc.team_id == project.team_id,
            added_by_name=assoc.added_by.name if assoc.added_by is not None else None,
            added_at=assoc.added_at,
        )

    primary_row = details_by_team_id.get(project.team_id)
    if primary_row is None:
        primary_row = ProjectTeamAssociationResponse(
            team_id=project.team_id,
            team_name=primary_team_name or "Unknown",
            is_primary=True,
            added_by_name=None,
            added_at=project.created_at,
        )
    else:
        primary_row.is_primary = True

    rows = [primary_row]
    for team_id, data in details_by_team_id.items():
        if team_id != project.team_id:
            rows.append(data)
    return rows


async def _get_company_scoped_project(
    *,
    db: AsyncSession,
    project_id: int,
    current_user: User,
) -> Optional[Project]:
    query = select(Project).join(Team, Project.team_id == Team.id).where(Project.id == project_id)
    query = apply_company_filter(query, Team.company_id, get_company_filter(current_user))
    return (await db.execute(query)).scalar_one_or_none()


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
    """List projects scoped to the caller's company."""
    base_query = (
        select(Project)
        .join(Team, Project.team_id == Team.id)
        .options(
            selectinload(Project.team_associations).selectinload(ProjectTeam.team),
            selectinload(Project.team_associations).selectinload(ProjectTeam.added_by),
        )
    )
    count_query = select(func.count(Project.id)).join(Team, Project.team_id == Team.id)

    # Multi-tenancy: filter by company through team
    company_id = get_company_filter(current_user)
    base_query = apply_company_filter(base_query, Team.company_id, company_id)
    count_query = apply_company_filter(count_query, Team.company_id, company_id)

    # Non-admin users see all projects in their company so they
    # can discover and self-add projects via the "Add to my team"
    # action. Operational access (time entries, tasks, reports)
    # remains gated by team association.

    if team_id:
        # Team filter semantics: include projects owned by the team and
        # projects shared to the team through project_teams.
        team_filter = or_(
            Project.team_id == team_id,
            Project.id.in_(
                select(ProjectTeam.project_id).where(ProjectTeam.team_id == team_id)
            ),
        )
        base_query = base_query.where(team_filter)
        count_query = count_query.where(team_filter)

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
        team_associations = _serialize_project_team_associations(
            project=project,
            primary_team_name=team_names.get(project.team_id),
        )
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
            team_associations=team_associations,
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
        has_access = await check_project_visibility(db, project.id, current_user)
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

    # Keep project_teams in sync for new projects so the primary team is
    # always represented in association metadata.
    db.add(
        ProjectTeam(
            project_id=project.id,
            team_id=project.team_id,
            added_by_user_id=current_user.id,
        )
    )
    await db.commit()

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


@router.post("/{project_id}/teams", status_code=status.HTTP_201_CREATED, response_model=Message)
async def add_team_to_project_endpoint(
    project_id: int,
    body: ProjectTeamAddRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a team association to a project.

    Any authenticated user may associate a team with a project.
    """
    success, error_code = await add_team_to_project(
        project_id=project_id,
        team_id=body.team_id,
        acting_user_id=current_user.id,
        acting_user_email=current_user.email,
        company_id=get_company_filter(current_user),
        db=db,
    )

    if success:
        return Message(message="Team associated with project")
    if error_code in ["project_not_found", "team_not_found"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or team not found")
    if error_code == "different_company":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project and team must belong to the same company")
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to associate team")


@router.delete("/{project_id}/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_from_project_endpoint(
    project_id: int,
    team_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a team association from a project.

    Any authenticated user may remove a shared association.
    """
    success, error_code = await remove_team_from_project(
        project_id=project_id,
        team_id=team_id,
        acting_user_id=current_user.id,
        acting_user_email=current_user.email,
        company_id=get_company_filter(current_user),
        db=db,
    )

    if success:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if error_code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project-team association not found")
    if error_code == "primary_team":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the primary team. Change project.team_id first.",
        )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to remove team association")


@router.get("/{project_id}/teams", response_model=List[ProjectTeamAssociationResponse])
async def list_project_teams_endpoint(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all teams associated with a project (primary first)."""
    query = select(Project).join(Team, Project.team_id == Team.id).where(Project.id == project_id)
    query = apply_company_filter(query, Team.company_id, get_company_filter(current_user))
    project = (await db.execute(query)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        # Visibility rule: regular users can list project teams if they can
        # see the project via either primary or associated team membership.
        has_access = await check_project_visibility(db, project_id, current_user)
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    rows = await list_project_teams(
        project_id=project_id,
        company_id=get_company_filter(current_user),
        db=db,
    )
    return [ProjectTeamAssociationResponse(**row) for row in rows]


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

    # Any authenticated user can update projects in their company scope.
    is_admin = current_user.role in ["super_admin", "admin", "company_admin"]

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
    team_changed = project_data.team_id is not None and project_data.team_id != old_values["team_id"]

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

    if team_changed:
        existing_primary_assoc = await db.execute(
            select(ProjectTeam.id).where(
                ProjectTeam.project_id == project.id,
                ProjectTeam.team_id == project.team_id,
            )
        )
        if existing_primary_assoc.scalar_one_or_none() is None:
            db.add(
                ProjectTeam(
                    project_id=project.id,
                    team_id=project.team_id,
                    added_by_user_id=current_user.id,
                )
            )

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


@router.delete("/{project_id}", response_model=ProjectDeleteResponse)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Permanently delete a project and dependent rows in one transaction."""
    project = await _get_company_scoped_project(db=db, project_id=project_id, current_user=current_user)

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await delete_project_with_cascade(db=db, project=project, acting_user=current_user)
    return ProjectDeleteResponse(
        deleted_tasks=result.deleted_tasks,
        deleted_entries=result.deleted_entries,
    )


@router.get("/{project_id}/delete-preview", response_model=ProjectDeletePreviewResponse)
async def delete_project_preview(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return the counts that would be hard-deleted for a project."""
    project = await _get_company_scoped_project(db=db, project_id=project_id, current_user=current_user)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task_count = (
        await db.execute(select(func.count(Task.id)).where(Task.project_id == project.id))
    ).scalar() or 0
    entry_count = (
        await db.execute(select(func.count(TimeEntry.id)).where(TimeEntry.project_id == project.id))
    ).scalar() or 0
    return ProjectDeletePreviewResponse(tasks=task_count, entries=entry_count)


@router.patch("/{project_id}/archive", response_model=ProjectResponse)
async def set_project_archive_status(
    project_id: int,
    body: ProjectArchiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Archive or unarchive a project."""
    project = await _get_company_scoped_project(db=db, project_id=project_id, current_user=current_user)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    old_values = {"is_archived": project.is_archived}
    project.is_archived = body.is_archived

    await AuditLogger.log(
        db=db,
        action=AuditAction.UPDATE,
        resource_type="project",
        resource_id=project.id,
        user_id=current_user.id,
        user_email=current_user.email,
        old_values=old_values,
        new_values={"is_archived": project.is_archived},
        details=("Archived" if body.is_archived else "Unarchived") + f" project '{project.name}'",
    )

    await db.commit()
    await db.refresh(project)

    team_name = (await db.execute(select(Team.name).where(Team.id == project.team_id))).scalar()
    task_count = (
        await db.execute(select(func.count(Task.id)).where(Task.project_id == project.id))
    ).scalar() or 0
    is_admin = current_user.role in ["super_admin", "admin", "company_admin"]

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
        deadline=project.deadline if is_admin else None,
    )


@router.post("/{source_project_id}/merge", response_model=ProjectMergeResponse)
async def merge_project_endpoint(
    source_project_id: int,
    body: ProjectMergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Merge source project into target and archive source in a single transaction."""
    if source_project_id == body.target_project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source and target must be different")

    source_project = await _get_company_scoped_project(
        db=db,
        project_id=source_project_id,
        current_user=current_user,
    )
    if not source_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source project not found")

    target_project = await _get_company_scoped_project(
        db=db,
        project_id=body.target_project_id,
        current_user=current_user,
    )
    if not target_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target project not found")
    if target_project.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target project cannot be archived")

    result = await merge_projects(
        db=db,
        source_project=source_project,
        target_project=target_project,
        acting_user=current_user,
    )
    return ProjectMergeResponse(
        moved_tasks=result.moved_tasks,
        moved_entries=result.moved_entries,
        renamed_tasks=result.renamed_tasks,
        archived_source=result.archived_source,
    )


@router.post("/{source_project_id}/merge/preview", response_model=ProjectMergePreviewResponse)
async def merge_project_preview_endpoint(
    source_project_id: int,
    body: ProjectMergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Preview merge results without modifying data."""
    if source_project_id == body.target_project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source and target must be different")

    source_project = await _get_company_scoped_project(
        db=db,
        project_id=source_project_id,
        current_user=current_user,
    )
    if not source_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source project not found")

    target_project = await _get_company_scoped_project(
        db=db,
        project_id=body.target_project_id,
        current_user=current_user,
    )
    if not target_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target project not found")
    if target_project.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target project cannot be archived")

    preview = await get_merge_preview(
        db=db,
        source_project=source_project,
        target_project=target_project,
    )
    return ProjectMergePreviewResponse(
        tasks_to_move=preview.tasks_to_move,
        entries_to_move=preview.entries_to_move,
        task_name_conflicts=preview.task_name_conflicts,
        target_existing_tasks=preview.target_existing_tasks,
        source_will_be_archived=preview.source_will_be_archived,
    )


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

