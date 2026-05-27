"""
Time entries management router - Core time tracking functionality
"""

import logging
import uuid as _uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import (
    apply_company_filter,
    get_company_filter,
    get_company_timezone,
    get_current_active_user,
)
from app.models import (
    Project,
    SessionBreak,
    SessionMeeting,
    Task,
    Team,
    TeamMember,
    TimeEntry,
    User,
    WorkSession,
)
from app.routers.websocket import manager as ws_manager
from app.schemas.auth import Message
from app.services.time_entry_description import resolve_description
from app.utils.timer_elapsed import (
    compute_display_elapsed_seconds,
    compute_state_elapsed_seconds,
)
from app.utils.timewindow import day_bounds

logger = logging.getLogger(__name__)

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
        # B1/B10: retain the 60s floor ONLY for explicitly user-submitted
        # manual durations. Computed durations from start/stop go through
        # ``calculate_duration_seconds`` and are no longer clamped.
        if v is not None and v < 60:
            raise ValueError('Duration must be at least 60 seconds')
        return v

    @model_validator(mode='after')
    def validate_chronology_and_bounds(self) -> "TimeEntryCreate":
        """B10: cross-field sanity checks on manual time entries."""
        start = self.start_time
        end = self.end_time
        if start is not None and end is not None:
            if end <= start:
                raise ValueError('end_time must be greater than start_time')
            # 24h cap, inclusive of the exact-24h boundary case.
            if (end - start) > timedelta(hours=24):
                raise ValueError('Manual entry cannot exceed 24 hours')
        return self


class TimeEntryUpdate(BaseModel):
    description: Optional[str] = Field(default=None, max_length=500)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    project_id: Optional[int] = None
    task_id: Optional[int] = None

    @model_validator(mode='after')
    def validate_chronology(self) -> "TimeEntryUpdate":
        """B3: when both fields are supplied, reject start > end at the
        schema layer (422). Handler-level checks still apply for the
        single-field-update case, where the other value comes from the
        existing row."""
        start = self.start_time
        end = self.end_time
        if start is not None and end is not None and end < start:
            raise ValueError('end_time must be greater than or equal to start_time')
        return self


class TimeEntryResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    task_id: Optional[int]
    task_name: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    project_color: Optional[str] = None
    description: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[int]
    duration_minutes: Optional[int] = None  # Computed field for convenience
    is_running: bool
    # Pause tracking for breaks/meetings
    is_paused: bool = False
    paused_at: Optional[datetime] = None
    pause_seconds: int = 0
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
    """Check if user has access to project (within their company) and return it"""
    # Multi-tenancy: join with team to filter by company
    query = select(Project).join(Team, Project.team_id == Team.id).where(Project.id == project_id)
    company_id = get_company_filter(user)
    query = apply_company_filter(query, Team.company_id, company_id)

    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        return None

    if user.role in ["super_admin", "admin", "company_admin"]:
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
def calculate_duration_seconds(start: datetime, end: datetime, pause_seconds: int = 0) -> int:
    """Return actual elapsed seconds between ``start`` and ``end``.

    B1: no 60-second clamp — short sessions stored verbatim. The 60s floor
    now lives on ``TimeEntryCreate.duration_seconds`` for explicit manual
    entries only.
    B14: defensively clamp negatives (clock skew, corrupted pause_seconds)
    so we never persist a negative duration.
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    total_elapsed = int((end - start).total_seconds())
    return max(0, total_elapsed - (pause_seconds or 0))


def make_entry_response(entry: TimeEntry, project_name: str = None, task_name: str = None, user_name: str = None, project_color: str = None) -> TimeEntryResponse:
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
        project_color=project_color,
        description=entry.description,
        start_time=entry.start_time,
        end_time=entry.end_time,
        duration_seconds=duration_seconds,
        duration_minutes=duration_minutes,
        is_running=entry.end_time is None,
        # Pause tracking for breaks/meetings
        is_paused=entry.is_paused or False,
        paused_at=entry.paused_at,
        pause_seconds=entry.pause_seconds or 0,
        created_at=entry.created_at
    )


@router.get("/timer", response_model=TimerStatus)
async def get_timer_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get current running timer status"""
    # Single eager-loaded query for session + meetings + breaks (used for orphan check AND meeting detection)
    session_result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.end_time.is_(None)
            )
        )
        .options(selectinload(WorkSession.meetings), selectinload(WorkSession.breaks))
    )
    active_session = session_result.scalar_one_or_none()

    # If no active session, there may still be orphan running TimeEntries
    # (rows with end_time IS NULL but no open WorkSession). Historically
    # we auto-closed them on every GET /timer. That silently mutated state
    # on a read and was a B14 finding. Now gated behind a feature flag
    # (default off) — when disabled we log + return the orphan as-is.
    if not active_session:
        orphan_result = await db.execute(
            select(TimeEntry)
            .where(TimeEntry.user_id == current_user.id, TimeEntry.end_time == None)
        )
        orphan_entries = orphan_result.scalars().all()
        if orphan_entries:
            if settings.TIMER_ORPHAN_AUTOCLOSE_ON_READ:
                now = datetime.now(timezone.utc)
                for entry in orphan_entries:
                    entry.end_time = now
                    entry.is_running = False
                    entry.is_paused = False
                    if entry.start_time:
                        entry.duration_seconds = calculate_duration_seconds(
                            entry.start_time, now, entry.pause_seconds or 0
                        )
                await db.commit()
            else:
                correlation_id = _uuid.uuid4().hex
                for entry in orphan_entries:
                    logger.warning(
                        "Orphan running time entry detected on GET /timer "
                        "(auto-close disabled). user_id=%s entry_id=%s "
                        "correlation_id=%s",
                        current_user.id,
                        entry.id,
                        correlation_id,
                    )
                # Return the first orphan running entry as-is so the client
                # still sees its active timer; no DB mutation.
                orphan = orphan_entries[0]
                project_name = None
                if orphan.project_id:
                    proj_r = await db.execute(
                        select(Project.name).where(Project.id == orphan.project_id)
                    )
                    project_name = proj_r.scalar()
                task_name = None
                if orphan.task_id:
                    task_r = await db.execute(
                        select(Task.name).where(Task.id == orphan.task_id)
                    )
                    task_name = task_r.scalar()
                now = datetime.now(timezone.utc)
                start = orphan.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                elapsed = max(0, int((now - start).total_seconds()) - (orphan.pause_seconds or 0))
                return TimerStatus(
                    is_running=True,
                    current_entry=make_entry_response(
                        orphan, project_name, task_name, current_user.name  # type: ignore[arg-type]
                    ),
                    elapsed_seconds=elapsed,
                )
        return TimerStatus(is_running=False)

    # Check if user is in a meeting — if so, find the PAUSED task entry, not the meeting entry
    # This way the frontend shows isPaused=true and the task timer freezes
    session_obj = active_session  # Reuse the same eager-loaded session

    in_meeting = False
    paused_entry_id = None
    if session_obj:
        for mtg in session_obj.meetings:
            if mtg.end_time is None:
                in_meeting = True
                paused_entry_id = mtg.paused_entry_id
                break

    if in_meeting and paused_entry_id:
        # Return the paused task entry so frontend shows isPaused=true
        paused_result = await db.execute(
            select(TimeEntry).where(TimeEntry.id == paused_entry_id)
        )
        paused_entry = paused_result.scalar_one_or_none()
        if paused_entry:
            # Get project/task names
            project_name = None
            if paused_entry.project_id:
                proj_r = await db.execute(select(Project.name).where(Project.id == paused_entry.project_id))
                project_name = proj_r.scalar()
            task_name = None
            if paused_entry.task_id:
                task_r = await db.execute(select(Task.name).where(Task.id == paused_entry.task_id))
                task_name = task_r.scalar()

            # Calculate elapsed from paused entry (it was stopped, so use its duration)
            elapsed = paused_entry.duration_seconds or 0

            # Build response — mark as paused so frontend freezes the task timer
            entry_resp = make_entry_response(paused_entry, project_name, task_name, current_user.name)
            # Override is_paused to true for the frontend
            entry_resp.is_paused = True
            entry_resp.is_running = True  # Still "running" conceptually, just paused

            return TimerStatus(
                is_running=True,
                current_entry=entry_resp,
                elapsed_seconds=elapsed
            )

    # Normal case: find running entry
    result = await db.execute(
        select(TimeEntry)
        .where(TimeEntry.user_id == current_user.id, TimeEntry.end_time == None)
        .order_by(TimeEntry.start_time.desc())
    )
    running_entry = result.scalar_one_or_none()

    if not running_entry:
        return TimerStatus(is_running=False)

    # Get project name (guard for null project_id — e.g. meeting entries)
    project_name = None
    if running_entry.project_id:
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
    # B14: clamp defensively — clock skew or corrupted pause_seconds must
    # never surface as a negative elapsed value to the client.
    elapsed = max(0, int((now - start).total_seconds()) - (running_entry.pause_seconds or 0))

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
    # Get company filter for multi-tenant data isolation
    company_filter = get_company_filter(current_user)

    # Build base query for active time entries with user, project, and task info
    query = (
        select(TimeEntry, User, Project, Task)
        .join(User, TimeEntry.user_id == User.id)
        .outerjoin(Project, TimeEntry.project_id == Project.id)
        .outerjoin(Task, TimeEntry.task_id == Task.id)
        .where(TimeEntry.end_time == None)
    )

    # Apply company filter using proper helper (handles FILTER_NULL_COMPANY sentinel)
    query = apply_company_filter(query, User.company_id, company_filter)

    query = query.order_by(TimeEntry.start_time.desc())
    result = await db.execute(query)

    rows = result.all()
    active_timers = []

    # Build a map of user_id -> (activity_state, break info, meeting info)
    # by joining each user's active WorkSession plus any open SessionBreak/SessionMeeting.
    user_ids = [user.id for _entry, user, _project, _task in rows]
    activity_by_user: dict[int, dict] = {}
    if user_ids:
        ws_q = (
            select(WorkSession)
            .where(
                WorkSession.user_id.in_(user_ids),
                WorkSession.end_time.is_(None),
            )
            .options(
                selectinload(WorkSession.breaks),
                selectinload(WorkSession.meetings),
            )
        )
        ws_rows = (await db.execute(ws_q)).scalars().all()
        for ws in ws_rows:
            state = "working"
            break_type = None
            meeting_type = None
            meeting_title = None
            # state_started_at is the moment the user entered the current
            # activity state (work / break / meeting). For "working" it is
            # left as None here and filled in below from the running
            # TimeEntry.start_time; for break/meeting it points at the
            # active SessionBreak/SessionMeeting.start_time so the panel
            # can display the duration of the current state.
            state_started_at = None
            if ws.status == "break":
                state = "break"
                for brk in ws.breaks:
                    if brk.end_time is None:
                        break_type = brk.break_type
                        state_started_at = brk.start_time
                        break
            elif ws.status == "meeting":
                state = "meeting"
                for mtg in ws.meetings:
                    if mtg.end_time is None:
                        meeting_type = mtg.meeting_type
                        meeting_title = mtg.title
                        state_started_at = mtg.start_time
                        break
            activity_by_user[ws.user_id] = {
                "activity_state": state,
                "break_type": break_type,
                "meeting_type": meeting_type,
                "meeting_title": meeting_title,
                "state_started_at": state_started_at,
            }

    for entry, user, project, task in rows:
        # Calculate elapsed seconds. While the entry is paused (user on
        # break) this freezes at paused_at so the panel matches the user's
        # own timer widget; otherwise it counts forward from start_time
        # minus any accumulated pause time.
        elapsed = compute_display_elapsed_seconds(entry)

        activity = activity_by_user.get(user.id) or {
            "activity_state": "working",
            "break_type": None,
            "meeting_type": None,
            "meeting_title": None,
            "state_started_at": None,
        }

        # Anchor the panel's displayed duration to the moment the current
        # activity state began. For "working" this is the TimeEntry's own
        # start_time; for break/meeting it's the active row's start_time.
        state_started_at = activity.get("state_started_at") or entry.start_time
        if activity["activity_state"] == "working":
            # Mirror the existing pause-aware reading so working users see
            # the same number on the panel as on their own timer widget.
            state_elapsed = elapsed
        else:
            state_elapsed = compute_state_elapsed_seconds(state_started_at)

        active_timers.append({
            "user_id": user.id,
            "user_name": user.name,
            "project_id": project.id if project else None,
            "project_name": project.name if project else None,
            "task_id": task.id if task else None,
            "task_name": task.name if task else None,
            "description": entry.description,
            "start_time": entry.start_time.isoformat(),
            "elapsed_seconds": elapsed,
            "state_started_at": state_started_at.isoformat(),
            "state_elapsed_seconds": state_elapsed,
            "activity_state": activity["activity_state"],
            "break_type": activity["break_type"],
            "meeting_type": activity["meeting_type"],
            "meeting_title": activity["meeting_title"],
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

    resolved_description = await resolve_description(
        description=entry_data.description,
        task_id=entry_data.task_id,
        db=db,
    )

    entry = TimeEntry(
        user_id=current_user.id,
        task_id=entry_data.task_id,
        project_id=entry_data.project_id,
        description=resolved_description,
        start_time=datetime.now(timezone.utc),
        end_time=None,
        duration_seconds=None,
        is_running=True
    )

    # === MICRO-TASK INTEGRATION: Link timer to work session ===
    # Find or create active work session for this user
    session_result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.end_time.is_(None)
            )
        )
    )
    active_session = session_result.scalar_one_or_none()

    if not active_session:
        # Auto-create session when starting first timer of the day
        active_session = WorkSession(
            user_id=current_user.id,
            company_id=current_user.company_id,
            status="active",
        )
        db.add(active_session)
        await db.flush()  # Get the ID without committing

    # Link time entry to session
    entry.work_session_id = active_session.id
    # === END MICRO-TASK INTEGRATION ===

    db.add(entry)
    # B2: the SELECT above is racy — two concurrent requests can both see
    # "no running timer" and try to INSERT. The unique partial index
    # ``ux_time_entries_one_running_per_user`` (migration
    # 021_unique_running_timer) makes the DB the source of truth. The
    # second concurrent INSERT raises IntegrityError; convert to 409.
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A timer is already running for this user.",
        ) from exc
    await db.refresh(entry)

    # Broadcast timer start to SAME COMPANY ONLY for real-time "Who's Working Now" updates
    await ws_manager.broadcast_to_company({
        "type": "timer_started",
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
            "is_running": True
        }
    }, company_id=current_user.company_id)

    # Update the WebSocket manager's active timers cache
    ws_manager.set_active_timer(current_user.id, {
        "user_name": current_user.name,
        "company_id": current_user.company_id,  # For multi-tenant filtering
        "project_id": entry.project_id,
        "project_name": project.name,
        "task_id": entry.task_id,
        "task_name": task_name,
        "description": entry.description,
        "start_time": entry.start_time.isoformat()
    })

    return make_entry_response(entry, project.name, task_name, current_user.name, project_color=project.color)


