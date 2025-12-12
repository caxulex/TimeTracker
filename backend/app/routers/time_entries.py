"""
Time entries management router - Core time tracking functionality
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date, timedelta, timezone

from app.database import get_db
from app.models import User, Team, TeamMember, Project, Task, TimeEntry
from app.dependencies import get_current_active_user
from app.schemas.auth import Message
from app.routers.websocket import manager as ws_manager

router = APIRouter()


class TimeEntryCreate(BaseModel):
    task_id: Optional[int] = None
    project_id: int
    description: Optional[str] = None
    start_time: Optional[datetime] = None  # None means start now (timer)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None  # For manual entry

    @field_validator('duration_seconds')
    @classmethod
    def validate_duration(cls, v):
        if v is not None and v < 60:
            raise ValueError('Duration must be at least 60 seconds')
        return v


class TimeEntryUpdate(BaseModel):
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class TimeEntryResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    task_id: Optional[int]
    task_name: Optional[str] = None
    project_id: int
    project_name: Optional[str] = None
    description: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[int]
    duration_minutes: Optional[int] = None  # Computed field for convenience
    is_running: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedTimeEntries(BaseModel):
    items: List[TimeEntryResponse]
    total: int
    page: int
    page_size: int
    pages: int
    total_seconds: int = 0
    total_hours: float = 0.0


class TimerStatus(BaseModel):
    is_running: bool
    current_entry: Optional[TimeEntryResponse] = None
    elapsed_seconds: Optional[int] = None


async def check_project_access(db: AsyncSession, project_id: int, user: User) -> Optional[Project]:
    """Check if user has access to project and return it"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        return None

    if user.role in ["super_admin", "admin"]:
        return project

    # Check team membership for project access
    if project.team_id:
        member_check = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == project.team_id,
                TeamMember.user_id == user.id
            )
        )
        if member_check.scalar_one_or_none():
            return project

    return None
def calculate_duration_seconds(start: datetime, end: datetime) -> int:
    """Calculate duration in seconds"""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    delta = end - start
    return max(60, int(delta.total_seconds()))


def make_entry_response(entry: TimeEntry, project_name: str = None, task_name: str = None, user_name: str = None) -> TimeEntryResponse:
    """Helper to create TimeEntryResponse"""
    duration_seconds = entry.duration_seconds
    duration_minutes = int(duration_seconds / 60) if duration_seconds else None
    
    return TimeEntryResponse(
        id=entry.id,
        user_id=entry.user_id,
        user_name=user_name,
        task_id=entry.task_id,
        task_name=task_name,
        project_id=entry.project_id,
        project_name=project_name,
        description=entry.description,
        start_time=entry.start_time,
        end_time=entry.end_time,
        duration_seconds=duration_seconds,
        duration_minutes=duration_minutes,
        is_running=entry.end_time is None,
        created_at=entry.created_at
    )


@router.get("/timer", response_model=TimerStatus)
async def get_timer_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get current running timer status"""
    result = await db.execute(
        select(TimeEntry)
        .where(TimeEntry.user_id == current_user.id, TimeEntry.end_time == None)
        .order_by(TimeEntry.start_time.desc())
    )
    running_entry = result.scalar_one_or_none()
    
    if not running_entry:
        return TimerStatus(is_running=False)
    
    # Get project name
    project_result = await db.execute(select(Project.name).where(Project.id == running_entry.project_id))
    project_name = project_result.scalar()
    
    # Get task name if applicable
    task_name = None
    if running_entry.task_id:
        task_result = await db.execute(select(Task.name).where(Task.id == running_entry.task_id))
        task_name = task_result.scalar()
    
    # Calculate elapsed time
    now = datetime.now(timezone.utc)
    start = running_entry.start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    elapsed = int((now - start).total_seconds())
    
    return TimerStatus(
        is_running=True,
        current_entry=make_entry_response(running_entry, project_name, task_name, current_user.name),
        elapsed_seconds=elapsed
    )


@router.get("/active", response_model=list[dict])
async def get_active_timers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all currently active timers (for admin/team view)"""
    # Query all active time entries with user, project, and task info
    result = await db.execute(
        select(TimeEntry, User, Project, Task)
        .join(User, TimeEntry.user_id == User.id)
        .join(Project, TimeEntry.project_id == Project.id)
        .outerjoin(Task, TimeEntry.task_id == Task.id)
        .where(TimeEntry.end_time == None)
        .order_by(TimeEntry.start_time.desc())
    )
    
    rows = result.all()
    active_timers = []
    
    for entry, user, project, task in rows:
        # Calculate elapsed seconds
        start = entry.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        elapsed = int((now - start).total_seconds())
        
        active_timers.append({
            "user_id": user.id,
            "user_name": user.name,
            "project_id": project.id,
            "project_name": project.name,
            "task_id": task.id if task else None,
            "task_name": task.name if task else None,
            "description": entry.description,
            "start_time": entry.start_time.isoformat(),
            "elapsed_seconds": elapsed
        })
    
    return active_timers


