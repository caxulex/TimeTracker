"""
TASK-009: Admin endpoint to view all users' time entries
TASK-010: Admin reports for all workers
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from datetime import datetime, date, timedelta

from app.database import get_db
from app.models import User, Team, TeamMember, Project, Task, TimeEntry
from app.dependencies import get_current_active_user

router = APIRouter(prefix="/admin", tags=["admin"])


class TimeEntryWithUser(BaseModel):
    id: int
    user_id: int
    user_name: str
    project_id: int
    project_name: str
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int

    class Config:
        from_attributes = True


class AdminTimeEntriesResponse(BaseModel):
    entries: List[TimeEntryWithUser]
    total: int
    total_seconds: int


class WorkerReport(BaseModel):
    user_id: int
    user_name: str
    email: str
    total_seconds: int
    total_hours: float
    entry_count: int
    projects_worked: int
    avg_daily_hours: float
    last_activity: Optional[datetime] = None


class AdminWorkersReportResponse(BaseModel):
    workers: List[WorkerReport]
    total_workers: int
    total_seconds: int
    total_hours: float
    period_start: date
    period_end: date


def require_admin(current_user: User = Depends(get_current_active_user)):
    """Dependency to require admin role"""
    if current_user.role not in ["super_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("/time-entries", response_model=AdminTimeEntriesResponse)
async def get_admin_time_entries(
    start_date: date,
    end_date: date,
    user_id: Optional[int] = None,
    team_id: Optional[int] = None,
    project_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get all time entries for admin (TASK-009)"""
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Build query
    query = (
        select(
            TimeEntry,
            User.name.label("user_name"),
            Project.name.label("project_name"),
            Task.name.label("task_name")
        )
        .join(User, TimeEntry.user_id == User.id)
        .join(Project, TimeEntry.project_id == Project.id)
        .outerjoin(Task, TimeEntry.task_id == Task.id)
        .where(
            TimeEntry.start_time >= start_datetime,
            TimeEntry.start_time <= end_datetime
        )
    )

    # Apply filters
    if user_id:
        query = query.where(TimeEntry.user_id == user_id)

    if team_id:
        team_users = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
        query = query.where(TimeEntry.user_id.in_(team_users))

    if project_id:
        query = query.where(TimeEntry.project_id == project_id)

    # Get total count
    count_query = (
        select(func.count(TimeEntry.id), func.coalesce(func.sum(TimeEntry.duration_seconds), 0))
        .where(
            TimeEntry.start_time >= start_datetime,
            TimeEntry.start_time <= end_datetime
        )
    )
    if user_id:
        count_query = count_query.where(TimeEntry.user_id == user_id)
    if team_id:
        team_users = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
        count_query = count_query.where(TimeEntry.user_id.in_(team_users))
    if project_id:
        count_query = count_query.where(TimeEntry.project_id == project_id)

    count_result = await db.execute(count_query)
    count_row = count_result.first()
    total = count_row[0] or 0
    total_seconds = count_row[1] or 0

    # Paginate and order
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(TimeEntry.start_time.desc())

    result = await db.execute(query)
    rows = result.all()

    entries = []
    for row in rows:
        entry = row[0]
        entries.append(TimeEntryWithUser(
            id=entry.id,
            user_id=entry.user_id,
            user_name=row.user_name,
            project_id=entry.project_id,
            project_name=row.project_name,
            task_id=entry.task_id,
            task_name=row.task_name,
            description=entry.description,
            start_time=entry.start_time,
            end_time=entry.end_time,
            duration_seconds=entry.duration_seconds or 0
        ))

    return AdminTimeEntriesResponse(
        entries=entries,
        total=total,
        total_seconds=total_seconds
    )


