"""
Reports and analytics router
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

router = APIRouter()


class ProjectSummary(BaseModel):
    project_id: int
    project_name: str
    total_seconds: int
    total_hours: float
    entry_count: int
    billable_amount: Optional[float] = None
    budget_hours: Optional[float] = None
    budget_used_percent: Optional[float] = None


class UserSummary(BaseModel):
    user_id: int
    user_name: str
    total_seconds: int
    total_hours: float
    entry_count: int


class TaskSummary(BaseModel):
    task_id: int
    task_name: str
    project_name: str
    total_seconds: int
    total_hours: float
    status: str


class DailySummary(BaseModel):
    date: date
    total_seconds: int
    total_hours: float
    entry_count: int


class WeeklySummary(BaseModel):
    week_start: date
    week_end: date
    total_seconds: int
    total_hours: float
    daily_breakdown: List[DailySummary]


class DashboardStats(BaseModel):
    today_seconds: int
    today_hours: float
    week_seconds: int
    week_hours: float
    month_seconds: int
    month_hours: float
    active_projects: int
    pending_tasks: int
    running_timer: bool


class TimeReport(BaseModel):
    start_date: date
    end_date: date
    total_seconds: int
    total_hours: float
    total_entries: int
    by_project: List[ProjectSummary]
    by_user: List[UserSummary]
    by_day: List[DailySummary]


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get dashboard statistics for current user"""
    now = datetime.now()
    today_start = datetime.combine(now.date(), datetime.min.time())
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)
    
    # Base filter for user's entries
    user_filter = TimeEntry.user_id == current_user.id
    
    # Today's time
    today_result = await db.execute(
        select(func.coalesce(func.sum(TimeEntry.duration_seconds), 0))
        .where(user_filter, TimeEntry.start_time >= today_start)
    )
    today_seconds = today_result.scalar() or 0
    
    # This week's time
    week_result = await db.execute(
        select(func.coalesce(func.sum(TimeEntry.duration_seconds), 0))
        .where(user_filter, TimeEntry.start_time >= week_start)
    )
    week_seconds = week_result.scalar() or 0
    
    # This month's time
    month_result = await db.execute(
        select(func.coalesce(func.sum(TimeEntry.duration_seconds), 0))
        .where(user_filter, TimeEntry.start_time >= month_start)
    )
    month_seconds = month_result.scalar() or 0
    
    # Active projects (user has access to)
    user_teams = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
    project_filter = Project.team_id.in_(user_teams)
    active_projects_result = await db.execute(
        select(func.count(Project.id))
        .where(project_filter, Project.is_archived == False)
    )
    active_projects = active_projects_result.scalar() or 0
    
    # Pending tasks assigned to user
    pending_tasks = 0  # Simplified for now
    
    # Check for running timer
    running_result = await db.execute(
        select(TimeEntry.id).where(user_filter, TimeEntry.end_time == None)
    )
    running_timer = running_result.scalar_one_or_none() is not None
    
    return DashboardStats(
        today_seconds=today_seconds,
        today_hours=round(today_seconds / 3600, 2),
        week_seconds=week_seconds,
        week_hours=round(week_seconds / 3600, 2),
        month_seconds=month_seconds,
        month_hours=round(month_seconds / 3600, 2),
        active_projects=active_projects,
        pending_tasks=pending_tasks,
        running_timer=running_timer
    )