@router.post("/start", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED)
async def start_timer(
    entry_data: TimeEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Start a new timer"""
    # Check for existing running timer
    existing = await db.execute(
        select(TimeEntry).where(TimeEntry.user_id == current_user.id, TimeEntry.end_time == None)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timer already running. Stop it first."
        )
    
    # Check project access
    project = await check_project_access(db, entry_data.project_id, current_user)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or access denied")
    
    # Verify task if provided
    task_name = None
    if entry_data.task_id:
        task_result = await db.execute(
            select(Task).where(Task.id == entry_data.task_id, Task.project_id == entry_data.project_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task not found in this project")
        task_name = task.name
    
    entry = TimeEntry(
        user_id=current_user.id,
        task_id=entry_data.task_id,
        project_id=entry_data.project_id,
        description=entry_data.description,
        start_time=datetime.now(timezone.utc),
        end_time=None,
        duration_seconds=None,
        is_running=True
    )
    
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    
    return make_entry_response(entry, project.name, task_name, current_user.name)


@router.post("/stop", response_model=TimeEntryResponse)
async def stop_timer(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Stop the running timer"""
    result = await db.execute(
        select(TimeEntry).where(TimeEntry.user_id == current_user.id, TimeEntry.end_time == None)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No running timer found")
    
    # Stop the timer
    end_time = datetime.now(timezone.utc)
    entry.end_time = end_time
    entry.duration_seconds = calculate_duration_seconds(entry.start_time, end_time)
    entry.is_running = False
    
    await db.commit()
    await db.refresh(entry)
    
    # Get names
    project_result = await db.execute(select(Project.name).where(Project.id == entry.project_id))
    project_name = project_result.scalar()
    
    task_name = None
    if entry.task_id:
        task_result = await db.execute(select(Task.name).where(Task.id == entry.task_id))
        task_name = task_result.scalar()
    
    # Broadcast time entry completion to all users for real-time reports update
    await ws_manager.broadcast_to_all({
        "type": "time_entry_completed",
        "data": {
            "entry_id": entry.id,
            "user_id": current_user.id,
            "user_name": current_user.name,
            "project_id": entry.project_id,
            "project_name": project_name,
            "task_id": entry.task_id,
            "task_name": task_name,
            "description": entry.description,
            "start_time": entry.start_time.isoformat(),
            "end_time": entry.end_time.isoformat(),
            "duration_seconds": entry.duration_seconds,
            "is_running": False
        }
    })
    
    return make_entry_response(entry, project_name, task_name, current_user.name)


@router.post("", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_entry(
    entry_data: TimeEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a manual time entry"""
    # Check project access
    project = await check_project_access(db, entry_data.project_id, current_user)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or access denied")
    
    # Verify task if provided
    task_name = None
    if entry_data.task_id:
        task_result = await db.execute(
            select(Task).where(Task.id == entry_data.task_id, Task.project_id == entry_data.project_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task not found in this project")
        task_name = task.name
    
    # Determine start/end/duration
    now = datetime.now(timezone.utc)
    
    if entry_data.duration_seconds:
        # Manual entry with duration
        start_time = entry_data.start_time or now
        end_time = start_time + timedelta(seconds=entry_data.duration_seconds)
        duration = entry_data.duration_seconds
    elif entry_data.start_time and entry_data.end_time:
        # Manual entry with start and end
        start_time = entry_data.start_time
        end_time = entry_data.end_time
        duration = calculate_duration_seconds(start_time, end_time)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either duration_seconds or both start_time and end_time"
        )
    
    entry = TimeEntry(
        user_id=current_user.id,
        task_id=entry_data.task_id,
        project_id=entry_data.project_id,
        description=entry_data.description,
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration,
        is_running=False
    )
    
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    
    # Broadcast manual time entry creation to all users for real-time reports update
    await ws_manager.broadcast_to_all({
        "type": "time_entry_created",
        "data": {
            "entry_id": entry.id,
            "user_id": current_user.id,
            "user_name": current_user.name,
            "project_id": entry.project_id,
            "project_name": project.name,
            "task_id": entry.task_id,
            "task_name": task_name,
            "description": entry.description,
            "start_time": entry.start_time.isoformat(),
            "end_time": entry.end_time.isoformat(),
            "duration_seconds": entry.duration_seconds,
            "is_running": False
        }
    })
    
    return make_entry_response(entry, project.name, task_name, current_user.name)


@router.get("", response_model=PaginatedTimeEntries)
async def list_time_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[int] = None,
    task_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List time entries"""
    base_query = select(TimeEntry)
    count_query = select(func.count(TimeEntry.id))
    sum_query = select(func.coalesce(func.sum(TimeEntry.duration_seconds), 0))
    
    # Filter by user (regular users see only their entries, admin sees all)
    if current_user.role not in ["super_admin", "admin"]:
        if user_id and user_id != current_user.id:
            # Can only see team members' entries
            user_teams = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
            team_users = select(TeamMember.user_id).where(TeamMember.team_id.in_(user_teams))
            base_query = base_query.where(
                (TimeEntry.user_id == current_user.id) | (TimeEntry.user_id.in_(team_users))
            )
            count_query = count_query.where(
                (TimeEntry.user_id == current_user.id) | (TimeEntry.user_id.in_(team_users))
            )
            sum_query = sum_query.where(
                (TimeEntry.user_id == current_user.id) | (TimeEntry.user_id.in_(team_users))
            )
        elif not user_id:
            base_query = base_query.where(TimeEntry.user_id == current_user.id)
            count_query = count_query.where(TimeEntry.user_id == current_user.id)
            sum_query = sum_query.where(TimeEntry.user_id == current_user.id)
    
    if user_id:
        base_query = base_query.where(TimeEntry.user_id == user_id)
        count_query = count_query.where(TimeEntry.user_id == user_id)
        sum_query = sum_query.where(TimeEntry.user_id == user_id)
    
    if project_id:
        base_query = base_query.where(TimeEntry.project_id == project_id)
        count_query = count_query.where(TimeEntry.project_id == project_id)
        sum_query = sum_query.where(TimeEntry.project_id == project_id)
    
    if task_id:
        base_query = base_query.where(TimeEntry.task_id == task_id)
        count_query = count_query.where(TimeEntry.task_id == task_id)
        sum_query = sum_query.where(TimeEntry.task_id == task_id)
    
    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        base_query = base_query.where(TimeEntry.start_time >= start_datetime)
        count_query = count_query.where(TimeEntry.start_time >= start_datetime)
        sum_query = sum_query.where(TimeEntry.start_time >= start_datetime)
    
    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        base_query = base_query.where(TimeEntry.start_time <= end_datetime)
        count_query = count_query.where(TimeEntry.start_time <= end_datetime)
        sum_query = sum_query.where(TimeEntry.start_time <= end_datetime)
    
    # Get counts
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    sum_result = await db.execute(sum_query)
    total_seconds = sum_result.scalar() or 0
    
    # Get paginated results
    offset = (page - 1) * page_size
    query = base_query.offset(offset).limit(page_size).order_by(TimeEntry.start_time.desc())
    result = await db.execute(query)
    entries = result.scalars().all()
    
    # Get related names
    project_ids = list(set(e.project_id for e in entries))
    task_ids = list(set(e.task_id for e in entries if e.task_id))
    user_ids = list(set(e.user_id for e in entries))
    
    project_names = {}
    if project_ids:
        projects_result = await db.execute(select(Project.id, Project.name).where(Project.id.in_(project_ids)))
        project_names = dict(projects_result.all())
    
    task_names = {}
    if task_ids:
        tasks_result = await db.execute(select(Task.id, Task.name).where(Task.id.in_(task_ids)))
        task_names = dict(tasks_result.all())
    
    user_names = {}
    if user_ids:
        users_result = await db.execute(select(User.id, User.name).where(User.id.in_(user_ids)))
        user_names = dict(users_result.all())
    
    items = [
        make_entry_response(
            entry,
            project_names.get(entry.project_id),
            task_names.get(entry.task_id) if entry.task_id else None,
            user_names.get(entry.user_id)
        )
        for entry in entries
    ]
    
    return PaginatedTimeEntries(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 1,
        total_seconds=total_seconds,
        total_hours=round(total_seconds / 3600, 2)
    )


@router.get("/{entry_id}", response_model=TimeEntryResponse)
async def get_time_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get time entry details"""
    result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time entry not found")
    
    # Check access
    if current_user.role not in ["super_admin", "admin"] and entry.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Get names
    project_result = await db.execute(select(Project.name).where(Project.id == entry.project_id))
    project_name = project_result.scalar()
    
    task_name = None
    if entry.task_id:
        task_result = await db.execute(select(Task.name).where(Task.id == entry.task_id))
        task_name = task_result.scalar()
    
    user_result = await db.execute(select(User.name).where(User.id == entry.user_id))
    user_name = user_result.scalar()
    
    return make_entry_response(entry, project_name, task_name, user_name)


@router.put("/{entry_id}", response_model=TimeEntryResponse)
async def update_time_entry(
    entry_id: int,
    entry_data: TimeEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update time entry"""
    result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time entry not found")
    
    # Only owner can update
    if entry.user_id != current_user.id and current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only update your own entries")
    
    if entry_data.description is not None:
        entry.description = entry_data.description
    
    if entry_data.start_time is not None:
        entry.start_time = entry_data.start_time
    
    if entry_data.end_time is not None:
        entry.end_time = entry_data.end_time
    
    # Recalculate duration if times changed
    if entry.end_time:
        entry.duration_seconds = calculate_duration_seconds(entry.start_time, entry.end_time)
        entry.is_running = False
    
    await db.commit()
    await db.refresh(entry)
    
    # Get names
    project_result = await db.execute(select(Project.name).where(Project.id == entry.project_id))
    project_name = project_result.scalar()
    
    task_name = None
    if entry.task_id:
        task_result = await db.execute(select(Task.name).where(Task.id == entry.task_id))
        task_name = task_result.scalar()
    
    # Broadcast time entry update to all users for real-time reports update
    await ws_manager.broadcast_to_all({
        "type": "time_entry_updated",
        "data": {
            "entry_id": entry.id,
            "user_id": entry.user_id,
            "project_id": entry.project_id,
            "project_name": project_name,
            "task_id": entry.task_id,
            "task_name": task_name,
            "description": entry.description,
            "start_time": entry.start_time.isoformat(),
            "end_time": entry.end_time.isoformat() if entry.end_time else None,
            "duration_seconds": entry.duration_seconds,
            "is_running": entry.is_running
        }
    })
    
    return make_entry_response(entry, project_name, task_name, current_user.name)


@router.delete("/{entry_id}", response_model=Message)
async def delete_time_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete time entry"""
    result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time entry not found")
    
    # Only owner can delete
    if entry.user_id != current_user.id and current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only delete your own entries")
    
    # Store entry data before deletion for WebSocket broadcast
    entry_data = {
        "entry_id": entry.id,
        "user_id": entry.user_id,
        "project_id": entry.project_id,
        "task_id": entry.task_id
    }
    
    await db.delete(entry)
    await db.commit()
    
    # Broadcast time entry deletion to all users for real-time reports update
    await ws_manager.broadcast_to_all({
        "type": "time_entry_deleted",
        "data": entry_data
    })
    
    return {"message": "Time entry deleted successfully"}
