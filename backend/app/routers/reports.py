"""
Reports and analytics router
"""

import logging
from typing import Optional, List
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from datetime import datetime, date, timedelta, timezone, time

from app.database import get_db
from app.models import User, Team, TeamMember, Project, Task, TimeEntry
from app.dependencies import get_current_active_user, get_company_filter, apply_company_filter, FILTER_NULL_COMPANY

router = APIRouter()
logger = logging.getLogger(__name__)


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


def calculate_entry_duration(entry: TimeEntry, now: datetime) -> int:
    """Calculate duration for a time entry, including running timers"""
    if entry.end_time is None:
        # Active timer - calculate elapsed time
        start = entry.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return int((now - start).total_seconds())
    else:
        return entry.duration_seconds or 0


def calculate_entry_duration_for_period(entry: TimeEntry, period_start: datetime, period_end: datetime, now: datetime) -> int:
    """
    Calculate duration of a time entry that overlaps with a specific period.
    This handles entries that span multiple days by only counting time within the period.
    
    Args:
        entry: The time entry
        period_start: Start of the period (e.g., start of day)
        period_end: End of the period (e.g., end of day)
        now: Current time (for running timers)
    
    Returns:
        Seconds of the entry that fall within the period
    """
    # Get entry start time with timezone
    entry_start = entry.start_time
    if entry_start.tzinfo is None:
        entry_start = entry_start.replace(tzinfo=timezone.utc)
    
    # Get entry end time (or now for running timers)
    if entry.end_time is None:
        entry_end = now
    else:
        entry_end = entry.end_time
        if entry_end.tzinfo is None:
            entry_end = entry_end.replace(tzinfo=timezone.utc)
    
    # Calculate overlap between entry and period
    overlap_start = max(entry_start, period_start)
    overlap_end = min(entry_end, period_end)
    
    # If no overlap, return 0
    if overlap_start >= overlap_end:
        return 0
    
    return int((overlap_end - overlap_start).total_seconds())


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get dashboard statistics for current user (filtered by company for multi-tenancy)"""
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
    week_start = today_start - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=7)
    month_start = today_start.replace(day=1)
    # Calculate month end (first day of next month)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)
    
    # Multi-tenancy: get company filter
    company_id = get_company_filter(current_user)
    
    # Base filter: admins see all in company, regular users see team data
    if current_user.role in ["super_admin", "admin"]:
        if company_id is None:
            user_filter = True  # Platform super_admin sees all
        elif company_id == FILTER_NULL_COMPANY:
            # Platform admin sees only platform users (NULL company_id)
            company_users = select(User.id).where(User.company_id.is_(None))
            user_filter = TimeEntry.user_id.in_(company_users)
        else:
            # Admin within a company sees all company entries
            company_users = select(User.id).where(User.company_id == company_id)
            user_filter = TimeEntry.user_id.in_(company_users)
    else:
        # Get all team members from user's teams (within company)
        user_teams_query = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
        team_members = select(TeamMember.user_id).where(TeamMember.team_id.in_(user_teams_query))
        user_filter = TimeEntry.user_id.in_(team_members)
    
    # Today's time - fetch entries that OVERLAP with today (started before today end AND ended after today start or still running)
    # This includes: entries that started today, entries from yesterday still running, entries spanning midnight
    today_query = select(TimeEntry).where(
        TimeEntry.start_time < today_end,  # Started before today ends
        (TimeEntry.end_time >= today_start) | (TimeEntry.end_time.is_(None))  # Ended after today started OR still running
    )
    if user_filter is not True:
        today_query = today_query.where(user_filter)
    today_result = await db.execute(today_query)
    today_entries = today_result.scalars().all()
    # Calculate only the portion that falls within today
    today_seconds = sum(calculate_entry_duration_for_period(e, today_start, today_end, now) for e in today_entries)
    
    # This week's time - fetch entries that overlap with this week
    week_query = select(TimeEntry).where(
        TimeEntry.start_time < week_end,
        (TimeEntry.end_time >= week_start) | (TimeEntry.end_time.is_(None))
    )
    if user_filter is not True:
        week_query = week_query.where(user_filter)
    week_result = await db.execute(week_query)
    week_entries = week_result.scalars().all()
    week_seconds = sum(calculate_entry_duration_for_period(e, week_start, week_end, now) for e in week_entries)
    
    # This month's time - fetch entries that overlap with this month
    month_query = select(TimeEntry).where(
        TimeEntry.start_time < month_end,
        (TimeEntry.end_time >= month_start) | (TimeEntry.end_time.is_(None))
    )
    if user_filter is not True:
        month_query = month_query.where(user_filter)
    month_result = await db.execute(month_query)
    month_entries = month_result.scalars().all()
    month_seconds = sum(calculate_entry_duration_for_period(e, month_start, month_end, now) for e in month_entries)
    
    # Active projects (user has access to, within company)
    user_teams = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
    project_query = select(func.count(Project.id)).join(Team, Project.team_id == Team.id).where(
        Project.team_id.in_(user_teams), 
        Project.is_archived == False
    )
    if company_id is None:
        pass  # Super admin sees all
    elif company_id == FILTER_NULL_COMPANY:
        project_query = project_query.where(Team.company_id.is_(None))
    else:
        project_query = project_query.where(Team.company_id == company_id)
    active_projects_result = await db.execute(project_query)
    active_projects = active_projects_result.scalar() or 0
    
    # Pending tasks assigned to user
    pending_tasks = 0  # Simplified for now
    
    # Check for running timer
    running_timer = any(e.end_time is None for e in today_entries)
    
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
    start_date: Optional[date] = None,
    week_offset: int = Query(0, ge=-52, le=0, description="Weeks ago (0 = current week)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get weekly time summary (filtered by company for multi-tenancy)"""
    now = datetime.now(timezone.utc)
    
    # Use start_date if provided, otherwise calculate from week_offset
    if start_date:
        week_start = start_date
    else:
        week_start = (now - timedelta(days=now.weekday()) - timedelta(weeks=abs(week_offset))).date()
    
    week_end = week_start + timedelta(days=6)
    
    start_datetime = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_datetime = datetime.combine(week_end + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)  # Midnight after week ends
    
    # Multi-tenancy: get company filter
    company_id = get_company_filter(current_user)
    
    # Build user filter: admins see all in company, regular users see team data
    if current_user.role in ["super_admin", "admin"]:
        if company_id is None:
            user_filter = True  # Platform super_admin sees all
        elif company_id == FILTER_NULL_COMPANY:
            company_users = select(User.id).where(User.company_id.is_(None))
            user_filter = TimeEntry.user_id.in_(company_users)
        else:
            company_users = select(User.id).where(User.company_id == company_id)
            user_filter = TimeEntry.user_id.in_(company_users)
    else:
        # Get all team members from user's teams
        user_teams = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
        team_members = select(TeamMember.user_id).where(TeamMember.team_id.in_(user_teams))
        user_filter = TimeEntry.user_id.in_(team_members)
    
    # Fetch entries that OVERLAP with this week (not just started within)
    entries_query = select(TimeEntry).where(
        TimeEntry.start_time < end_datetime,  # Started before week ends
        (TimeEntry.end_time >= start_datetime) | (TimeEntry.end_time.is_(None))  # Ended after week started OR still running
    )
    if user_filter is not True:
        entries_query = entries_query.where(user_filter)
    entries_result = await db.execute(entries_query)
    all_entries = entries_result.scalars().all()
    
    # Calculate total seconds for the week using period overlap
    total_seconds = sum(calculate_entry_duration_for_period(e, start_datetime, end_datetime, now) for e in all_entries)
    
    # Daily breakdown - calculate overlap for each day
    daily_breakdown = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = datetime.combine(day + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
        
        # Calculate seconds for this day from ALL entries that overlap with this day
        day_seconds = sum(calculate_entry_duration_for_period(e, day_start, day_end, now) for e in all_entries)
        # Count entries that have any overlap with this day
        day_count = sum(1 for e in all_entries if calculate_entry_duration_for_period(e, day_start, day_end, now) > 0)
        
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
    now = datetime.now(timezone.utc)
    
    # Default to current month
    if not start_date:
        start_date = now.replace(day=1).date()
    if not end_date:
        end_date = now.date()
    
    start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)  # Day after end_date at midnight
    
    # Get accessible projects and users for current user
    if current_user.role in ["super_admin", "admin"]:
        project_ids_query = select(Project.id)
        user_filter = True  # No filter, see all users
    else:
        user_teams = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
        project_ids_query = select(Project.id).where(
            Project.team_id.in_(user_teams)
        )
        # Get all team members from user's teams
        team_members = select(TeamMember.user_id).where(TeamMember.team_id.in_(user_teams))
        user_filter = TimeEntry.user_id.in_(team_members)
    
    # Fetch entries that OVERLAP with the period (not just started within)
    query_filters = [
        TimeEntry.start_time < end_datetime,  # Started before period ends
        (TimeEntry.end_time >= start_datetime) | (TimeEntry.end_time.is_(None)),  # Ended after period started OR still running
        TimeEntry.project_id.in_(project_ids_query)
    ]
    if user_filter is not True:
        query_filters.append(user_filter)
    
    result = await db.execute(
        select(TimeEntry, Project.name)
        .join(Project, TimeEntry.project_id == Project.id)
        .where(*query_filters)
    )
    
    # Group by project and calculate totals - only count time within the period
    project_data = defaultdict(lambda: {"name": "", "seconds": 0, "count": 0})
    
    for entry, project_name in result.all():
        pid = entry.project_id
        project_data[pid]["name"] = project_name
        # Calculate only the portion that falls within the requested period
        entry_seconds = calculate_entry_duration_for_period(entry, start_datetime, end_datetime, now)
        if entry_seconds > 0:
            project_data[pid]["seconds"] += entry_seconds
            project_data[pid]["count"] += 1
    
    summaries = []
    for project_id, data in sorted(project_data.items(), key=lambda x: x[1]["seconds"], reverse=True):
        total_seconds = data["seconds"]
        total_hours = round(total_seconds / 3600, 2)

        summaries.append(ProjectSummary(
            project_id=project_id,
            project_name=data["name"],
            total_seconds=total_seconds,
            total_hours=total_hours,
            entry_count=data["count"],
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
    now = datetime.now(timezone.utc)
    
    # Default to current month
    if not start_date:
        start_date = now.replace(day=1).date()
    if not end_date:
        end_date = now.date()
    
    start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
    
    # Fetch entries that OVERLAP with the period
    query = (
        select(TimeEntry, Task.name.label("task_name"), Task.status, Project.name.label("project_name"))
        .join(Task, TimeEntry.task_id == Task.id)
        .join(Project, TimeEntry.project_id == Project.id)
        .where(
            TimeEntry.user_id == current_user.id,
            TimeEntry.task_id != None,
            TimeEntry.start_time < end_datetime,
            (TimeEntry.end_time >= start_datetime) | (TimeEntry.end_time.is_(None))
        )
    )
    
    if project_id:
        query = query.where(TimeEntry.project_id == project_id)
    
    result = await db.execute(query)
    
    # Group by task and calculate totals - only count time within period
    task_data = defaultdict(lambda: {"task_name": "", "project_name": "", "status": "", "seconds": 0})
    
    for entry, task_name, task_status, project_name in result.all():
        tid = entry.task_id
        task_data[tid]["task_name"] = task_name
        task_data[tid]["project_name"] = project_name
        task_data[tid]["status"] = task_status
        entry_seconds = calculate_entry_duration_for_period(entry, start_datetime, end_datetime, now)
        if entry_seconds > 0:
            task_data[tid]["seconds"] += entry_seconds
    
    summaries = []
    for task_id, data in sorted(task_data.items(), key=lambda x: x[1]["seconds"], reverse=True):
        total_seconds = data["seconds"]
        summaries.append(TaskSummary(
            task_id=task_id,
            task_name=data["task_name"],
            project_name=data["project_name"],
            total_seconds=total_seconds,
            total_hours=round(total_seconds / 3600, 2),
            status=data["status"]
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
    """Get team time report (team admin/owner only, filtered by company for multi-tenancy)"""
    # Multi-tenancy: verify team belongs to user's company
    company_id = get_company_filter(current_user)
    team_query = select(Team).where(Team.id == team_id)
    team_query = apply_company_filter(team_query, Team.company_id, company_id)
    team_result = await db.execute(team_query)
    team = team_result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    
    # Check team access
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
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
        now = datetime.now(timezone.utc)
        start_date = now.replace(day=1).date()
    if not end_date:
        end_date = datetime.now(timezone.utc).date()
    
    now = datetime.now(timezone.utc)
    start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
    
    # Get team members
    team_members = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
    
    # Get team projects
    team_projects = select(Project.id).where(Project.team_id == team_id)
    
    # Fetch all entries that OVERLAP with the period (instead of using SQL aggregates)
    entries_query = (
        select(TimeEntry, Project.name.label("project_name"), User.name.label("user_name"))
        .join(Project, TimeEntry.project_id == Project.id)
        .join(User, TimeEntry.user_id == User.id)
        .where(
            TimeEntry.user_id.in_(team_members),
            TimeEntry.project_id.in_(team_projects),
            TimeEntry.start_time < end_datetime,
            (TimeEntry.end_time >= start_datetime) | (TimeEntry.end_time.is_(None))
        )
    )
    entries_result = await db.execute(entries_query)
    all_entries = entries_result.all()
    
    # Calculate totals with proper period overlap
    total_seconds = 0
    total_entries = 0
    project_data = defaultdict(lambda: {"name": "", "seconds": 0, "count": 0})
    user_data = defaultdict(lambda: {"name": "", "seconds": 0, "count": 0})
    
    for entry, project_name, user_name in all_entries:
        entry_seconds = calculate_entry_duration_for_period(entry, start_datetime, end_datetime, now)
        if entry_seconds > 0:
            total_seconds += entry_seconds
            total_entries += 1
            project_data[entry.project_id]["name"] = project_name
            project_data[entry.project_id]["seconds"] += entry_seconds
            project_data[entry.project_id]["count"] += 1
            user_data[entry.user_id]["name"] = user_name
            user_data[entry.user_id]["seconds"] += entry_seconds
            user_data[entry.user_id]["count"] += 1
    
    # Build by_project list
    by_project = []
    for pid, data in sorted(project_data.items(), key=lambda x: x[1]["seconds"], reverse=True):
        seconds = data["seconds"]
        by_project.append(ProjectSummary(
            project_id=pid,
            project_name=data["name"],
            total_seconds=seconds,
            total_hours=round(seconds / 3600, 2),
            entry_count=data["count"],
            billable_amount=None,
            budget_hours=None,
            budget_used_percent=None
        ))
    
    # Build by_user list
    by_user = []
    for uid, data in sorted(user_data.items(), key=lambda x: x[1]["seconds"], reverse=True):
        seconds = data["seconds"]
        by_user.append(UserSummary(
            user_id=uid,
            user_name=data["name"],
            total_seconds=seconds,
            total_hours=round(seconds / 3600, 2),
            entry_count=data["count"]
        ))
    
    # By day - calculate overlap for each day
    by_day = []
    current_date = start_date
    while current_date <= end_date:
        day_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = datetime.combine(current_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
        
        day_seconds = 0
        day_count = 0
        for entry, _, _ in all_entries:
            entry_day_seconds = calculate_entry_duration_for_period(entry, day_start, day_end, now)
            if entry_day_seconds > 0:
                day_seconds += entry_day_seconds
                day_count += 1
        
        by_day.append(DailySummary(
            date=current_date,
            total_seconds=day_seconds,
            total_hours=round(day_seconds / 3600, 2),
            entry_count=day_count
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
    start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
    
    # Fetch entries that OVERLAP with the export period
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
            TimeEntry.start_time < end_datetime,
            (TimeEntry.end_time >= start_datetime) | (TimeEntry.end_time.is_(None))
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


class TeamAnalytics(BaseModel):
    team_id: int
    team_name: str
    member_count: int
    total_today_seconds: int
    total_today_hours: float
    total_week_seconds: int
    total_week_hours: float
    total_month_seconds: int
    total_month_hours: float
    active_members_today: int
    running_timers: int
    top_performers: List[UserSummary]  # Top 3 this week


class IndividualUserMetrics(BaseModel):
    user_id: int
    user_name: str
    user_email: str
    role: str
    teams: List[str]
    # Time metrics
    today_seconds: int
    today_hours: float
    week_seconds: int
    week_hours: float
    month_seconds: int
    month_hours: float
    # Activity metrics
    total_entries: int
    active_days_this_month: int
    avg_hours_per_day: float
    current_timer_running: bool
    # Project breakdown
    projects: List[ProjectSummary]
    # Recent activity
    last_activity: Optional[datetime] = None

@router.get("/admin/dashboard", response_model=AdminDashboardStats)
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    '''Get admin dashboard with all team members time (admin and super_admin, filtered by company)'''
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), time.min).replace(tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
    week_start = (today_start - timedelta(days=now.weekday()))
    week_end = week_start + timedelta(days=7)
    month_start = today_start.replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)

    # Multi-tenancy: get company filter
    company_id = get_company_filter(current_user)
    
    # Build company user filter
    if company_id is None:
        user_filter = True  # Platform super_admin sees all
    elif company_id == FILTER_NULL_COMPANY:
        company_users_subq = select(User.id).where(User.company_id.is_(None))
        user_filter = TimeEntry.user_id.in_(company_users_subq)
    else:
        company_users_subq = select(User.id).where(User.company_id == company_id)
        user_filter = TimeEntry.user_id.in_(company_users_subq)

    # Total time today - entries that OVERLAP with today
    today_query = select(TimeEntry).where(
        TimeEntry.start_time < today_end,
        (TimeEntry.end_time >= today_start) | (TimeEntry.end_time.is_(None))
    )
    if user_filter is not True:
        today_query = today_query.where(user_filter)
    today_entries_result = await db.execute(today_query)
    today_entries = today_entries_result.scalars().all()
    
    logger.info(f"Found {len(today_entries)} time entries overlapping with today")
    
    # Calculate only the portion that falls within today
    total_today = sum(calculate_entry_duration_for_period(e, today_start, today_end, now) for e in today_entries)
    
    logger.info(f"FINAL total_today={total_today}")

    # Total time this week - entries that overlap with this week
    week_query = select(TimeEntry).where(
        TimeEntry.start_time < week_end,
        (TimeEntry.end_time >= week_start) | (TimeEntry.end_time.is_(None))
    )
    if user_filter is not True:
        week_query = week_query.where(user_filter)
    week_entries_result = await db.execute(week_query)
    week_entries = week_entries_result.scalars().all()
    
    total_week = sum(calculate_entry_duration_for_period(e, week_start, week_end, now) for e in week_entries)

    # Total time this month - entries that overlap with this month
    month_query = select(TimeEntry).where(
        TimeEntry.start_time < month_end,
        (TimeEntry.end_time >= month_start) | (TimeEntry.end_time.is_(None))
    )
    if user_filter is not True:
        month_query = month_query.where(user_filter)
    month_entries_result = await db.execute(month_query)
    month_entries = month_entries_result.scalars().all()
    
    total_month = sum(calculate_entry_duration_for_period(e, month_start, month_end, now) for e in month_entries)

    # Active users today - count distinct users from entries overlapping with today
    active_users = len(set(e.user_id for e in today_entries if calculate_entry_duration_for_period(e, today_start, today_end, now) > 0))

    # Active projects (within company)
    project_query = select(func.count(Project.id)).join(Team, Project.team_id == Team.id).where(Project.is_archived == False)
    if company_id is None:
        pass  # Super admin sees all
    elif company_id == FILTER_NULL_COMPANY:
        project_query = project_query.where(Team.company_id.is_(None))
    else:
        project_query = project_query.where(Team.company_id == company_id)
    active_projects_result = await db.execute(project_query)
    active_projects = active_projects_result.scalar() or 0

    # Running timers count (within company)
    running_query = select(func.count(TimeEntry.id)).where(TimeEntry.end_time.is_(None))
    if user_filter is not True:
        running_query = running_query.where(user_filter)
    running_result = await db.execute(running_query)
    running_timers = running_result.scalar() or 0

    # Time by user today - use the already fetched today_entries with period calculation
    user_totals = {}
    for entry in today_entries:
        user_id = entry.user_id
        
        if user_id not in user_totals:
            # Need to fetch user name
            user_totals[user_id] = {
                "user_name": None,  # Will be populated below
                "total_seconds": 0,
                "entry_count": 0
            }
        
        # Calculate only the portion that falls within today
        entry_seconds = calculate_entry_duration_for_period(entry, today_start, today_end, now)
        if entry_seconds > 0:
            user_totals[user_id]["total_seconds"] += entry_seconds
            user_totals[user_id]["entry_count"] += 1
    
    # Fetch user names for users with entries
    if user_totals:
        user_names_query = select(User.id, User.name).where(User.id.in_(list(user_totals.keys())))
        user_names_result = await db.execute(user_names_query)
        for row in user_names_result.all():
            if row.id in user_totals:
                user_totals[row.id]["user_name"] = row.name

    by_user = []
    for user_id, data in sorted(user_totals.items(), key=lambda x: x[1]["total_seconds"], reverse=True):
        by_user.append(UserSummary(
            user_id=user_id,
            user_name=data["user_name"],
            total_seconds=data["total_seconds"],
            total_hours=round(data["total_seconds"] / 3600, 2),
            entry_count=data["entry_count"]
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


@router.get("/admin/teams", response_model=List[TeamAnalytics])
async def get_team_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    '''Get analytics for all teams (admin and super_admin only, filtered by company)'''
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), time.min).replace(tzinfo=timezone.utc)
    week_start = (today_start - timedelta(days=now.weekday()))
    month_start = today_start.replace(day=1)

    # Multi-tenancy: filter teams by company
    company_id = get_company_filter(current_user)
    teams_query = select(Team)
    teams_query = apply_company_filter(teams_query, Team.company_id, company_id)
    teams_result = await db.execute(teams_query)
    teams = teams_result.scalars().all()

    team_analytics = []

    for team in teams:
        # Get team members
        members_result = await db.execute(
            select(TeamMember.user_id, User.name)
            .join(User, TeamMember.user_id == User.id)
            .where(TeamMember.team_id == team.id)
        )
        members = members_result.all()
        member_ids = [m.user_id for m in members]

        if not member_ids:
            # Empty team, skip
            continue

        # Total time today (team members) - including active timers
        today_entries_result = await db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.start_time >= today_start,
                    TimeEntry.user_id.in_(member_ids)
                )
            )
        )
        today_entries = today_entries_result.scalars().all()
        
        total_today = 0
        for entry in today_entries:
            if entry.end_time is None:
                start = entry.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                total_today += int((now - start).total_seconds())
            else:
                total_today += (entry.duration_seconds or 0)

        # Total time this week (team members)
        week_entries_result = await db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.start_time >= week_start,
                    TimeEntry.user_id.in_(member_ids)
                )
            )
        )
        week_entries = week_entries_result.scalars().all()
        
        total_week = 0
        for entry in week_entries:
            if entry.end_time is None:
                start = entry.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                total_week += int((now - start).total_seconds())
            else:
                total_week += (entry.duration_seconds or 0)

        # Total time this month (team members)
        month_entries_result = await db.execute(
            select(TimeEntry)
            .where(
                and_(
                    TimeEntry.start_time >= month_start,
                    TimeEntry.user_id.in_(member_ids)
                )
            )
        )
        month_entries = month_entries_result.scalars().all()
        
        total_month = 0
        for entry in month_entries:
            if entry.end_time is None:
                start = entry.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                total_month += int((now - start).total_seconds())
            else:
                total_month += (entry.duration_seconds or 0)

        # Active members today
        active_members_result = await db.execute(
            select(func.count(func.distinct(TimeEntry.user_id)))
            .where(
                and_(
                    TimeEntry.start_time >= today_start,
                    TimeEntry.user_id.in_(member_ids)
                )
            )
        )
        active_members = active_members_result.scalar() or 0

        # Running timers count
        running_result = await db.execute(
            select(func.count(TimeEntry.id))
            .where(
                and_(
                    TimeEntry.end_time == None,
                    TimeEntry.user_id.in_(member_ids)
                )
            )
        )
        running_timers = running_result.scalar() or 0

        # Top performers this week (top 3)
        user_result = await db.execute(
            select(
                TimeEntry.user_id,
                User.name,
                TimeEntry.duration_seconds,
                TimeEntry.start_time,
                TimeEntry.end_time
            )
            .join(User, TimeEntry.user_id == User.id)
            .where(
                and_(
                    TimeEntry.start_time >= week_start,
                    TimeEntry.user_id.in_(member_ids)
                )
            )
        )

        # Aggregate by user
        user_totals = {}
        for row in user_result.all():
            user_id = row.user_id
            user_name = row.name
            
            if user_id not in user_totals:
                user_totals[user_id] = {
                    "user_name": user_name,
                    "total_seconds": 0,
                    "entry_count": 0
                }
            
            if row.end_time is None:
                start = row.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                user_totals[user_id]["total_seconds"] += int((now - start).total_seconds())
            else:
                user_totals[user_id]["total_seconds"] += (row.duration_seconds or 0)
            
            user_totals[user_id]["entry_count"] += 1

        # Get top 3 performers
        top_performers = []
        for user_id, data in sorted(user_totals.items(), key=lambda x: x[1]["total_seconds"], reverse=True)[:3]:
            top_performers.append(UserSummary(
                user_id=user_id,
                user_name=data["user_name"],
                total_seconds=data["total_seconds"],
                total_hours=round(data["total_seconds"] / 3600, 2),
                entry_count=data["entry_count"]
            ))

        team_analytics.append(TeamAnalytics(
            team_id=team.id,
            team_name=team.name,
            member_count=len(member_ids),
            total_today_seconds=total_today,
            total_today_hours=round(total_today / 3600, 2),
            total_week_seconds=total_week,
            total_week_hours=round(total_week / 3600, 2),
            total_month_seconds=total_month,
            total_month_hours=round(total_month / 3600, 2),
            active_members_today=active_members,
            running_timers=running_timers,
            top_performers=top_performers
        ))

    return team_analytics


