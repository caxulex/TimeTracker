"""
Tasks management router
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.models import User, Project, Task, TeamMember
from app.dependencies import get_current_active_user
from app.schemas.auth import Message
from app.routers.websocket import manager as ws_manager

router = APIRouter()


class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    project_id: int
    status: str = Field(default="TODO", pattern="^(TODO|IN_PROGRESS|DONE)$")


class TaskUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(TODO|IN_PROGRESS|DONE)$")


class TaskResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    project_id: int
    project_name: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaginatedTasks(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int
    pages: int


async def check_project_access(db: AsyncSession, project_id: int, user: User) -> bool:
    """Check if user has access to project"""
    if user.role in ["super_admin", "admin"]:
        return True
    
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        return False
    
    member_result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == project.team_id,
            TeamMember.user_id == user.id
        )
    )
    return member_result.scalar_one_or_none() is not None


@router.get("", response_model=PaginatedTasks)
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[int] = None,
    status: Optional[str] = Query(None, pattern="^(TODO|IN_PROGRESS|DONE)$"),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List tasks"""
    base_query = select(Task)
    count_query = select(func.count(Task.id))
    
    # Filter by accessible projects
    if current_user.role != "super_admin":
        user_teams = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
        user_projects = select(Project.id).where(Project.team_id.in_(user_teams))
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
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * page_size
    query = base_query.offset(offset).limit(page_size).order_by(Task.created_at.desc())
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # Get project names
    project_ids = list(set(t.project_id for t in tasks))
    project_names = {}
    if project_ids:
        projects_result = await db.execute(select(Project.id, Project.name).where(Project.id.in_(project_ids)))
        project_names = dict(projects_result.all())
    
    items = []
    for task in tasks:
        items.append(TaskResponse(
            id=task.id,
            name=task.name,
            description=task.description,
            project_id=task.project_id,
            project_name=project_names.get(task.project_id),
            status=task.status,
            created_at=task.created_at,
            updated_at=task.updated_at
        ))
    
    return PaginatedTasks(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 1
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get task details"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    # Check access
    has_access = await check_project_access(db, task.project_id, current_user)
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Get project name
    project_result = await db.execute(select(Project.name).where(Project.id == task.project_id))
    project_name = project_result.scalar()
    
    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        project_id=task.project_id,
        project_name=project_name,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new task"""
    # Check project access
    has_access = await check_project_access(db, task_data.project_id, current_user)
    if not has_access:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or access denied")
    
    # Get project name and team_id for notifications
    project_result = await db.execute(select(Project).where(Project.id == task_data.project_id))
    project = project_result.scalar()
    
    task = Task(
        name=task_data.name,
        description=task_data.description,
        project_id=task_data.project_id,
        status=task_data.status
    )
    
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    # Notify all team members about new task
    await ws_manager.broadcast_to_team(
        {
            "type": "task_created",
            "data": {
                "task_id": task.id,
                "task_name": task.name,
                "project_id": project.id,
                "project_name": project.name,
                "status": task.status,
                "created_by": current_user.name
            }
        },
        project.team_id
    )
    
    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        project_id=task.project_id,
        project_name=project.name,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a task"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    # Check access
    has_access = await check_project_access(db, task.project_id, current_user)
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Update fields
    if task_data.name is not None:
        task.name = task_data.name
    if task_data.description is not None:
        task.description = task_data.description
    if task_data.status is not None:
        task.status = task_data.status
    
    await db.commit()
    await db.refresh(task)
    
    # Get project name
    project_result = await db.execute(select(Project.name).where(Project.id == task.project_id))
    project_name = project_result.scalar()
    
    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        project_id=task.project_id,
        project_name=project_name,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@router.delete("/{task_id}", response_model=Message)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a task"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    # Check access
    has_access = await check_project_access(db, task.project_id, current_user)
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    await db.delete(task)
    await db.commit()
    
    return Message(message="Task deleted successfully")