@router.get("/weekly", response_model=WeeklySummary)
async def get_weekly_summary(
    week_offset: int = Query(0, ge=-52, le=0, description="Weeks ago (0 = current week)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get weekly time summary"""
    now = datetime.now()
    week_start = (now - timedelta(days=now.weekday()) - timedelta(weeks=abs(week_offset))).date()
    week_end = week_start + timedelta(days=6)
    
    start_datetime = datetime.combine(week_start, datetime.min.time())
    end_datetime = datetime.combine(week_end, datetime.max.time())
    
    user_filter = TimeEntry.user_id == current_user.id
    date_filter = and_(TimeEntry.start_time >= start_datetime, TimeEntry.start_time <= end_datetime)
    
    # Total for week
    total_result = await db.execute(
        select(
            func.coalesce(func.sum(TimeEntry.duration_seconds), 0),
            func.count(TimeEntry.id)
        )
        .where(user_filter, date_filter)
    )
    total_row = total_result.first()
    total_seconds = total_row[0] or 0
    
    # Daily breakdown
    daily_breakdown = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        day_result = await db.execute(
            select(
                func.coalesce(func.sum(TimeEntry.duration_seconds), 0),
                func.count(TimeEntry.id)
            )
            .where(user_filter, TimeEntry.start_time >= day_start, TimeEntry.start_time <= day_end)
        )
        day_row = day_result.first()
        day_seconds = day_row[0] or 0
        day_count = day_row[1] or 0
        
        daily_breakdown.append(DailySummary(
            date=day,
            total_seconds=day_seconds,
            total_hours=round(day_seconds / 3600, 2),
            entry_count=day_count
        ))
    
    return WeeklySummary(
        week_start=week_start,
        week_end=week_end,
        total_seconds=total_seconds,
        total_hours=round(total_seconds / 3600, 2),
        daily_breakdown=daily_breakdown
    )


@router.get("/by-project", response_model=List[ProjectSummary])
async def get_time_by_project(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get time summary grouped by project"""
    # Default to current month
    if not start_date:
        now = datetime.now()
        start_date = now.replace(day=1).date()
    if not end_date:
        end_date = datetime.now().date()
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get accessible projects for user
    if current_user.role == "super_admin":
        project_ids_query = select(Project.id)
    else:
        user_teams = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
        project_ids_query = select(Project.id).where(
            Project.team_id.in_(user_teams)
        )
    
    # Query time by project
    result = await db.execute(
        select(
            TimeEntry.project_id,
            Project.name,
            # Project.is_billable,
            # Project.hourly_rate,
            # Project.budget_hours,
            func.coalesce(func.sum(TimeEntry.duration_seconds), 0).label("total_seconds"),
            func.count(TimeEntry.id).label("entry_count")
        )
        .join(Project, TimeEntry.project_id == Project.id)
        .where(
            TimeEntry.user_id == current_user.id,
            TimeEntry.start_time >= start_datetime,
            TimeEntry.start_time <= end_datetime,
            TimeEntry.project_id.in_(project_ids_query)
        )
        .group_by(TimeEntry.project_id, Project.name)
        .order_by(func.sum(TimeEntry.duration_seconds).desc())
    )
    
    summaries = []
    for row in result.all():
        total_seconds = row.total_seconds or 0
        total_hours = round(total_seconds / 3600, 2)

        summaries.append(ProjectSummary(
            project_id=row.project_id,
            project_name=row.name,
            total_seconds=total_seconds,
            total_hours=total_hours,
            entry_count=row.entry_count,
            billable_amount=None,
            budget_hours=None,
            budget_used_percent=None
        ))

    return summaries
@router.get("/by-task", response_model=List[TaskSummary])
async def get_time_by_task(
    project_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get time summary grouped by task"""
    # Default to current month
    if not start_date:
        now = datetime.now()
        start_date = now.replace(day=1).date()
    if not end_date:
        end_date = datetime.now().date()
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    query = (
        select(
            TimeEntry.task_id,
            Task.name.label("task_name"),
            Task.status,
            Project.name.label("project_name"),
            func.coalesce(func.sum(TimeEntry.duration_seconds), 0).label("total_seconds")
        )
        .join(Task, TimeEntry.task_id == Task.id)
        .join(Project, TimeEntry.project_id == Project.id)
        .where(
            TimeEntry.user_id == current_user.id,
            TimeEntry.task_id != None,
            TimeEntry.start_time >= start_datetime,
            TimeEntry.start_time <= end_datetime
        )
        .group_by(TimeEntry.task_id, Task.name, Task.status, Project.name)
        .order_by(func.sum(TimeEntry.duration_seconds).desc())
    )
    
    if project_id:
        query = query.where(TimeEntry.project_id == project_id)
    
    result = await db.execute(query)
    
    summaries = []
    for row in result.all():
        total_seconds = row.total_seconds or 0
        summaries.append(TaskSummary(
            task_id=row.task_id,
            task_name=row.task_name,
            project_name=row.project_name,
            total_seconds=total_seconds,
            total_hours=round(total_seconds / 3600, 2),
            status=row.status
        ))
    
    return summaries


@router.get("/team", response_model=TimeReport)
async def get_team_report(
    team_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get team time report (team admin/owner only)"""
    # Check team access
    if current_user.role != "super_admin":
        member_check = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == current_user.id,
                TeamMember.role.in_(["owner", "admin"])
            )
        )
        if not member_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Team admin access required")
    
    # Default to current month
    if not start_date:
        now = datetime.now()
        start_date = now.replace(day=1).date()
    if not end_date:
        end_date = datetime.now().date()
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get team members
    team_members = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
    
    # Get team projects
    team_projects = select(Project.id).where(Project.team_id == team_id)
    
    # Base filter
    base_filter = and_(
        TimeEntry.user_id.in_(team_members),
        TimeEntry.project_id.in_(team_projects),
        TimeEntry.start_time >= start_datetime,
        TimeEntry.start_time <= end_datetime
    )
    
    # Total summary
    total_result = await db.execute(
        select(
            func.coalesce(func.sum(TimeEntry.duration_seconds), 0),
            func.count(TimeEntry.id)
        )
        .where(base_filter)
    )
    total_row = total_result.first()
    total_seconds = total_row[0] or 0
    total_entries = total_row[1] or 0
    
    # By project
    project_result = await db.execute(
        select(
            TimeEntry.project_id,
            Project.name,
            # Project.is_billable,
            # Project.hourly_rate,
            # Project.budget_hours,
            func.coalesce(func.sum(TimeEntry.duration_seconds), 0).label("total_seconds"),
            func.count(TimeEntry.id).label("entry_count")
        )
        .join(Project, TimeEntry.project_id == Project.id)
        .where(base_filter)
        .group_by(TimeEntry.project_id, Project.name)
        .order_by(func.sum(TimeEntry.duration_seconds).desc())
    )
    
    by_project = []
    for row in project_result.all():
        seconds = row.total_seconds or 0
        hours = round(seconds / 3600, 2)
        by_project.append(ProjectSummary(
            project_id=row.project_id,
            project_name=row.name,
            total_seconds=seconds,
            total_hours=hours,
            entry_count=row.entry_count,
            billable_amount=None,
            budget_hours=None,
            budget_used_percent=None
        ))
    
    # By user
    user_result = await db.execute(
        select(
            TimeEntry.user_id,
            User.name,
            func.coalesce(func.sum(TimeEntry.duration_seconds), 0).label("total_seconds"),
            func.count(TimeEntry.id).label("entry_count")
        )
        .join(User, TimeEntry.user_id == User.id)
        .where(base_filter)
        .group_by(TimeEntry.user_id, User.name)
        .order_by(func.sum(TimeEntry.duration_seconds).desc())
    )
    
    by_user = []
    for row in user_result.all():
        seconds = row.total_seconds or 0
        by_user.append(UserSummary(
            user_id=row.user_id,
            user_name=row.name,
            total_seconds=seconds,
            total_hours=round(seconds / 3600, 2),
            entry_count=row.entry_count
        ))
    
    # By day
    by_day = []
    current_date = start_date
    while current_date <= end_date:
        day_start = datetime.combine(current_date, datetime.min.time())
        day_end = datetime.combine(current_date, datetime.max.time())
        
        day_result = await db.execute(
            select(
                func.coalesce(func.sum(TimeEntry.duration_seconds), 0),
                func.count(TimeEntry.id)
            )
            .where(
                TimeEntry.user_id.in_(team_members),
                TimeEntry.project_id.in_(team_projects),
                TimeEntry.start_time >= day_start,
                TimeEntry.start_time <= day_end
            )
        )
        day_row = day_result.first()
        day_seconds = day_row[0] or 0
        
        by_day.append(DailySummary(
            date=current_date,
            total_seconds=day_seconds,
            total_hours=round(day_seconds / 3600, 2),
            entry_count=day_row[1] or 0
        ))
        
        current_date += timedelta(days=1)
    
    return TimeReport(
        start_date=start_date,
        end_date=end_date,
        total_seconds=total_seconds,
        total_hours=round(total_seconds / 3600, 2),
        total_entries=total_entries,
        by_project=by_project,
        by_user=by_user,
        by_day=by_day
    )


@router.get("/export")
async def export_time_entries(
    start_date: date,
    end_date: date,
    project_id: Optional[int] = None,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Export time entries (JSON or CSV format)"""
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    query = (
        select(
            TimeEntry,
            Project.name.label("project_name"),
            Task.name.label("task_name"),
            User.name.label("user_name")
        )
        .join(Project, TimeEntry.project_id == Project.id)
        .outerjoin(Task, TimeEntry.task_id == Task.id)
        .join(User, TimeEntry.user_id == User.id)
        .where(
            TimeEntry.user_id == current_user.id,
            TimeEntry.start_time >= start_datetime,
            TimeEntry.start_time <= end_datetime
        )
        .order_by(TimeEntry.start_time.desc())
    )
    
    if project_id:
        query = query.where(TimeEntry.project_id == project_id)
    
    result = await db.execute(query)
    rows = result.all()
    
    if format == "csv":
        import csv
        import io
        from fastapi.responses import StreamingResponse
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Date", "Start Time", "End Time", "Duration (hours)",
            "Project", "Task", "Description"
        ])
        
        for row in rows:
            entry = row[0]
            writer.writerow([
                entry.start_time.date().isoformat(),
                entry.start_time.time().isoformat(),
                entry.end_time.time().isoformat() if entry.end_time else "",
                round(entry.duration_seconds / 3600, 2) if entry.duration_seconds else "",
                row.project_name,
                row.task_name or "",
                entry.description or ""
            ])
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=time_entries_{start_date}_{end_date}.csv"}
        )
    
    # JSON format
    entries = []
    for row in rows:
        entry = row[0]
        entries.append({
            "id": entry.id,
            "date": entry.start_time.date().isoformat(),
            "start_time": entry.start_time.isoformat(),
            "end_time": entry.end_time.isoformat() if entry.end_time else None,
            "duration_hours": round(entry.duration_seconds / 3600, 2) if entry.duration_seconds else None,
            "project": row.project_name,
            "task": row.task_name,
            "description": entry.description
        })
    
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_entries": len(entries),
        "entries": entries
    }