@router.get("/admin/users/{user_id}", response_model=IndividualUserMetrics)
async def get_user_metrics(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    '''Get detailed metrics for a specific user (admin and super_admin only, filtered by company)'''
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Multi-tenancy: filter user by company
    company_id = get_company_filter(current_user)
    user_query = select(User).where(User.id == user_id)
    user_query = apply_company_filter(user_query, User.company_id, company_id)
    
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), time.min).replace(tzinfo=timezone.utc)
    week_start = (today_start - timedelta(days=now.weekday()))
    month_start = today_start.replace(day=1)

    # Get user's teams
    teams_result = await db.execute(
        select(Team.name)
        .join(TeamMember, Team.id == TeamMember.team_id)
        .where(TeamMember.user_id == user_id)
    )
    teams = [t[0] for t in teams_result.all()]

    # Time today
    today_entries_result = await db.execute(
        select(TimeEntry)
        .where(
            and_(
                TimeEntry.start_time >= today_start,
                TimeEntry.user_id == user_id
            )
        )
    )
    today_entries = today_entries_result.scalars().all()
    
    today_seconds = 0
    for entry in today_entries:
        if entry.end_time is None:
            start = entry.start_time
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            today_seconds += int((now - start).total_seconds())
        else:
            today_seconds += (entry.duration_seconds or 0)

    # Time this week
    week_entries_result = await db.execute(
        select(TimeEntry)
        .where(
            and_(
                TimeEntry.start_time >= week_start,
                TimeEntry.user_id == user_id
            )
        )
    )
    week_entries = week_entries_result.scalars().all()
    
    week_seconds = 0
    for entry in week_entries:
        if entry.end_time is None:
            start = entry.start_time
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            week_seconds += int((now - start).total_seconds())
        else:
            week_seconds += (entry.duration_seconds or 0)

    # Time this month
    month_entries_result = await db.execute(
        select(TimeEntry)
        .where(
            and_(
                TimeEntry.start_time >= month_start,
                TimeEntry.user_id == user_id
            )
        )
    )
    month_entries = month_entries_result.scalars().all()
    
    month_seconds = 0
    for entry in month_entries:
        if entry.end_time is None:
            start = entry.start_time
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            month_seconds += int((now - start).total_seconds())
        else:
            month_seconds += (entry.duration_seconds or 0)

    # Total entries count
    total_entries_result = await db.execute(
        select(func.count(TimeEntry.id))
        .where(TimeEntry.user_id == user_id)
    )
    total_entries = total_entries_result.scalar() or 0

    # Active days this month
    active_days_result = await db.execute(
        select(func.count(func.distinct(func.date(TimeEntry.start_time))))
        .where(
            and_(
                TimeEntry.start_time >= month_start,
                TimeEntry.user_id == user_id
            )
        )
    )
    active_days = active_days_result.scalar() or 0

    # Average hours per day (this month)
    avg_hours_per_day = round(month_seconds / 3600 / max(active_days, 1), 2)

    # Check for running timer
    running_result = await db.execute(
        select(TimeEntry)
        .where(
            and_(
                TimeEntry.user_id == user_id,
                TimeEntry.end_time == None
            )
        )
    )
    current_timer_running = running_result.scalar_one_or_none() is not None

    # Project breakdown (this month)
    project_result = await db.execute(
        select(
            TimeEntry.project_id,
            Project.name,
            TimeEntry.duration_seconds,
            TimeEntry.start_time,
            TimeEntry.end_time
        )
        .join(Project, TimeEntry.project_id == Project.id)
        .where(
            and_(
                TimeEntry.start_time >= month_start,
                TimeEntry.user_id == user_id
            )
        )
    )

    project_totals = {}
    for row in project_result.all():
        project_id = row.project_id
        project_name = row.name
        
        if project_id not in project_totals:
            project_totals[project_id] = {
                "project_name": project_name,
                "total_seconds": 0,
                "entry_count": 0
            }
        
        if row.end_time is None:
            start = row.start_time
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            project_totals[project_id]["total_seconds"] += int((now - start).total_seconds())
        else:
            project_totals[project_id]["total_seconds"] += (row.duration_seconds or 0)
        
        project_totals[project_id]["entry_count"] += 1

    projects = []
    for project_id, data in sorted(project_totals.items(), key=lambda x: x[1]["total_seconds"], reverse=True):
        projects.append(ProjectSummary(
            project_id=project_id,
            project_name=data["project_name"],
            total_seconds=data["total_seconds"],
            total_hours=round(data["total_seconds"] / 3600, 2),
            entry_count=data["entry_count"]
        ))

    # Last activity
    last_activity_result = await db.execute(
        select(TimeEntry.start_time)
        .where(TimeEntry.user_id == user_id)
        .order_by(TimeEntry.start_time.desc())
        .limit(1)
    )
    last_activity_row = last_activity_result.scalar_one_or_none()

    return IndividualUserMetrics(
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
        role=user.role,
        teams=teams,
        today_seconds=today_seconds,
        today_hours=round(today_seconds / 3600, 2),
        week_seconds=week_seconds,
        week_hours=round(week_seconds / 3600, 2),
        month_seconds=month_seconds,
        month_hours=round(month_seconds / 3600, 2),
        total_entries=total_entries,
        active_days_this_month=active_days,
        avg_hours_per_day=avg_hours_per_day,
        current_timer_running=current_timer_running,
        projects=projects,
        last_activity=last_activity_row
    )


