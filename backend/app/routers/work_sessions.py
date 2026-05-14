"""
Work Session Management API Endpoints.

Handles work sessions, breaks, and meetings for the Micro-Task Management feature.

Key concepts:
- WorkSession: A user's work day/period (start work → end work)
- SessionBreak: Break periods that pause BOTH global and task timers
- SessionMeeting: Meeting periods that pause ONLY task timer (global keeps running)

Timer behavior:
- Global timer: Tracks total work time for the day (minus breaks)
- Task timer: Tracks time on current task (pauses for breaks AND meetings)
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_company_timezone, get_current_active_user
from app.models import SessionBreak, SessionMeeting, TimeEntry, User, WorkSession
from app.routers.websocket import manager as ws_manager
from app.schemas.sessions import (
    DailySessionReport,
    SessionBreakCreate,
    SessionBreakResponse,
    SessionMeetingCreate,
    SessionMeetingResponse,
    SessionStatusResponse,
    SessionSummary,
    WorkSessionResponse,
    WorkSessionWithDetails,
)
from app.utils.timewindow import day_bounds, local_today, range_bounds

router = APIRouter(prefix="/api/work-sessions", tags=["work-sessions"])


# ============================================
# HELPER FUNCTIONS
# ============================================

async def get_active_session(db: AsyncSession, user_id: int) -> Optional[WorkSession]:
    """Get user's active work session (if any)."""
    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == user_id,
                WorkSession.end_time.is_(None)
            )
        )
        .options(
            selectinload(WorkSession.breaks),
            selectinload(WorkSession.meetings),
            selectinload(WorkSession.time_entries)
        )
    )
    return result.scalar_one_or_none()


def _activity_payload(state: str, *, break_type: Optional[str] = None,
                       meeting_type: Optional[str] = None,
                       meeting_title: Optional[str] = None) -> dict:
    """Build the activity-state subset of an active-timer cache entry."""
    return {
        "activity_state": state,
        "break_type": break_type if state == "break" else None,
        "meeting_type": meeting_type if state == "meeting" else None,
        "meeting_title": meeting_title if state == "meeting" else None,
    }


