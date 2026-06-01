"""
TASK-009: Admin endpoint to view all users' time entries
TASK-010: Admin reports for all workers
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    apply_company_filter,
    get_company_filter,
    get_company_timezone,
    require_admin,
)
from app.models import Project, Task, TeamMember, TimeEntry, User
from app.utils.timewindow import day_bounds, local_today, now_utc, range_bounds

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ws/metrics")
async def get_websocket_metrics(
    current_user: User = Depends(require_admin),
):
    """Operational visibility for the WebSocket connection manager.

    Counters are in-memory only (no Redis); the snapshot resets on app
    restart. ``heartbeat_timeouts_last_hour`` is a sliding 60-minute
    count derived from per-event timestamps recorded by the heartbeat
    watchdog. Admin-only.
    """
    from app.routers.websocket import manager

    by_company: dict[str, int] = {}
    unique_users: set[int] = set()
    total_connections = 0
    for user_id, sockets in manager.active_connections.items():
        count = len(sockets)
        if count == 0:
            continue
        unique_users.add(user_id)
        total_connections += count
        company_id = manager.user_companies.get(user_id)
        key = "null" if company_id is None else str(company_id)
        by_company[key] = by_company.get(key, 0) + count

    return {
        "active_connections": total_connections,
        "unique_users": len(unique_users),
        "by_company": by_company,
        "heartbeat_timeouts_last_hour": manager.heartbeat_timeouts_last_hour(),
    }


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


# B11: require_admin is now imported from app.dependencies (canonical).
# Previous inline definition removed to eliminate drift.


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
    current_user: User = Depends(require_admin),
    tz: str = Depends(get_company_timezone),
):
    """Get all time entries for admin (TASK-009) with multi-tenant filtering"""
    start_datetime, end_datetime = range_bounds(start_date, end_date, tz)

    # Get company filter for multi-tenant data isolation
    company_filter = get_company_filter(current_user)

    # Build query
    query = (
        select(
            TimeEntry,
            User.name.label("user_name"),
            Project.name.label("project_name"),
            Task.name.label("task_name")
        )
        .join(User, TimeEntry.user_id == User.id)
        .outerjoin(Project, TimeEntry.project_id == Project.id)
        .outerjoin(Task, TimeEntry.task_id == Task.id)
        .where(
            TimeEntry.start_time >= start_datetime,
            TimeEntry.start_time < end_datetime
        )
    )

    # Apply company filter for multi-tenant isolation
    query = apply_company_filter(query, User.company_id, company_filter)

    # Apply filters
    if user_id:
        query = query.where(TimeEntry.user_id == user_id)

    if team_id:
        team_users = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
        query = query.where(TimeEntry.user_id.in_(team_users))

    if project_id:
        query = query.where(TimeEntry.project_id == project_id)

    # Get total count - also needs company filtering
    count_query = (
        select(func.count(TimeEntry.id), func.coalesce(func.sum(TimeEntry.duration_seconds), 0))
        .join(User, TimeEntry.user_id == User.id)
        .where(
            TimeEntry.start_time >= start_datetime,
            TimeEntry.start_time < end_datetime
        )
    )
    count_query = apply_company_filter(count_query, User.company_id, company_filter)
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
    current_user: User = Depends(require_admin),
    tz: str = Depends(get_company_timezone),
):
    """Get report for all workers (TASK-010) with multi-tenant filtering"""
    # Default to current local month
    today_local = local_today(tz)
    if not start_date:
        start_date = today_local.replace(day=1)
    if not end_date:
        end_date = today_local

    start_datetime, end_datetime = range_bounds(start_date, end_date, tz)
    days_in_period = (end_date - start_date).days + 1

    # Get company filter for multi-tenant data isolation
    company_filter = get_company_filter(current_user)

    # Base user filter with company filtering
    user_query = select(User).where(User.is_active == True)
    user_query = apply_company_filter(user_query, User.company_id, company_filter)

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
                TimeEntry.start_time < end_datetime
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
    current_user: User = Depends(require_admin),
    tz: str = Depends(get_company_timezone),
):
    """Get activity alerts for admin (TASK-022) with multi-tenant filtering"""
    now = now_utc()
    # Today's local civil day, expressed as a UTC interval [start, end)
    today_start, _today_end = day_bounds(local_today(tz), tz)

    # Get company filter for multi-tenant data isolation
    company_filter = get_company_filter(current_user)

    alerts = []

    # Alert: Long running timers (> 8 hours) - WITH COMPANY FILTERING
    long_timers_query = (
        select(TimeEntry, User.name)
        .join(User, TimeEntry.user_id == User.id)
        .where(
            TimeEntry.is_running == True,
            TimeEntry.start_time <= now - timedelta(hours=8)
        )
    )
    # Apply company filter
    long_timers_query = apply_company_filter(long_timers_query, User.company_id, company_filter)
    long_timers_result = await db.execute(long_timers_query)
    for row in long_timers_result.all():
        entry, user_name = row
        start = entry.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        hours = (now - start).total_seconds() / 3600
        alerts.append({
            "type": "long_timer",
            "severity": "warning",
            "message": f"{user_name} has been tracking time for {hours:.1f} hours",
            "user_name": user_name,
            "entry_id": entry.id,
            "start_time": entry.start_time.isoformat(),
            "hours": round(hours, 1)
        })

    # Alert: Users with no activity today (active users only) - WITH COMPANY FILTERING
    active_users_query = select(User.id, User.name).where(User.is_active == True)
    active_users_query = apply_company_filter(active_users_query, User.company_id, company_filter)
    active_users_result = await db.execute(active_users_query)
    active_users = active_users_result.all()

    # Get users active today - filter by company through User join
    active_today_query = (
        select(func.distinct(TimeEntry.user_id))
        .join(User, TimeEntry.user_id == User.id)
        .where(TimeEntry.start_time >= today_start)
    )
    active_today_query = apply_company_filter(active_today_query, User.company_id, company_filter)
    active_today_result = await db.execute(active_today_query)
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
                last = last_entry
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                days_ago = (now - last).days
                if days_ago > 1:
                    alerts.append({
                        "type": "no_activity",
                        "severity": "info",
                        "message": f"{user_name} hasn't tracked time in {days_ago} days",
                        "user_name": user_name,
                        "last_activity": last_entry.isoformat(),
                        "days_inactive": days_ago
                    })

    # Alert: Currently running timers - WITH COMPANY FILTERING
    running_timers_query = (
        select(TimeEntry, User.name, Project.name)
        .join(User, TimeEntry.user_id == User.id)
        .outerjoin(Project, TimeEntry.project_id == Project.id)
        .where(TimeEntry.is_running == True)
    )
    running_timers_query = apply_company_filter(running_timers_query, User.company_id, company_filter)
    running_timers_result = await db.execute(running_timers_query)
    running_count = 0
    for row in running_timers_result.all():
        entry, user_name, project_name = row
        project_name = project_name or "Meeting"  # Handle meeting entries
        running_count += 1
        start = entry.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        hours = (now - start).total_seconds() / 3600
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