@router.get("/admin/users", response_model=List[UserSummary])
async def get_all_users_summary(
    period: str = Query("week", regex="^(today|week|month)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    '''Get summary of all users sorted by time tracked (admin and super_admin only, filtered by company)'''
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), time.min).replace(tzinfo=timezone.utc)
    week_start = (today_start - timedelta(days=now.weekday()))
    month_start = today_start.replace(day=1)

    # Determine start time based on period
    if period == "today":
        start_time = today_start
    elif period == "week":
        start_time = week_start
    else:  # month
        start_time = month_start

    # Multi-tenancy: filter by company
    company_id = get_company_filter(current_user)

    # Get all users' time entries for the period (filtered by company)
    entries_query = select(
        TimeEntry.user_id,
        User.name,
        TimeEntry.duration_seconds,
        TimeEntry.start_time,
        TimeEntry.end_time
    ).join(User, TimeEntry.user_id == User.id).where(TimeEntry.start_time >= start_time)
    
    entries_query = apply_company_filter(entries_query, User.company_id, company_id)
    
    entries_result = await db.execute(entries_query)

    user_totals = {}
    for row in entries_result.all():
        user_id = row.user_id
        user_name = row.name
        
        if user_id not in user_totals:
            user_totals[user_id] = {
                "user_name": user_name,
                "total_seconds": 0,
                "entry_count": 0
            }
        
        if row.end_time is None:
            start = row.start_time
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            user_totals[user_id]["total_seconds"] += int((now - start).total_seconds())
        else:
            user_totals[user_id]["total_seconds"] += (row.duration_seconds or 0)
        
        user_totals[user_id]["entry_count"] += 1

    # Sort by total time descending
    users_summary = []
    for user_id, data in sorted(user_totals.items(), key=lambda x: x[1]["total_seconds"], reverse=True):
        users_summary.append(UserSummary(
            user_id=user_id,
            user_name=data["user_name"],
            total_seconds=data["total_seconds"],
            total_hours=round(data["total_seconds"] / 3600, 2),
            entry_count=data["entry_count"]
        ))

    return users_summary

