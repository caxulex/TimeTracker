"""
Tasks management router
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import apply_company_filter, get_company_filter, get_current_active_user
from app.models import BasecampTaskMapping, Project, Task, TaskTeam, Team, User
from app.routers.websocket import manager as ws_manager
from app.schemas.auth import Message
from app.services.audit_logger import AuditAction, AuditLogger
from app.services.project_team_service import build_project_visibility_filter
from app.services.task_service import apply_teams_to_task, get_task_teams_map

router = APIRouter()


class TaskTeamResponse(BaseModel):
    id: int
    name: str
    color: str


class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    project_id: int
    status: str = Field(default="TODO", pattern="^(TODO|IN_PROGRESS|DONE)$")
    team_ids: Optional[list[int]] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(TODO|IN_PROGRESS|DONE)$")
    project_id: Optional[int] = None
    team_ids: Optional[list[int]] = None


class TaskResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    project_id: int
    project_name: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    basecamp_due_on: Optional[date] = None
    basecamp_todo_created_at: Optional[datetime] = None
    basecamp_todo_position: Optional[int] = None
    teams: list[TaskTeamResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PaginatedTasks(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int
    pages: int


async def check_project_access(db: AsyncSession, project_id: int, user: User) -> bool:
    """Return True if user has visibility into project_id."""
    query = select(Project).join(Team, Project.team_id == Team.id).where(Project.id == project_id)
    query = apply_company_filter(query, Team.company_id, get_company_filter(user))

    result = await db.execute(query)
    project = result.scalar_one_or_none()
    if not project:
        return False

    if user.role in ["super_admin", "admin", "company_admin"]:
        return True

    visibility_result = await db.execute(
        select(Project.id).where(
            Project.id == project_id,
            build_project_visibility_filter(user.id),
        )
    )
    return visibility_result.scalar_one_or_none() is not None


@router.get("", response_model=PaginatedTasks)
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[int] = None,
    status: Optional[str] = Query(None, pattern="^(TODO|IN_PROGRESS|DONE)$"),
    search: Optional[str] = None,
    team_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List tasks."""
    base_query = (
        select(
            Task,
            BasecampTaskMapping.basecamp_due_on,
            BasecampTaskMapping.basecamp_todo_created_at,
            BasecampTaskMapping.basecamp_todo_position,
        )
        .outerjoin(BasecampTaskMapping, BasecampTaskMapping.task_id == Task.id)
        .join(Project, Project.id == Task.project_id)
        .join(Team, Team.id == Project.team_id)
    )
    count_query = (
        select(func.count(Task.id))
        .join(Project, Project.id == Task.project_id)
        .join(Team, Team.id == Project.team_id)
    )

    company_id = get_company_filter(current_user)
    base_query = apply_company_filter(base_query, Team.company_id, company_id)
    count_query = apply_company_filter(count_query, Team.company_id, company_id)

    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        user_projects = select(Project.id).where(build_project_visibility_filter(current_user.id))
        base_query = base_query.where(Task.project_id.in_(user_projects))
        count_query = count_query.where(Task.project_id.in_(user_projects))

    if project_id:
        base_query = base_query.where(Task.project_id == project_id)
        count_query = count_query.where(Task.project_id == project_id)

    if status:
        base_query = base_query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)

    if search:
        search_filter = f"%{search}%"
        base_query = base_query.where(Task.name.ilike(search_filter))
        count_query = count_query.where(Task.name.ilike(search_filter))

    parsed_team_ids: list[int] = []
    if team_ids:
        try:
            parsed_team_ids = sorted({int(raw.strip()) for raw in team_ids.split(",") if raw.strip()})
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="team_ids must be a comma-separated list of integers",
            ) from exc

    if parsed_team_ids:
        matching_task_ids = select(TaskTeam.task_id).where(TaskTeam.team_id.in_(parsed_team_ids))
        base_query = base_query.where(Task.id.in_(matching_task_ids))
        count_query = count_query.where(Task.id.in_(matching_task_ids))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(base_query.order_by(Task.created_at.desc()).offset(offset).limit(page_size))
    ).all()

    project_ids = list({row[0].project_id for row in rows})
    project_names: dict[int, str] = {}
    if project_ids:
        project_names = dict(
            (await db.execute(select(Project.id, Project.name).where(Project.id.in_(project_ids)))).all()
        )

    task_ids = [row[0].id for row in rows]
    teams_map = await get_task_teams_map(db, task_ids)

    items: list[TaskResponse] = []
    for task, bc_due_on, bc_created_at, bc_position in rows:
        items.append(
            TaskResponse(
                id=task.id,
                name=task.name,
                description=task.description,
                project_id=task.project_id,
                project_name=project_names.get(task.project_id),
                status=task.status,
                created_at=task.created_at,
                updated_at=task.updated_at,
                basecamp_due_on=bc_due_on,
                basecamp_todo_created_at=bc_created_at,
                basecamp_todo_position=bc_position,
                teams=[TaskTeamResponse(**item) for item in teams_map.get(task.id, [])],
            )
        )

    return PaginatedTasks(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 1,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get task details."""
    row = (
        await db.execute(
            select(
                Task,
                BasecampTaskMapping.basecamp_due_on,
                BasecampTaskMapping.basecamp_todo_created_at,
                BasecampTaskMapping.basecamp_todo_position,
            )
            .outerjoin(BasecampTaskMapping, BasecampTaskMapping.task_id == Task.id)
            .where(Task.id == task_id)
        )
    ).one_or_none()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task, bc_due_on, bc_created_at, bc_position = row

    if not await check_project_access(db, task.project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    project_name = (await db.execute(select(Project.name).where(Project.id == task.project_id))).scalar()
    teams = (await get_task_teams_map(db, [task.id])).get(task.id, [])

    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        project_id=task.project_id,
        project_name=project_name,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        basecamp_due_on=bc_due_on,
        basecamp_todo_created_at=bc_created_at,
        basecamp_todo_position=bc_position,
        teams=[TaskTeamResponse(**item) for item in teams],
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new task."""
    if not await check_project_access(db, task_data.project_id, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or access denied")

    project = (await db.execute(select(Project).where(Project.id == task_data.project_id))).scalar_one()

    task = Task(
        name=task_data.name,
        description=task_data.description,
        project_id=task_data.project_id,
        status=task_data.status,
    )
    db.add(task)
    await db.flush()

    if task_data.team_ids is not None:
        try:
            added_team_ids, removed_team_ids = await apply_teams_to_task(db, task.id, task_data.team_ids, current_user.id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        if added_team_ids or removed_team_ids:
            await AuditLogger.log(
                db=db,
                action=AuditAction.UPDATE,
                resource_type="task",
                resource_id=task.id,
                user_id=current_user.id,
                user_email=current_user.email,
                old_values={"team_ids": removed_team_ids},
                new_values={"team_ids": added_team_ids},
                details=f"Updated task-team assignments for task '{task.name}'",
            )

    await db.commit()
    await db.refresh(task)

    await ws_manager.broadcast_to_team(
        {
            "type": "task_created",
            "data": {
                "task_id": task.id,
                "task_name": task.name,
                "project_id": project.id,
                "project_name": project.name,
                "status": task.status,
                "created_by": current_user.name,
            },
        },
        project.team_id,
    )

    teams = (await get_task_teams_map(db, [task.id])).get(task.id, [])
    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        project_id=task.project_id,
        project_name=project.name,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        teams=[TaskTeamResponse(**item) for item in teams],
    )


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a task."""
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not await check_project_access(db, task.project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if task_data.project_id is not None and task_data.project_id != task.project_id:
        if not await check_project_access(db, task_data.project_id, current_user):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project_id or access denied")

    if task_data.name is not None:
        task.name = task_data.name
    if task_data.description is not None:
        task.description = task_data.description
    if task_data.status is not None:
        task.status = task_data.status
    if task_data.project_id is not None:
        task.project_id = task_data.project_id

    if task_data.team_ids is not None:
        try:
            added_team_ids, removed_team_ids = await apply_teams_to_task(db, task.id, task_data.team_ids, current_user.id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        if added_team_ids or removed_team_ids:
            await AuditLogger.log(
                db=db,
                action=AuditAction.UPDATE,
                resource_type="task",
                resource_id=task.id,
                user_id=current_user.id,
                user_email=current_user.email,
                old_values={"removed_team_ids": removed_team_ids},
                new_values={"added_team_ids": added_team_ids},
                details=f"Updated task-team assignments for task '{task.name}'",
            )

    await db.commit()
    await db.refresh(task)

    project_name = (await db.execute(select(Project.name).where(Project.id == task.project_id))).scalar()
    teams = (await get_task_teams_map(db, [task.id])).get(task.id, [])

    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        project_id=task.project_id,
        project_name=project_name,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        teams=[TaskTeamResponse(**item) for item in teams],
    )


@router.delete("/{task_id}", response_model=Message)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a task."""
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not await check_project_access(db, task.project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    await db.delete(task)
    await db.commit()

    return Message(message="Task deleted successfully")
