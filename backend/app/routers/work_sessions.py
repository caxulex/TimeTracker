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

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models import User, WorkSession, SessionBreak, SessionMeeting, TimeEntry
from app.schemas.sessions import (
    WorkSessionCreate,
    WorkSessionResponse,
    WorkSessionWithDetails,
    SessionBreakCreate,
    SessionBreakResponse,
    SessionMeetingCreate,
    SessionMeetingResponse,
    SessionStatusResponse,
)

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
    
    # Global timer = elapsed - total break time (meetings don't subtract from global)
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
    
    # Stop any running time entries
    for entry in session.time_entries:
        if entry.end_time is None:
            entry.end_time = now
            entry.is_running = False
            entry.is_paused = False
            if entry.start_time:
                total_elapsed = int((entry.end_time - entry.start_time).total_seconds())
                entry.duration_seconds = total_elapsed - entry.pause_seconds
    
    # End any active breaks
    for brk in session.breaks:
        if brk.end_time is None:
            brk.end_time = now
            brk.duration_seconds = int((now - brk.start_time).total_seconds())
            session.total_break_seconds += brk.duration_seconds
    
    # End any active meetings
    for mtg in session.meetings:
        if mtg.end_time is None:
            mtg.end_time = now
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
    Start a meeting (pauses ONLY task timer, global keeps running).
    
    Meeting types:
    - "internal": Internal team meeting
    - "external": External meeting
    - "client": Client meeting
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
    
    # Pause current task (but NOT the global session timer!)
    now = datetime.now(timezone.utc)
    for entry in session.time_entries:
        if entry.is_running and not entry.is_paused:
            entry.is_paused = True
            entry.paused_at = now
    
    # Update session status
    session.status = "meeting"
    
    # Create meeting record
    new_meeting = SessionMeeting(
        work_session_id=session.id,
        title=meeting_data.title,
        meeting_type=meeting_data.meeting_type,
        start_time=now,
    )
    db.add(new_meeting)
    await db.commit()
    await db.refresh(new_meeting)
    
    return SessionMeetingResponse.model_validate(new_meeting)


@router.post("/meeting/end", response_model=SessionMeetingResponse)
async def end_meeting(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    End the current meeting (resumes task timer).
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
    
    # End the meeting
    now = datetime.now(timezone.utc)
    active_meeting.end_time = now
    active_meeting.duration_seconds = int((now - active_meeting.start_time).total_seconds())
    
    # Update session totals
    session.total_meeting_seconds += active_meeting.duration_seconds
    session.status = "active"
    
    # Resume paused time entries
    for entry in session.time_entries:
        if entry.is_paused:
            entry.is_paused = False
            if entry.paused_at:
                entry.pause_seconds += int((now - entry.paused_at).total_seconds())
            entry.paused_at = None
    
    await db.commit()
    await db.refresh(active_meeting)
    
    return SessionMeetingResponse.model_validate(active_meeting)