async def _refresh_active_timer_cache(
    db: AsyncSession,
    user: User,
    activity: dict,
) -> Optional[dict]:
    """Rebuild and broadcast the active-timer cache entry for ``user``.

    Looks up the user's currently-open TimeEntry (if any) and merges the
    given activity payload (state/break_type/meeting_*) into the entry
    cached in ``ws_manager.active_timers``. Then emits ``timer_updated``
    so the "Who's Working Now" panel can mutate locally without a full
    snapshot refresh.

    Returns the new cache entry, or ``None`` if no open entry exists.
    """
    from app.models import Project, Task

    stmt = (
        select(TimeEntry, Project, Task)
        .outerjoin(Project, TimeEntry.project_id == Project.id)
        .outerjoin(Task, TimeEntry.task_id == Task.id)
        .where(
            TimeEntry.user_id == user.id,
            TimeEntry.end_time.is_(None),
        )
        .order_by(TimeEntry.start_time.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        ws_manager.clear_active_timer(user.id)
        return None

    entry, project, task = row
    start = entry.start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    elapsed = int((datetime.now(timezone.utc) - start).total_seconds())

    timer_entry = {
        "user_id": user.id,
        "user_name": user.name,
        "company_id": user.company_id,
        "project_id": project.id if project else None,
        "project_name": project.name if project else ("Meeting" if entry.project_id is None else None),
        "task_id": task.id if task else None,
        "task_name": task.name if task else None,
        "description": entry.description,
        "start_time": entry.start_time.isoformat(),
        "elapsed_seconds": elapsed,
        **activity,
    }
    ws_manager.set_active_timer(user.id, timer_entry)
    await ws_manager.broadcast_timer_updated(
        company_id=user.company_id,
        timer_entry=ws_manager.active_timers.get(user.id, timer_entry),
    )
    return timer_entry


# ============================================
# SESSION STATUS ENDPOINT
# ============================================

@router.get("/current", response_model=SessionStatusResponse)
async def get_current_session(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current user's active work session status.

    Returns comprehensive status including:
    - Whether user has an active session
    - Current status (working, break, meeting, idle)
    - Timer values for global and task timers
    - Current break/meeting details if applicable
    """
    session = await get_active_session(db, current_user.id)

    if not session:
        return SessionStatusResponse(
            has_active_session=False,
            session=None,
            current_status="idle",
            global_timer_seconds=0,
            task_timer_seconds=0,
        )

    # Calculate current elapsed time
    now = datetime.now(timezone.utc)
    elapsed_seconds = int((now - session.start_time).total_seconds())

    # Determine current status and find active break/meeting
    current_break = None
    current_meeting = None
    current_status = "working"

    for brk in session.breaks:
        if brk.end_time is None:
            current_break = brk
            current_status = "break"
            break

    if current_status != "break":
        for mtg in session.meetings:
            if mtg.end_time is None:
                current_meeting = mtg
                current_status = "meeting"
                break

    # Calculate task timer (from running time entry)
    task_timer_seconds = 0
    for entry in session.time_entries:
        if entry.is_running and not entry.is_paused:
            task_timer_seconds = int((now - entry.start_time).total_seconds()) - entry.pause_seconds

    # Global timer = elapsed - breaks only (meetings count as work time)
    global_timer_seconds = elapsed_seconds - session.total_break_seconds

    # If currently on break, subtract current break duration too
    if current_break:
        current_break_duration = int((now - current_break.start_time).total_seconds())
        global_timer_seconds -= current_break_duration

    return SessionStatusResponse(
        has_active_session=True,
        session=WorkSessionResponse.model_validate(session),
        current_status=current_status,
        global_timer_seconds=max(0, global_timer_seconds),
        task_timer_seconds=max(0, task_timer_seconds),
        current_break=SessionBreakResponse.model_validate(current_break) if current_break else None,
        current_meeting=SessionMeetingResponse.model_validate(current_meeting) if current_meeting else None,
    )


# ============================================
# SESSION MANAGEMENT ENDPOINTS
# ============================================

@router.post("/start", response_model=WorkSessionResponse)
async def start_session(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new work session (clock in for the day).

    A user can only have one active session at a time.
    """
    # Check if already has active session
    existing = await get_active_session(db, current_user.id)

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active work session. End it first."
        )

    # Create new session
    session = WorkSession(
        user_id=current_user.id,
        company_id=current_user.company_id,
        status="active",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Broadcast session started to company
    await ws_manager.broadcast_session_started(
        company_id=current_user.company_id,
        user_id=current_user.id,
        user_name=current_user.name,
        session_data={
            "session_id": session.id,
            "start_time": session.start_time.isoformat(),
            "status": session.status
        }
    )

    return WorkSessionResponse.model_validate(session)


@router.post("/end", response_model=WorkSessionResponse)
async def end_session(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    End the current work session (clock out for the day).

    This will:
    - Stop any running time entries
    - End any active breaks or meetings
    - Calculate total work/break/meeting time
    - Mark session as completed
    """
    session = await get_active_session(db, current_user.id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active work session found."
        )

    now = datetime.now(timezone.utc)

    # Stop any running time entries linked to this session
    for entry in session.time_entries:
        if entry.end_time is None:
            entry.end_time = now
            entry.is_running = False
            entry.is_paused = False
            end_time = entry.end_time  # Capture for type checker
            if entry.start_time and end_time:
                total_elapsed = int((end_time - entry.start_time).total_seconds())
                entry.duration_seconds = total_elapsed - (entry.pause_seconds or 0)

    # ALSO stop any orphaned running entries for this user (entries without session_id)
    # This ensures all timers stop when user clocks out
    orphan_result = await db.execute(
        select(TimeEntry).where(
            and_(
                TimeEntry.user_id == current_user.id,
                TimeEntry.end_time.is_(None),
                TimeEntry.work_session_id.is_(None)  # Not linked to any session
            )
        )
    )
    orphan_entries = orphan_result.scalars().all()
    for entry in orphan_entries:
        entry.end_time = now
        entry.is_running = False
        entry.is_paused = False
        end_time = entry.end_time  # Capture for type checker
        if entry.start_time and end_time:
            total_elapsed = int((end_time - entry.start_time).total_seconds())
            entry.duration_seconds = total_elapsed - (entry.pause_seconds or 0)

    # End any active breaks
    for brk in session.breaks:
        if brk.end_time is None:
            brk.end_time = now
            if brk.start_time:
                brk.duration_seconds = int((now - brk.start_time).total_seconds())
                session.total_break_seconds += brk.duration_seconds

    # End any active meetings
    for mtg in session.meetings:
        if mtg.end_time is None:
            mtg.end_time = now
            if mtg.start_time:
                mtg.duration_seconds = int((now - mtg.start_time).total_seconds())
                session.total_meeting_seconds += mtg.duration_seconds

    # Calculate totals
    session.end_time = now
    session.status = "completed"
    session.total_work_seconds = sum(
        (e.duration_seconds or 0) for e in session.time_entries
    )

    await db.commit()
    await db.refresh(session)

    # Broadcast session ended to company
    await ws_manager.broadcast_session_ended(
        company_id=current_user.company_id,
        user_id=current_user.id,
        user_name=current_user.name,
        session_data={
            "session_id": session.id,
            "end_time": now.isoformat(),
            "total_work_seconds": session.total_work_seconds,
            "total_break_seconds": session.total_break_seconds,
            "total_meeting_seconds": session.total_meeting_seconds,
            "status": session.status
        }
    )

    return WorkSessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=WorkSessionWithDetails)
async def get_session_details(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific work session."""
    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.id == session_id,
                WorkSession.user_id == current_user.id
            )
        )
        .options(
            selectinload(WorkSession.breaks),
            selectinload(WorkSession.meetings)
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work session not found."
        )

    return WorkSessionWithDetails.model_validate(session)


# ============================================
# BREAK ENDPOINTS
# ============================================

@router.post("/break/start", response_model=SessionBreakResponse)
async def start_break(
    break_data: SessionBreakCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a break (pauses BOTH global and task timers).

    Break types:
    - "short": Quick break (5-15 mins)
    - "lunch": Lunch break (30-60 mins)
    - "other": Other break type
    """
    session = await get_active_session(db, current_user.id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active work session. Start a session first."
        )

    # Check no active break already
    for brk in session.breaks:
        if brk.end_time is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an active break."
            )

    # Check no active meeting (can't start break during meeting)
    for mtg in session.meetings:
        if mtg.end_time is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End your meeting before starting a break."
            )

    # Pause any running time entry
    now = datetime.now(timezone.utc)
    for entry in session.time_entries:
        if entry.is_running and not entry.is_paused:
            entry.is_paused = True
            entry.paused_at = now

    # Update session status
    session.status = "break"

    # Create break record
    new_break = SessionBreak(
        work_session_id=session.id,
        break_type=break_data.break_type,
        start_time=now,
    )
    db.add(new_break)
    await db.commit()
    await db.refresh(new_break)

    # Broadcast break started to company
    await ws_manager.broadcast_break_started(
        company_id=current_user.company_id,
        user_id=current_user.id,
        user_name=current_user.name,
        break_data={
            "break_id": new_break.id,
            "break_type": new_break.break_type,
            "start_time": new_break.start_time.isoformat()
        }
    )

    # Refresh the active-timer cache so "Who's Working Now" shows the break state.
    await _refresh_active_timer_cache(
        db,
        current_user,
        _activity_payload("break", break_type=new_break.break_type),
    )

    return SessionBreakResponse.model_validate(new_break)


@router.post("/break/end", response_model=SessionBreakResponse)
async def end_break(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    End the current break (resumes BOTH global and task timers).
    """
    session = await get_active_session(db, current_user.id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active work session found."
        )

    # Find active break
    active_break = None
    for brk in session.breaks:
        if brk.end_time is None:
            active_break = brk
            break

    if not active_break:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active break to end."
        )

    # End the break
    now = datetime.now(timezone.utc)
    active_break.end_time = now
    active_break.duration_seconds = int((now - active_break.start_time).total_seconds())

    # Update session totals
    session.total_break_seconds += active_break.duration_seconds
    session.status = "active"

    # Resume paused time entries
    for entry in session.time_entries:
        if entry.is_paused:
            entry.is_paused = False
            if entry.paused_at:
                entry.pause_seconds += int((now - entry.paused_at).total_seconds())
            entry.paused_at = None

    await db.commit()
    await db.refresh(active_break)

    # Broadcast break ended to company
    await ws_manager.broadcast_break_ended(
        company_id=current_user.company_id,
        user_id=current_user.id,
        user_name=current_user.name,
        break_data={
            "break_id": active_break.id,
            "break_type": active_break.break_type,
            "duration_seconds": active_break.duration_seconds,
            "end_time": now.isoformat()
        }
    )

    # Restore working state in the active-timer cache.
    await _refresh_active_timer_cache(
        db,
        current_user,
        _activity_payload("working"),
    )

    return SessionBreakResponse.model_validate(active_break)


# ============================================
# MEETING ENDPOINTS
# ============================================

@router.post("/meeting/start", response_model=SessionMeetingResponse)
async def start_meeting(
    meeting_data: SessionMeetingCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a meeting (pauses task timer, creates meeting time entry).

    Meeting types:
    - "internal": Internal team meeting
    - "external": External meeting
    - "client": Client meeting

    This will:
    1. Pause any running time entry
    2. Create a new time entry for the meeting
    3. The meeting time entry will show in reports
    """
    session = await get_active_session(db, current_user.id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active work session. Start a session first."
        )

    # Check no active meeting already
    for mtg in session.meetings:
        if mtg.end_time is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an active meeting."
            )

    # Check no active break (can't start meeting during break)
    for brk in session.breaks:
        if brk.end_time is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End your break before starting a meeting."
            )

    now = datetime.now(timezone.utc)
    paused_entry_id = None

    # Find and STOP (not just pause) current time entry
    for entry in session.time_entries:
        if entry.is_running:
            # Stop this entry completely (we'll restart it after meeting)
            entry.end_time = now
            entry.is_running = False
            entry.is_paused = False
            if entry.start_time:
                total_elapsed = int((now - entry.start_time).total_seconds())
                entry.duration_seconds = total_elapsed - (entry.pause_seconds or 0)
            paused_entry_id = entry.id
            break

    # Update session status
    session.status = "meeting"

    # Create a time entry for the meeting
    meeting_description = meeting_data.title or f"{meeting_data.meeting_type.capitalize()} Meeting"
    meeting_entry = TimeEntry(
        user_id=current_user.id,
        project_id=None,  # Meetings don't require a project
        task_id=None,
        description=f"[Meeting] {meeting_description}",
        start_time=now,
        is_running=True,
        is_paused=False,
        pause_seconds=0,
        work_session_id=session.id,
    )
    db.add(meeting_entry)
    await db.flush()  # Get the ID

    # Create meeting record with references
    new_meeting = SessionMeeting(
        work_session_id=session.id,
        title=meeting_data.title,
        meeting_type=meeting_data.meeting_type,
        start_time=now,
        paused_entry_id=paused_entry_id,
        time_entry_id=meeting_entry.id,
    )
    db.add(new_meeting)
    await db.commit()
    await db.refresh(new_meeting)

    # Broadcast meeting started to company
    await ws_manager.broadcast_meeting_started(
        company_id=current_user.company_id,
        user_id=current_user.id,
        user_name=current_user.name,
        meeting_data={
            "meeting_id": new_meeting.id,
            "title": new_meeting.title,
            "meeting_type": new_meeting.meeting_type,
            "start_time": new_meeting.start_time.isoformat(),
            "time_entry_id": meeting_entry.id
        }
    )

    # Replace the cache entry with the new meeting TimeEntry (no project).
    await _refresh_active_timer_cache(
        db,
        current_user,
        _activity_payload(
            "meeting",
            meeting_type=new_meeting.meeting_type,
            meeting_title=new_meeting.title,
        ),
    )

    return SessionMeetingResponse.model_validate(new_meeting)


@router.post("/meeting/end", response_model=SessionMeetingResponse)
async def end_meeting(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    End the current meeting (stops meeting time entry, restarts previous task).

    This will:
    1. Stop the meeting time entry
    2. Restart the previously paused time entry (if any)
    """
    session = await get_active_session(db, current_user.id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active work session found."
        )

    # Find active meeting
    active_meeting = None
    for mtg in session.meetings:
        if mtg.end_time is None:
            active_meeting = mtg
            break

    if not active_meeting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active meeting to end."
        )

    now = datetime.now(timezone.utc)

    # End the meeting
    active_meeting.end_time = now
    active_meeting.duration_seconds = int((now - active_meeting.start_time).total_seconds())

    # Stop the meeting time entry
    if active_meeting.time_entry_id:
        result = await db.execute(
            select(TimeEntry).where(TimeEntry.id == active_meeting.time_entry_id)
        )
        meeting_entry = result.scalar_one_or_none()
        if meeting_entry and meeting_entry.is_running:
            meeting_entry.end_time = now
            meeting_entry.is_running = False
            meeting_entry.duration_seconds = int((now - meeting_entry.start_time).total_seconds())

    # Restart the previously paused time entry
    if active_meeting.paused_entry_id:
        result = await db.execute(
            select(TimeEntry).where(TimeEntry.id == active_meeting.paused_entry_id)
        )
        paused_entry = result.scalar_one_or_none()
        if paused_entry:
            # Create a NEW time entry continuing the previous task
            resumed_entry = TimeEntry(
                user_id=current_user.id,
                project_id=paused_entry.project_id,
                task_id=paused_entry.task_id,
                description=paused_entry.description,
                start_time=now,
                is_running=True,
                is_paused=False,
                pause_seconds=0,
                work_session_id=session.id,
            )
            db.add(resumed_entry)

    # Update session totals
    session.total_meeting_seconds += active_meeting.duration_seconds or 0
    session.status = "active"

    await db.commit()
    await db.refresh(active_meeting)

    # Broadcast meeting ended to company
    await ws_manager.broadcast_meeting_ended(
        company_id=current_user.company_id,
        user_id=current_user.id,
        user_name=current_user.name,
        meeting_data={
            "meeting_id": active_meeting.id,
            "title": active_meeting.title,
            "meeting_type": active_meeting.meeting_type,
            "duration_seconds": active_meeting.duration_seconds,
            "end_time": now.isoformat()
        }
    )

    # Replace the cache entry with the resumed project TimeEntry (if any),
    # restoring "working" state. If no resume happened the helper will
    # clear the cache instead.
    await _refresh_active_timer_cache(
        db,
        current_user,
        _activity_payload("working"),
    )

    return SessionMeetingResponse.model_validate(active_meeting)


# ============================================
# SESSION REPORTS ENDPOINTS (Additive)
# ============================================

@router.get("/reports/daily", response_model=DailySessionReport)
async def get_daily_session_report(
    report_date: Optional[date] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    tz: str = Depends(get_company_timezone),
):
    """
    Get a daily session report showing work, break, and meeting breakdown.

    If no date provided, returns today's report.
    This is ADDITIVE - does not modify existing reports.
    """
    if report_date is None:
        report_date = local_today(tz)

    # Half-open tenant-local day bounds (B7).
    day_start, day_end = day_bounds(report_date, tz)

    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.start_time >= day_start,
                WorkSession.start_time < day_end,
            )
        )
        .options(
            selectinload(WorkSession.breaks),
            selectinload(WorkSession.meetings),
            selectinload(WorkSession.time_entries)
        )
    )
    sessions = result.scalars().all()

    # Aggregate data
    total_work = 0
    total_break = 0
    total_meeting = 0
    task_breakdown = []

    for session in sessions:
        total_work += session.total_work_seconds
        total_break += session.total_break_seconds
        total_meeting += session.total_meeting_seconds

        # Build task breakdown from time entries
        for entry in session.time_entries:
            if entry.duration_seconds:
                task_breakdown.append({
                    "time_entry_id": entry.id,
                    "task_id": entry.task_id,
                    "project_id": entry.project_id,
                    "description": entry.description,
                    "duration_seconds": entry.duration_seconds,
                    "start_time": entry.start_time.isoformat() if entry.start_time else None,
                    "end_time": entry.end_time.isoformat() if entry.end_time else None,
                })

    return DailySessionReport(
        date=report_date,
        user_id=current_user.id,
        user_name=current_user.name,
        total_work_seconds=total_work,
        total_break_seconds=total_break,
        total_meeting_seconds=total_meeting,
        net_productive_seconds=total_work,  # Work time excludes breaks/meetings
        session_count=len(sessions),
        task_breakdown=task_breakdown
    )