@router.post("/stop", response_model=TimeEntryResponse)
async def stop_timer(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Stop the running timer"""
    # Guard: block stop during active meeting or break (must end those first)
    guard_session_result = await db.execute(
        select(WorkSession)
        .where(and_(WorkSession.user_id == current_user.id, WorkSession.end_time.is_(None)))
        .options(selectinload(WorkSession.meetings), selectinload(WorkSession.breaks))
    )
    guard_session = guard_session_result.scalar_one_or_none()
    if guard_session:
        for mtg in guard_session.meetings:
            if mtg.end_time is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot stop timer during a meeting. End the meeting first."
                )
        for brk in guard_session.breaks:
            if brk.end_time is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot stop timer during a break. End the break first."
                )

    result = await db.execute(
        select(TimeEntry).where(TimeEntry.user_id == current_user.id, TimeEntry.end_time == None)
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No running timer found")

    # Stop the timer
    end_time = datetime.now(timezone.utc)
    entry.end_time = end_time
    entry.duration_seconds = calculate_duration_seconds(entry.start_time, end_time, entry.pause_seconds or 0)
    entry.is_running = False

    await db.commit()
    await db.refresh(entry)

    # Get names (guard for null project_id — e.g. meeting entries)
    project_name = None
    if entry.project_id:
        project_result = await db.execute(select(Project.name).where(Project.id == entry.project_id))
        project_name = project_result.scalar()

    task_name = None
    if entry.task_id:
        task_result = await db.execute(select(Task.name).where(Task.id == entry.task_id))
        task_name = task_result.scalar()

    # Broadcast timer stopped to SAME COMPANY for real-time "Who's Working Now" updates
    await ws_manager.broadcast_to_company({
        "type": "timer_stopped",
        "data": {
            "user_id": current_user.id,
            "user_name": current_user.name,
            "project_name": project_name,
            "task_name": task_name,
            "duration_seconds": entry.duration_seconds
        }
    }, company_id=current_user.company_id)

    # Clear the WebSocket manager's active timer cache for this user
    ws_manager.clear_active_timer(current_user.id)

    # Also broadcast time entry completion for reports update (SAME COMPANY ONLY)
    await ws_manager.broadcast_to_company({
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
    }, company_id=current_user.company_id)

    return make_entry_response(entry, project_name, task_name, current_user.name)


# ============================================
# TASK SWITCHING ENDPOINT
# ============================================

class TaskSwitchRequest(BaseModel):
    """Request body for switching tasks while timer keeps running."""
    project_id: int
    task_id: Optional[int] = None
    description: Optional[str] = None


@router.post("/switch", response_model=TimeEntryResponse)
async def switch_task(
    switch_data: TaskSwitchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Switch to a different project/task without stopping the session clock.

    This atomically:
    1. Stops the current running time entry (finalizes its duration)
    2. Starts a new time entry with the new project/task
    3. Links the new entry to the same work session

    The work session (Clock In) keeps running — only the task timer resets.
    """
    now = datetime.now(timezone.utc)

    # Guard: block switch during active meeting or break (must end those first)
    guard_session_result = await db.execute(
        select(WorkSession)
        .where(and_(WorkSession.user_id == current_user.id, WorkSession.end_time.is_(None)))
        .options(selectinload(WorkSession.meetings), selectinload(WorkSession.breaks))
    )
    guard_session = guard_session_result.scalar_one_or_none()
    if guard_session:
        for mtg in guard_session.meetings:
            if mtg.end_time is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot switch tasks during a meeting. End the meeting first."
                )
        for brk in guard_session.breaks:
            if brk.end_time is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot switch tasks during a break. End the break first."
                )

    # 1. Find and stop the current running entry
    result = await db.execute(
        select(TimeEntry).where(
            TimeEntry.user_id == current_user.id,
            TimeEntry.end_time == None
        )
    )
    old_entry = result.scalar_one_or_none()

    if not old_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No running timer to switch from. Start a timer first."
        )

    # 2. Validate the new project
    new_project = await check_project_access(db, switch_data.project_id, current_user)
    if not new_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied"
        )

    # 3. Validate the new task (if provided)
    new_task_name = None
    if switch_data.task_id:
        task_result = await db.execute(
            select(Task).where(
                Task.id == switch_data.task_id,
                Task.project_id == switch_data.project_id
            )
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task not found in this project"
            )
        new_task_name = task.name

    # 4. Stop the old entry
    old_entry.end_time = now
    old_entry.is_running = False
    old_entry.is_paused = False
    if old_entry.start_time:
        old_entry.duration_seconds = calculate_duration_seconds(old_entry.start_time, now, old_entry.pause_seconds or 0)

    # 5. Create the new entry linked to the same work session
    resolved_description = await resolve_description(
        description=switch_data.description,
        task_id=switch_data.task_id,
        db=db,
    )

    new_entry = TimeEntry(
        user_id=current_user.id,
        project_id=switch_data.project_id,
        task_id=switch_data.task_id,
        description=resolved_description,
        start_time=now,
        end_time=None,
        duration_seconds=None,
        is_running=True,
        is_paused=False,
        pause_seconds=0,
        work_session_id=old_entry.work_session_id,  # Keep same session!
    )
    db.add(new_entry)

    await db.commit()
    await db.refresh(new_entry)

    # 6. Broadcast task switch to company
    await ws_manager.broadcast_to_company({
        "type": "timer_started",
        "data": {
            "entry_id": new_entry.id,
            "user_id": current_user.id,
            "user_name": current_user.name,
            "project_id": new_entry.project_id,
            "project_name": new_project.name,
            "task_id": new_entry.task_id,
            "task_name": new_task_name,
            "description": new_entry.description,
            "start_time": new_entry.start_time.isoformat(),
            "is_running": True
        }
    }, company_id=current_user.company_id)

    # Update WebSocket active timer cache
    ws_manager.set_active_timer(current_user.id, {
        "user_name": current_user.name,
        "company_id": current_user.company_id,
        "project_id": new_entry.project_id,
        "project_name": new_project.name,
        "task_id": new_entry.task_id,
        "task_name": new_task_name,
        "description": new_entry.description,
        "start_time": new_entry.start_time.isoformat()
    })

    return make_entry_response(new_entry, new_project.name, new_task_name, current_user.name, project_color=new_project.color)


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

    # Broadcast manual time entry creation to SAME COMPANY for real-time reports update
    await ws_manager.broadcast_to_company({
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
    }, company_id=current_user.company_id)

    return make_entry_response(entry, project.name, task_name, current_user.name, project_color=project.color)