class AdminDashboardStats(BaseModel):
    total_today_seconds: int
    total_today_hours: float
    total_week_seconds: int
    total_week_hours: float
    total_month_seconds: int
    total_month_hours: float
    active_users_today: int
    active_projects: int
    running_timers: int
    by_user: List[UserSummary]


@router.get("/admin/dashboard", response_model=AdminDashboardStats)
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    '''Get admin dashboard with all team members time (super_admin only)'''
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    now = datetime.now()
    today_start = datetime.combine(now.date(), datetime.min.time())
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    # Total time today (all users)
    today_result = await db.execute(
        select(func.coalesce(func.sum(TimeEntry.duration_seconds), 0))
        .where(TimeEntry.start_time >= today_start)
    )
    total_today = today_result.scalar() or 0

    # Total time this week (all users)
    week_result = await db.execute(
        select(func.coalesce(func.sum(TimeEntry.duration_seconds), 0))
        .where(TimeEntry.start_time >= week_start)
    )
    total_week = week_result.scalar() or 0

    # Total time this month (all users)
    month_result = await db.execute(
        select(func.coalesce(func.sum(TimeEntry.duration_seconds), 0))
        .where(TimeEntry.start_time >= month_start)
    )
    total_month = month_result.scalar() or 0

    # Active users today
    active_users_result = await db.execute(
        select(func.count(func.distinct(TimeEntry.user_id)))
        .where(TimeEntry.start_time >= today_start)
    )
    active_users = active_users_result.scalar() or 0

    # Active projects
    active_projects_result = await db.execute(
        select(func.count(Project.id))
        .where(Project.is_archived == False)
    )
    active_projects = active_projects_result.scalar() or 0

    # Running timers count
    running_result = await db.execute(
        select(func.count(TimeEntry.id))
        .where(TimeEntry.end_time == None)
    )
    running_timers = running_result.scalar() or 0

    # Time by user today
    user_result = await db.execute(
        select(
            TimeEntry.user_id,
            User.name,
            func.coalesce(func.sum(TimeEntry.duration_seconds), 0).label("total_seconds"),
            func.count(TimeEntry.id).label("entry_count")
        )
        .join(User, TimeEntry.user_id == User.id)
        .where(TimeEntry.start_time >= today_start)
        .group_by(TimeEntry.user_id, User.name)
        .order_by(func.sum(TimeEntry.duration_seconds).desc())
    )

    by_user = []
    for row in user_result.all():
        by_user.append(UserSummary(
            user_id=row.user_id,
            user_name=row.name,
            total_seconds=row.total_seconds or 0,
            total_hours=round((row.total_seconds or 0) / 3600, 2),
            entry_count=row.entry_count
        ))

    return AdminDashboardStats(
        total_today_seconds=total_today,
        total_today_hours=round(total_today / 3600, 2),
        total_week_seconds=total_week,
        total_week_hours=round(total_week / 3600, 2),
        total_month_seconds=total_month,
        total_month_hours=round(total_month / 3600, 2),
        active_users_today=active_users,
        active_projects=active_projects,
        running_timers=running_timers,
        by_user=by_user
    )