@router.get("/reports/summary", response_model=SessionSummary)
async def get_session_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    tz: str = Depends(get_company_timezone),
):
    """
    Get a session summary for a date range.

    Defaults to the current week if no dates provided.
    This is ADDITIVE - does not modify existing reports.
    """
    if end_date is None:
        end_date = local_today(tz)
    if start_date is None:
        # Default to start of current week (Monday)
        start_date = end_date - timedelta(days=end_date.weekday())

    # Half-open tenant-local range bounds (B7).
    range_start, range_end = range_bounds(start_date, end_date, tz)

    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.start_time >= range_start,
                WorkSession.start_time < range_end,
            )
        )
    )
    sessions = result.scalars().all()

    # Aggregate totals
    total_work = sum(s.total_work_seconds for s in sessions)
    total_break = sum(s.total_break_seconds for s in sessions)
    total_meeting = sum(s.total_meeting_seconds for s in sessions)

    # Calculate averages
    completed_sessions = [s for s in sessions if s.status == "completed"]
    avg_session_length = 0
    if completed_sessions:
        total_session_time = sum(
            int((s.end_time - s.start_time).total_seconds())
            for s in completed_sessions
            if s.end_time
        )
        avg_session_length = total_session_time // len(completed_sessions)

    return SessionSummary(
        start_date=start_date,
        end_date=end_date,
        user_id=current_user.id,
        user_name=current_user.name,
        total_work_seconds=total_work,
        total_break_seconds=total_break,
        total_meeting_seconds=total_meeting,
        session_count=len(sessions),
        average_session_seconds=avg_session_length
    )