@router.get("/workers-report", response_model=AdminWorkersReportResponse)
async def get_workers_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    team_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get report for all workers (TASK-010)"""
    # Default to current month
    if not start_date:
        now = datetime.now()
        start_date = now.replace(day=1).date()
    if not end_date:
        end_date = datetime.now().date()

    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    days_in_period = (end_date - start_date).days + 1

    # Base user filter
    user_query = select(User).where(User.is_active == True)
    
    if team_id:
        team_users = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
        user_query = user_query.where(User.id.in_(team_users))

    users_result = await db.execute(user_query)
    users = users_result.scalars().all()

    workers = []
    total_seconds = 0

    for user in users:
        # Get time entries for this user
        entries_query = (
            select(
                func.coalesce(func.sum(TimeEntry.duration_seconds), 0).label("total_seconds"),
                func.count(TimeEntry.id).label("entry_count"),
                func.count(func.distinct(TimeEntry.project_id)).label("projects_worked"),
                func.max(TimeEntry.start_time).label("last_activity")
            )
            .where(
                TimeEntry.user_id == user.id,
                TimeEntry.start_time >= start_datetime,
                TimeEntry.start_time <= end_datetime
            )
        )

        result = await db.execute(entries_query)
        row = result.first()

        user_seconds = row.total_seconds or 0
        total_seconds += user_seconds
        
        workers.append(WorkerReport(
            user_id=user.id,
            user_name=user.name,
            email=user.email,
            total_seconds=user_seconds,
            total_hours=round(user_seconds / 3600, 2),
            entry_count=row.entry_count or 0,
            projects_worked=row.projects_worked or 0,
            avg_daily_hours=round(user_seconds / 3600 / days_in_period, 2) if days_in_period > 0 else 0,
            last_activity=row.last_activity
        ))

    # Sort by total time descending
    workers.sort(key=lambda w: w.total_seconds, reverse=True)

    return AdminWorkersReportResponse(
        workers=workers,
        total_workers=len(workers),
        total_seconds=total_seconds,
        total_hours=round(total_seconds / 3600, 2),
        period_start=start_date,
        period_end=end_date
    )


@router.get("/activity-alerts")
async def get_activity_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get activity alerts for admin (TASK-022)"""
    now = datetime.now()
    today_start = datetime.combine(now.date(), datetime.min.time())
    
    alerts = []

    # Alert: Long running timers (> 8 hours)
    long_timers_result = await db.execute(
        select(TimeEntry, User.name)
        .join(User, TimeEntry.user_id == User.id)
        .where(
            TimeEntry.end_time == None,
            TimeEntry.start_time <= now - timedelta(hours=8)
        )
    )
    for row in long_timers_result.all():
        entry, user_name = row
        hours = (now - entry.start_time).total_seconds() / 3600
        alerts.append({
            "type": "long_timer",
            "severity": "warning",
            "message": f"{user_name} has been tracking time for {hours:.1f} hours",
            "user_name": user_name,
            "entry_id": entry.id,
            "start_time": entry.start_time.isoformat(),
            "hours": round(hours, 1)
        })

    # Alert: Users with no activity today (active users only)
    active_users_result = await db.execute(
        select(User.id, User.name)
        .where(User.is_active == True)
    )
    active_users = active_users_result.all()
    
    active_today_result = await db.execute(
        select(func.distinct(TimeEntry.user_id))
        .where(TimeEntry.start_time >= today_start)
    )
    active_today_ids = {r[0] for r in active_today_result.all()}

    for user_id, user_name in active_users:
        if user_id not in active_today_ids:
            # Check when they last tracked time
            last_entry_result = await db.execute(
                select(func.max(TimeEntry.start_time))
                .where(TimeEntry.user_id == user_id)
            )
            last_entry = last_entry_result.scalar()
            
            if last_entry:
                days_ago = (now - last_entry).days
                if days_ago > 1:
                    alerts.append({
                        "type": "no_activity",
                        "severity": "info",
                        "message": f"{user_name} hasn't tracked time in {days_ago} days",
                        "user_name": user_name,
                        "last_activity": last_entry.isoformat(),
                        "days_inactive": days_ago
                    })

    # Alert: Currently running timers
    running_timers_result = await db.execute(
        select(TimeEntry, User.name, Project.name)
        .join(User, TimeEntry.user_id == User.id)
        .join(Project, TimeEntry.project_id == Project.id)
        .where(TimeEntry.end_time == None)
    )
    running_count = 0
    for row in running_timers_result.all():
        entry, user_name, project_name = row
        running_count += 1
        hours = (now - entry.start_time).total_seconds() / 3600
        if hours < 8:  # Don't duplicate long timer alerts
            alerts.append({
                "type": "active_timer",
                "severity": "success",
                "message": f"{user_name} is working on {project_name}",
                "user_name": user_name,
                "project_name": project_name,
                "entry_id": entry.id,
                "start_time": entry.start_time.isoformat(),
                "hours": round(hours, 2)
            })

    return {
        "alerts": alerts,
        "summary": {
            "total_alerts": len(alerts),
            "running_timers": running_count,
            "long_timers": len([a for a in alerts if a["type"] == "long_timer"]),
            "inactive_users": len([a for a in alerts if a["type"] == "no_activity"])
        }
    }