@router.get("", response_model=PaginatedTimeEntries)
async def list_time_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    project_id: Optional[int] = None,
    task_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    tz: str = Depends(get_company_timezone),
):
    """List time entries (filtered by company for multi-tenancy)"""
    # Multi-tenancy: join with user to filter by company.
    # B23: ``count_query`` and ``sum_query`` are merged into a single
    # aggregate ``stats_query`` so the endpoint issues exactly two
    # round-trips: one for total/sum, one for the rows + eager-loaded
    # project/task/user via joinedload (has-one, no Cartesian risk).
    base_query = select(TimeEntry).join(User, TimeEntry.user_id == User.id)
    stats_query = select(
        func.count(TimeEntry.id),
        func.coalesce(func.sum(TimeEntry.duration_seconds), 0),
    ).join(User, TimeEntry.user_id == User.id)

    # Multi-tenancy: filter by company
    company_id = get_company_filter(current_user)
    base_query = apply_company_filter(base_query, User.company_id, company_id)
    stats_query = apply_company_filter(stats_query, User.company_id, company_id)

    # Filter by user (regular users see only their entries, admin sees all in company)
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        if user_id and user_id != current_user.id:
            # B29: explicit user_id from a non-admin must reference a teammate.
            # Previously, a non-shared user_id silently produced an empty 200
            # response; that is an information-leakage smell and is now a 403.
            user_teams = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
            shared_team_check = await db.execute(
                select(TeamMember.user_id)
                .where(
                    TeamMember.team_id.in_(user_teams),
                    TeamMember.user_id == user_id,
                )
                .limit(1)
            )
            if shared_team_check.first() is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to view this user's time entries.",
                )
            # Authorized: scope visible rows to self OR teammates (the
            # subsequent ``user_id`` filter below narrows further to the
            # requested user).
            team_users = select(TeamMember.user_id).where(TeamMember.team_id.in_(user_teams))
            base_query = base_query.where(
                (TimeEntry.user_id == current_user.id) | (TimeEntry.user_id.in_(team_users))
            )
            stats_query = stats_query.where(
                (TimeEntry.user_id == current_user.id) | (TimeEntry.user_id.in_(team_users))
            )
        elif not user_id:
            base_query = base_query.where(TimeEntry.user_id == current_user.id)
            stats_query = stats_query.where(TimeEntry.user_id == current_user.id)

    if user_id:
        base_query = base_query.where(TimeEntry.user_id == user_id)
        stats_query = stats_query.where(TimeEntry.user_id == user_id)

    if project_id:
        base_query = base_query.where(TimeEntry.project_id == project_id)
        stats_query = stats_query.where(TimeEntry.project_id == project_id)

    if task_id:
        base_query = base_query.where(TimeEntry.task_id == task_id)
        stats_query = stats_query.where(TimeEntry.task_id == task_id)

    if start_date:
        # B7: tenant-local midnight as half-open range start.
        start_datetime, _ = day_bounds(start_date, tz)
        base_query = base_query.where(TimeEntry.start_time >= start_datetime)
        stats_query = stats_query.where(TimeEntry.start_time >= start_datetime)

    if end_date:
        # B7+B20: half-open range [start_of_local_day, next_local_day_midnight).
        # Matches reports.py and avoids both the microsecond cliff of
        # datetime.max.time() and the UTC-vs-local mismatch.
        _, end_datetime = day_bounds(end_date, tz)
        base_query = base_query.where(TimeEntry.start_time < end_datetime)
        stats_query = stats_query.where(TimeEntry.start_time < end_datetime)

    # Get aggregate stats (count + sum) in a single round trip.
    stats_result = await db.execute(stats_query)
    total, total_seconds = stats_result.one()
    total = total or 0
    total_seconds = total_seconds or 0

    # Get paginated results.
    # B23: eager-load project/task/user via joinedload. All three are
    # has-one (many-to-one from TimeEntry), so a single LEFT OUTER JOIN
    # is safe (no Cartesian explosion) and yields the rows + names in
    # one query. Combined with the merged stats query above, the
    # endpoint now issues exactly two SQL statements regardless of page
    # size. The response shape is unchanged.
    offset = (page - 1) * page_size
    query = (
        base_query
        .options(
            joinedload(TimeEntry.project),
            joinedload(TimeEntry.task),
            joinedload(TimeEntry.user),
        )
        .offset(offset)
        .limit(page_size)
        .order_by(TimeEntry.start_time.desc())
    )
    result = await db.execute(query)
    entries = result.scalars().all()

    items = [
        make_entry_response(
            entry,
            entry.project.name if entry.project else None,
            entry.task.name if entry.task else None,
            entry.user.name if entry.user else None,
            project_color=entry.project.color if entry.project else None,
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
    """Get time entry details with multi-tenant validation"""
    # Get company filter for multi-tenant data isolation
    company_filter = get_company_filter(current_user)

    # Query with company filter to ensure we only access our company's entries
    query = (
        select(TimeEntry)
        .join(User, TimeEntry.user_id == User.id)
        .where(TimeEntry.id == entry_id)
    )
    query = apply_company_filter(query, User.company_id, company_filter)

    result = await db.execute(query)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time entry not found or access denied")

    # Check access - users can only see their own entries unless admin/company_admin
    if current_user.role not in ["super_admin", "admin", "company_admin"] and entry.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Get names (guard for null project_id — e.g. meeting entries)
    project_name = None
    project_color = None
    if entry.project_id:
        project_result = await db.execute(
            select(Project.name, Project.color).where(Project.id == entry.project_id)
        )
        row = project_result.first()
        if row is not None:
            project_name, project_color = row

    task_name = None
    if entry.task_id:
        task_result = await db.execute(select(Task.name).where(Task.id == entry.task_id))
        task_name = task_result.scalar()

    user_result = await db.execute(select(User.name).where(User.id == entry.user_id))
    user_name = user_result.scalar()

    return make_entry_response(entry, project_name, task_name, user_name, project_color=project_color)


@router.put("/{entry_id}", response_model=TimeEntryResponse)
async def update_time_entry(
    entry_id: int,
    entry_data: TimeEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update time entry with multi-tenant validation"""
    # Get company filter for multi-tenant data isolation
    company_filter = get_company_filter(current_user)

    # Query with company filter to ensure we only access our company's entries
    query = (
        select(TimeEntry)
        .join(User, TimeEntry.user_id == User.id)
        .where(TimeEntry.id == entry_id)
    )
    query = apply_company_filter(query, User.company_id, company_filter)

    result = await db.execute(query)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time entry not found or access denied")

    # Only owner can update (super_admin only allowed within their own company now)
    if entry.user_id != current_user.id and current_user.role not in ["super_admin", "admin", "company_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only update your own entries")

    if entry_data.description is not None:
        entry.description = entry_data.description

    if entry_data.start_time is not None:
        entry.start_time = entry_data.start_time

    if entry_data.end_time is not None:
        entry.end_time = entry_data.end_time

    # B3: after applying any partial update, validate chronology against
    # the merged state. The schema model_validator already rejects payloads
    # that carry both fields out of order; this handles the case where only
    # one field is updated and the other comes from the existing row. We
    # raise 400 here — clearer than relying on the DB CHECK constraint.
    if entry.end_time is not None and entry.start_time is not None:
        start = entry.start_time
        end = entry.end_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end < start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_time must be greater than or equal to start_time",
            )

    if entry_data.project_id is not None:
        # Verify project exists and belongs to same company
        project_result = await db.execute(
            select(Project).where(Project.id == entry_data.project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        entry.project_id = entry_data.project_id
        # Clear task if project changed (task may not belong to new project)
        if entry_data.task_id is None:
            entry.task_id = None

    if entry_data.task_id is not None:
        # Verify task exists and belongs to the project
        task_result = await db.execute(
            select(Task).where(Task.id == entry_data.task_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        if task.project_id != (entry_data.project_id or entry.project_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task does not belong to the selected project")
        entry.task_id = entry_data.task_id
    elif entry_data.task_id == 0 or (entry_data.project_id is not None and entry_data.task_id is None):
        # Allow clearing task by setting to None
        pass  # task_id already handled above

    # Recalculate duration if times changed
    if entry.end_time:
        entry.duration_seconds = calculate_duration_seconds(entry.start_time, entry.end_time)
        entry.is_running = False

    entry.description = await resolve_description(
        description=entry.description,
        task_id=entry.task_id,
        db=db,
    )

    await db.commit()
    await db.refresh(entry)

    # Get names (guard for null project_id — e.g. meeting entries)
    project_name = None
    if entry.project_id:
        project_result = await db.execute(select(Project.name).where(Project.id == entry.project_id))
        project_name = project_result.scalar()

    task_name = None
    if entry.task_id:
        task_result = await db.execute(select(Task.name).where(Task.id == entry.task_id))
        task_name = task_result.scalar()

    # Broadcast time entry update to SAME COMPANY for real-time reports update
    await ws_manager.broadcast_to_company({
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
    }, company_id=current_user.company_id)

    return make_entry_response(entry, project_name, task_name, current_user.name)


@router.patch("/entries/{entry_id}", response_model=TimeEntryResponse)
async def patch_time_entry(
    entry_id: int,
    entry_data: TimeEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Edit a time entry the current user owns.

    Personal-scope endpoint: ownership is enforced strictly even for
    admins. Validation order is fail-fast:

      1. Existence (404)
      2. Ownership (403)
      3. Running-timer guards (400) — start_time and end_time edits are
         rejected; the user must use ``/stop`` first.
      4. Time logic (400) — end > start, end <= now() + 5 min.
      5. Project access (404 / 403) — only when project_id is changing.
      6. Task validity (404 / 400) — task must belong to the resulting
         project_id.
      7. Description max length is enforced at the schema layer (422).
    """
    # 1. Existence
    result = await db.execute(
        select(TimeEntry).where(TimeEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time entry not found",
        )

    # 2. Ownership — admins are NOT exempt on this personal-scope endpoint.
    if entry.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own time entries",
        )

    is_running = entry.end_time is None

    # 3. Running-timer guards
    if is_running:
        if entry_data.start_time is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stop the timer before editing its start time.",
            )
        if entry_data.end_time is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stop the timer first via the Stop button before editing it.",
            )

    # 4. Time logic — validate against the resulting (start, end) pair.
    new_start = entry_data.start_time if entry_data.start_time is not None else entry.start_time
    new_end = entry_data.end_time if entry_data.end_time is not None else entry.end_time

    if entry_data.start_time is not None or entry_data.end_time is not None:
        if new_start is not None and new_start.tzinfo is None:
            new_start = new_start.replace(tzinfo=timezone.utc)
        if new_end is not None and new_end.tzinfo is None:
            new_end = new_end.replace(tzinfo=timezone.utc)

        if new_end is not None and new_start is not None:
            if new_end <= new_start:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_time must be greater than start_time",
                )
            now = datetime.now(timezone.utc)
            if new_end > now + timedelta(minutes=5):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_time cannot be in the future",
                )

    # 5. Project access — only validate when project_id is provided AND changing.
    target_project_id = entry.project_id
    if entry_data.project_id is not None and entry_data.project_id != entry.project_id:
        project = await check_project_access(db, entry_data.project_id, current_user)
        if not project:
            # Distinguish "doesn't exist" from "no access".
            exists_result = await db.execute(
                select(Project.id).where(Project.id == entry_data.project_id)
            )
            if exists_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this project",
            )
        target_project_id = entry_data.project_id

    # 6. Task validity
    target_task_id = entry.task_id
    if entry_data.task_id is not None:
        task_result = await db.execute(
            select(Task).where(Task.id == entry_data.task_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            )
        if task.project_id != target_project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task does not belong to the selected project",
            )
        target_task_id = entry_data.task_id

    # All validations passed — apply changes.
    if entry_data.description is not None:
        entry.description = entry_data.description
    if entry_data.start_time is not None:
        entry.start_time = new_start
    if entry_data.end_time is not None:
        entry.end_time = new_end
    if entry_data.project_id is not None:
        entry.project_id = target_project_id
    if entry_data.task_id is not None:
        entry.task_id = target_task_id

    # Recompute duration when the entry is closed.
    if entry.end_time is not None:
        entry.duration_seconds = calculate_duration_seconds(
            entry.start_time,
            entry.end_time,
            entry.pause_seconds or 0,
        )
        entry.is_running = False

    entry.description = await resolve_description(
        description=entry.description,
        task_id=entry.task_id,
        db=db,
    )

    await db.commit()
    await db.refresh(entry)

    project_name = None
    if entry.project_id:
        project_name_result = await db.execute(
            select(Project.name).where(Project.id == entry.project_id)
        )
        project_name = project_name_result.scalar()

    task_name = None
    if entry.task_id:
        task_name_result = await db.execute(
            select(Task.name).where(Task.id == entry.task_id)
        )
        task_name = task_name_result.scalar()

    # Broadcast update for real-time reports refresh (same pattern as PUT).
    await ws_manager.broadcast_to_company(
        {
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
                "is_running": entry.is_running,
            },
        },
        company_id=current_user.company_id,
    )

    return make_entry_response(entry, project_name, task_name, current_user.name)


@router.delete("/{entry_id}", response_model=Message)
async def delete_time_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete time entry with multi-tenant validation"""
    # Get company filter for multi-tenant data isolation
    company_filter = get_company_filter(current_user)

    # Query with company filter to ensure we only access our company's entries
    query = (
        select(TimeEntry)
        .join(User, TimeEntry.user_id == User.id)
        .where(TimeEntry.id == entry_id)
    )
    query = apply_company_filter(query, User.company_id, company_filter)

    result = await db.execute(query)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time entry not found or access denied")

    # Only owner can delete (admins within company can delete)
    if entry.user_id != current_user.id and current_user.role not in ["super_admin", "admin", "company_admin"]:
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

    # Broadcast time entry deletion to SAME COMPANY for real-time reports update
    await ws_manager.broadcast_to_company({
        "type": "time_entry_deleted",
        "data": entry_data
    }, company_id=current_user.company_id)

    return {"message": "Time entry deleted successfully"}