# ============================================
# ADMIN: STALE SESSION CLEANUP
# ============================================

@router.post("/admin/cleanup-stale", response_model=dict)
async def cleanup_stale_sessions(
    max_hours: int = 12,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin endpoint to manually close stale work sessions.

    Closes all sessions that have been running longer than max_hours.
    Also closes any orphaned time entries.

    Only accessible by admin/super_admin users.
    """
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    now = datetime.now(timezone.utc)
    max_age = now - timedelta(hours=max_hours)

    sessions_closed = 0
    entries_closed = 0

    # Find all stale sessions
    stale_result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.end_time.is_(None),
                WorkSession.start_time < max_age
            )
        )
        .options(
            selectinload(WorkSession.time_entries),
            selectinload(WorkSession.breaks),
            selectinload(WorkSession.meetings)
        )
    )
    stale_sessions = stale_result.scalars().all()

    for session in stale_sessions:
        # Close time entries
        for entry in session.time_entries:
            if entry.end_time is None:
                entry.end_time = now
                entry.is_running = False
                entry.is_paused = False
                if entry.start_time:
                    total_elapsed = int((now - entry.start_time).total_seconds())
                    entry.duration_seconds = total_elapsed - (entry.pause_seconds or 0)
                entries_closed += 1

        # Close breaks
        for brk in session.breaks:
            if brk.end_time is None:
                brk.end_time = now
                brk.duration_seconds = int((now - brk.start_time).total_seconds())
                session.total_break_seconds += brk.duration_seconds

        # Close meetings
        for mtg in session.meetings:
            if mtg.end_time is None:
                mtg.end_time = now
                mtg.duration_seconds = int((now - mtg.start_time).total_seconds())
                session.total_meeting_seconds += mtg.duration_seconds

        # Close session
        session.end_time = now
        session.status = "auto_closed"
        session.total_work_seconds = sum(
            (e.duration_seconds or 0) for e in session.time_entries
        )
        sessions_closed += 1

    # Close orphaned entries (not linked to any session)
    orphan_result = await db.execute(
        select(TimeEntry).where(
            and_(
                TimeEntry.end_time.is_(None),
                TimeEntry.start_time < max_age
            )
        )
    )
    orphan_entries = orphan_result.scalars().all()

    for entry in orphan_entries:
        entry.end_time = now
        entry.is_running = False
        entry.is_paused = False
        if entry.start_time:
            total_elapsed = int((now - entry.start_time).total_seconds())
            entry.duration_seconds = total_elapsed - (entry.pause_seconds or 0)
        entries_closed += 1

    await db.commit()

    return {
        "success": True,
        "sessions_closed": sessions_closed,
        "entries_closed": entries_closed,
        "max_hours": max_hours,
        "cleanup_time": now.isoformat()
    }
