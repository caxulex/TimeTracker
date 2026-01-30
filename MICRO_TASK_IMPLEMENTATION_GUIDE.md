# 🤖 COPILOT IMPLEMENTATION GUIDE: Micro-Task Management Feature

> **CRITICAL**: This is a step-by-step checklist for GitHub Copilot to implement the micro-task management feature WITHOUT breaking existing functionality.
>
> **Date Created**: January 30, 2026  
> **Reference Document**: `MICRO_TASK_MANAGEMENT_UPDATE.md`

---

## ⚠️ GOLDEN RULES - NEVER VIOLATE THESE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. NEVER remove or rename existing database columns                        │
│  2. NEVER change the meaning of `duration_seconds` in TimeEntry             │
│  3. NEVER modify existing API response structures (only ADD fields)         │
│  4. NEVER change how `is_running` or `end_time == None` works              │
│  5. ALWAYS make new FK columns NULLABLE                                     │
│  6. ALWAYS run tests after EACH phase before proceeding                     │
│  7. ALWAYS commit after each completed phase                                │
│  8. STOP immediately if any test fails - do not proceed                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 IMPLEMENTATION PHASES

### Current Progress Tracker
```
PHASE 1: [  ] Database Models
PHASE 2: [  ] Database Migration  
PHASE 3: [  ] Backend Schemas
PHASE 4: [  ] Session API Endpoints
PHASE 5: [  ] Timer Integration
PHASE 6: [  ] WebSocket Updates
PHASE 7: [  ] Frontend Stores
PHASE 8: [  ] Frontend Components
PHASE 9: [  ] Reports Integration
PHASE 10: [  ] Testing & Validation
```

---

# PHASE 1: DATABASE MODELS

## Pre-Phase Checklist
- [ ] Read current `backend/app/models/__init__.py` completely
- [ ] Identify all existing TimeEntry relationships
- [ ] Verify no conflicts with new model names

## Tasks

### 1.1 Create WorkSession Model
**File**: `backend/app/models/__init__.py`

**Add AFTER the TimeEntry class (do NOT modify TimeEntry yet):**

```python
# - [ ] Task 1.1.1: Add WorkSession model
class WorkSession(Base):
    """
    Represents a user's work day/session.
    Links multiple TimeEntry records together.
    """
    __tablename__ = "work_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("companies.id"), nullable=True)
    
    # Session timing
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Calculated totals (updated on session end)
    total_work_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_break_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_meeting_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    # Values: "active", "break", "meeting", "completed"
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="work_sessions")
    company: Mapped[Optional["Company"]] = relationship("Company")
    time_entries: Mapped[List["TimeEntry"]] = relationship("TimeEntry", back_populates="work_session")
    breaks: Mapped[List["SessionBreak"]] = relationship("SessionBreak", back_populates="work_session", cascade="all, delete-orphan")
    meetings: Mapped[List["SessionMeeting"]] = relationship("SessionMeeting", back_populates="work_session", cascade="all, delete-orphan")
```

**Verification after 1.1.1:**
- [ ] Code passes syntax check
- [ ] No import errors

### 1.2 Create SessionBreak Model
**Add AFTER WorkSession class:**

```python
# - [ ] Task 1.1.2: Add SessionBreak model
class SessionBreak(Base):
    """Records break periods within a work session."""
    __tablename__ = "session_breaks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_sessions.id"), nullable=False)
    
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    break_type: Mapped[str] = mapped_column(String(20), default="short", nullable=False)
    # Values: "short", "lunch", "other"
    
    # Relationships
    work_session: Mapped["WorkSession"] = relationship("WorkSession", back_populates="breaks")
```

### 1.3 Create SessionMeeting Model
**Add AFTER SessionBreak class:**

```python
# - [ ] Task 1.1.3: Add SessionMeeting model
class SessionMeeting(Base):
    """Records meeting periods within a work session."""
    __tablename__ = "session_meetings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_sessions.id"), nullable=False)
    
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    meeting_type: Mapped[str] = mapped_column(String(20), default="internal", nullable=False)
    # Values: "internal", "external", "client"
    
    # Relationships
    work_session: Mapped["WorkSession"] = relationship("WorkSession", back_populates="meetings")
```

### 1.4 Add TimeEntry Foreign Key (NULLABLE!)
**CRITICAL: This is an ADDITIVE change only!**

**Find the TimeEntry class and ADD these columns (do NOT remove anything):**

```python
# - [ ] Task 1.1.4: Add nullable FK to TimeEntry
# ADD these lines to TimeEntry class - DO NOT REMOVE ANY EXISTING COLUMNS

    # Link to work session (NULLABLE for backward compatibility)
    work_session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("work_sessions.id"), nullable=True
    )
    
    # Pause tracking (for breaks/meetings)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pause_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationship
    work_session: Mapped[Optional["WorkSession"]] = relationship("WorkSession", back_populates="time_entries")
```

### 1.5 Add User Relationship
**Find the User class and ADD:**

```python
# - [ ] Task 1.1.5: Add work_sessions relationship to User
    work_sessions: Mapped[List["WorkSession"]] = relationship("WorkSession", back_populates="user")
```

## Phase 1 Completion Checklist
- [ ] All 5 tasks above completed
- [ ] Run: `python -c "from backend.app.models import *; print('Models OK')"` - MUST pass
- [ ] No existing columns were removed
- [ ] No existing relationships were modified
- [ ] Commit: `git add -A && git commit -m "Phase 1: Add micro-task models (no migration yet)"`

**⛔ STOP HERE IF ANY CHECK FAILS - DO NOT PROCEED TO PHASE 2**

---

# PHASE 2: DATABASE MIGRATION

## Pre-Phase Checklist
- [ ] Phase 1 completed and committed
- [ ] Database backup taken (if production)
- [ ] Currently on feature branch: `feature/micro-task-management`

## Tasks

### 2.1 Generate Migration
```bash
# - [ ] Task 2.1.1: Generate alembic migration
cd backend
alembic revision --autogenerate -m "add_micro_task_management_tables"
```

### 2.2 Review Migration File
**File**: `backend/alembic/versions/xxx_add_micro_task_management_tables.py`

**CRITICAL VERIFICATION - The migration MUST:**
- [ ] Only contain `op.create_table()` for new tables
- [ ] Only contain `op.add_column()` for TimeEntry changes
- [ ] NOT contain any `op.drop_column()`
- [ ] NOT contain any `op.alter_column()` that changes types
- [ ] All new FK columns have `nullable=True`

### 2.3 Run Migration (Development)
```bash
# - [ ] Task 2.3.1: Apply migration
alembic upgrade head
```

### 2.4 Verify Migration
```bash
# - [ ] Task 2.4.1: Verify tables exist
# Run this SQL to verify:
# SELECT table_name FROM information_schema.tables WHERE table_name IN ('work_sessions', 'session_breaks', 'session_meetings');
```

## Phase 2 Completion Checklist
- [ ] Migration file reviewed and safe
- [ ] Migration applied successfully
- [ ] New tables created: work_sessions, session_breaks, session_meetings
- [ ] TimeEntry table has new columns: work_session_id, is_paused, paused_at, pause_seconds
- [ ] ALL existing data still accessible
- [ ] Run existing tests: `pytest backend/tests/ -v` - MUST pass with NO failures
- [ ] Commit: `git add -A && git commit -m "Phase 2: Database migration for micro-task management"`

**⛔ STOP HERE IF ANY TEST FAILS - DO NOT PROCEED TO PHASE 3**

---

# PHASE 3: BACKEND SCHEMAS (Pydantic)

## Pre-Phase Checklist
- [ ] Phase 2 completed and committed
- [ ] All existing tests passing

## Tasks

### 3.1 Create Session Schemas
**Create new file**: `backend/app/schemas/sessions.py`

```python
# - [ ] Task 3.1.1: Create sessions.py schema file
"""
Pydantic schemas for Work Sessions, Breaks, and Meetings.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


# ============================================
# SESSION BREAK SCHEMAS
# ============================================
class SessionBreakBase(BaseModel):
    break_type: str = "short"  # "short", "lunch", "other"


class SessionBreakCreate(SessionBreakBase):
    pass


class SessionBreakResponse(SessionBreakBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    work_session_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int = 0


# ============================================
# SESSION MEETING SCHEMAS
# ============================================
class SessionMeetingBase(BaseModel):
    title: Optional[str] = None
    meeting_type: str = "internal"  # "internal", "external", "client"


class SessionMeetingCreate(SessionMeetingBase):
    pass


class SessionMeetingResponse(SessionMeetingBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    work_session_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int = 0


# ============================================
# WORK SESSION SCHEMAS
# ============================================
class WorkSessionBase(BaseModel):
    pass


class WorkSessionCreate(WorkSessionBase):
    pass


class WorkSessionResponse(WorkSessionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    company_id: Optional[int] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str
    total_work_seconds: int = 0
    total_break_seconds: int = 0
    total_meeting_seconds: int = 0
    created_at: datetime


class WorkSessionWithDetails(WorkSessionResponse):
    """Session with nested breaks and meetings."""
    breaks: List[SessionBreakResponse] = []
    meetings: List[SessionMeetingResponse] = []


# ============================================
# SESSION STATUS SCHEMA (for real-time updates)
# ============================================
class SessionStatusResponse(BaseModel):
    """Current session status for a user."""
    has_active_session: bool
    session: Optional[WorkSessionResponse] = None
    current_status: str  # "working", "break", "meeting", "idle"
    global_timer_seconds: int = 0  # Total session time
    task_timer_seconds: int = 0    # Current task time
    current_break: Optional[SessionBreakResponse] = None
    current_meeting: Optional[SessionMeetingResponse] = None
```

### 3.2 Export Schemas
**File**: `backend/app/schemas/__init__.py`

**ADD (do not remove existing exports):**
```python
# - [ ] Task 3.2.1: Add session schema exports
from .sessions import (
    WorkSessionCreate,
    WorkSessionResponse,
    WorkSessionWithDetails,
    SessionBreakCreate,
    SessionBreakResponse,
    SessionMeetingCreate,
    SessionMeetingResponse,
    SessionStatusResponse,
)
```

## Phase 3 Completion Checklist
- [ ] New schema file created: `backend/app/schemas/sessions.py`
- [ ] Schemas exported in `__init__.py`
- [ ] Run: `python -c "from backend.app.schemas.sessions import *; print('Schemas OK')"` - MUST pass
- [ ] Existing schemas still work
- [ ] Commit: `git add -A && git commit -m "Phase 3: Session Pydantic schemas"`

**⛔ STOP HERE IF ANY CHECK FAILS - DO NOT PROCEED TO PHASE 4**

---

# PHASE 4: SESSION API ENDPOINTS

## Pre-Phase Checklist
- [ ] Phase 3 completed and committed
- [ ] All existing tests passing

## Tasks

### 4.1 Create Session Router
**Create new file**: `backend/app/routers/sessions.py`

```python
# - [ ] Task 4.1.1: Create sessions.py router (start with basic structure)
"""
Work Session Management API Endpoints.
Handles sessions, breaks, and meetings.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..auth import get_current_user
from ..models import User, WorkSession, SessionBreak, SessionMeeting, TimeEntry
from ..schemas.sessions import (
    WorkSessionCreate,
    WorkSessionResponse,
    WorkSessionWithDetails,
    SessionBreakCreate,
    SessionBreakResponse,
    SessionMeetingCreate,
    SessionMeetingResponse,
    SessionStatusResponse,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ============================================
# SESSION ENDPOINTS
# ============================================

@router.get("/current", response_model=SessionStatusResponse)
async def get_current_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the current user's active work session status."""
    # Find active session (no end_time)
    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.end_time.is_(None)
            )
        )
        .options(selectinload(WorkSession.breaks), selectinload(WorkSession.meetings))
    )
    session = result.scalar_one_or_none()
    
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
    
    # Determine current status
    current_break = None
    current_meeting = None
    current_status = "working"
    
    for brk in session.breaks:
        if brk.end_time is None:
            current_break = brk
            current_status = "break"
            break
    
    for mtg in session.meetings:
        if mtg.end_time is None:
            current_meeting = mtg
            current_status = "meeting"
            break
    
    return SessionStatusResponse(
        has_active_session=True,
        session=WorkSessionResponse.model_validate(session),
        current_status=current_status,
        global_timer_seconds=elapsed_seconds - session.total_break_seconds,
        task_timer_seconds=0,  # Will be calculated from current TimeEntry
        current_break=SessionBreakResponse.model_validate(current_break) if current_break else None,
        current_meeting=SessionMeetingResponse.model_validate(current_meeting) if current_meeting else None,
    )


@router.post("/start", response_model=WorkSessionResponse)
async def start_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start a new work session (clock in for the day)."""
    # Check if already has active session
    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.end_time.is_(None)
            )
        )
    )
    existing = result.scalar_one_or_none()
    
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """End the current work session (clock out for the day)."""
    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.end_time.is_(None)
            )
        )
        .options(selectinload(WorkSession.time_entries))
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active work session found."
        )
    
    # Stop any running time entries
    for entry in session.time_entries:
        if entry.end_time is None:
            entry.end_time = datetime.now(timezone.utc)
            entry.is_running = False
            if entry.start_time:
                entry.duration_seconds = int((entry.end_time - entry.start_time).total_seconds())
    
    # Calculate totals
    now = datetime.now(timezone.utc)
    session.end_time = now
    session.status = "completed"
    session.total_work_seconds = sum(
        (e.duration_seconds or 0) for e in session.time_entries
    )
    
    await db.commit()
    await db.refresh(session)
    
    return WorkSessionResponse.model_validate(session)


# ============================================
# BREAK ENDPOINTS  
# ============================================

@router.post("/break/start", response_model=SessionBreakResponse)
async def start_break(
    break_data: SessionBreakCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start a break (pauses BOTH global and task timers)."""
    # Get active session
    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.end_time.is_(None)
            )
        )
        .options(selectinload(WorkSession.breaks), selectinload(WorkSession.time_entries))
    )
    session = result.scalar_one_or_none()
    
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """End the current break (resumes BOTH global and task timers)."""
    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.end_time.is_(None)
            )
        )
        .options(selectinload(WorkSession.breaks), selectinload(WorkSession.time_entries))
    )
    session = result.scalar_one_or_none()
    
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start a meeting (pauses ONLY task timer, global keeps running)."""
    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.end_time.is_(None)
            )
        )
        .options(selectinload(WorkSession.meetings), selectinload(WorkSession.time_entries))
    )
    session = result.scalar_one_or_none()
    
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """End the current meeting (resumes task timer)."""
    result = await db.execute(
        select(WorkSession)
        .where(
            and_(
                WorkSession.user_id == current_user.id,
                WorkSession.end_time.is_(None)
            )
        )
        .options(selectinload(WorkSession.meetings), selectinload(WorkSession.time_entries))
    )
    session = result.scalar_one_or_none()
    
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
```

### 4.2 Register Router in Main App
**File**: `backend/app/main.py`

**ADD (do not remove existing routers):**
```python
# - [ ] Task 4.2.1: Import and include sessions router
from .routers import sessions

# In the app setup section:
app.include_router(sessions.router)
```

## Phase 4 Completion Checklist
- [ ] New router file created: `backend/app/routers/sessions.py`
- [ ] Router registered in main.py
- [ ] Run: `python -c "from backend.app.routers.sessions import router; print('Router OK')"` - MUST pass
- [ ] Start backend server: `uvicorn backend.app.main:app --reload` - MUST start without errors
- [ ] Test endpoint: `curl http://localhost:8000/api/sessions/current` - MUST return response (401 is OK)
- [ ] ALL existing tests still pass: `pytest backend/tests/ -v`
- [ ] Commit: `git add -A && git commit -m "Phase 4: Session API endpoints"`

**⛔ STOP HERE IF ANY CHECK FAILS - DO NOT PROCEED TO PHASE 5**

---

# PHASE 5: TIMER INTEGRATION

## Pre-Phase Checklist
- [ ] Phase 4 completed and committed
- [ ] Session endpoints working
- [ ] All existing tests passing

## Tasks

### 5.1 Modify Time Entry Start (CAREFULLY!)
**File**: `backend/app/routers/time_entries.py`

**Find the `start_timer` endpoint and ADD session linking logic (do NOT change existing behavior):**

```python
# - [ ] Task 5.1.1: Add session auto-creation to start_timer
# Find the start_timer function and ADD this logic AFTER creating the time entry:

# Auto-create or link to work session
from ..models import WorkSession

# After: db.add(entry) but BEFORE: await db.commit()
# ADD THIS:

# Find or create active work session
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
    # Auto-create session when starting first timer
    active_session = WorkSession(
        user_id=current_user.id,
        company_id=current_user.company_id,
        status="active",
    )
    db.add(active_session)
    await db.flush()  # Get the ID

# Link time entry to session
entry.work_session_id = active_session.id
```

### 5.2 Verify Existing Behavior Unchanged
**CRITICAL**: Run these tests IMMEDIATELY after 5.1:

```bash
# - [ ] Task 5.2.1: Test existing timer functionality
pytest backend/tests/test_time_entries.py -v

# - [ ] Task 5.2.2: Manual test - start timer
# Use API or frontend to start a timer
# Verify it works exactly as before

# - [ ] Task 5.2.3: Manual test - stop timer  
# Stop the timer
# Verify duration_seconds is calculated correctly
```

## Phase 5 Completion Checklist
- [ ] Timer start auto-creates session if needed
- [ ] Timer links to active session
- [ ] **CRITICAL**: Existing timer start/stop works EXACTLY as before
- [ ] **CRITICAL**: duration_seconds calculated correctly
- [ ] **CRITICAL**: Payroll calculation unchanged
- [ ] ALL existing tests pass: `pytest backend/tests/ -v`
- [ ] Commit: `git add -A && git commit -m "Phase 5: Timer-session integration"`

**⛔ STOP HERE IF ANY CHECK FAILS - DO NOT PROCEED TO PHASE 6**

---

# PHASE 6: WEBSOCKET UPDATES

## Pre-Phase Checklist
- [ ] Phase 5 completed and committed
- [ ] All existing tests passing

## Tasks

### 6.1 Add New WebSocket Message Types
**File**: `backend/app/routers/websocket.py` or `backend/websocket/manager.py`

**ADD new message types (do NOT modify existing messages):**

```python
# - [ ] Task 6.1.1: Add session WebSocket broadcasts
# Add these new broadcast functions (do NOT modify existing ones):

async def broadcast_session_started(company_id: int, user_id: int, session_data: dict):
    """Broadcast when a user starts their work session."""
    await ws_manager.broadcast_to_company(company_id, {
        "type": "session_started",
        "user_id": user_id,
        "data": session_data
    })

async def broadcast_session_ended(company_id: int, user_id: int, session_data: dict):
    """Broadcast when a user ends their work session."""
    await ws_manager.broadcast_to_company(company_id, {
        "type": "session_ended",
        "user_id": user_id,
        "data": session_data
    })

async def broadcast_break_started(company_id: int, user_id: int, break_data: dict):
    """Broadcast when a user starts a break."""
    await ws_manager.broadcast_to_company(company_id, {
        "type": "break_started",
        "user_id": user_id,
        "data": break_data
    })

async def broadcast_break_ended(company_id: int, user_id: int, break_data: dict):
    """Broadcast when a user ends a break."""
    await ws_manager.broadcast_to_company(company_id, {
        "type": "break_ended",
        "user_id": user_id,
        "data": break_data
    })

async def broadcast_meeting_started(company_id: int, user_id: int, meeting_data: dict):
    """Broadcast when a user starts a meeting."""
    await ws_manager.broadcast_to_company(company_id, {
        "type": "meeting_started",
        "user_id": user_id,
        "data": meeting_data
    })

async def broadcast_meeting_ended(company_id: int, user_id: int, meeting_data: dict):
    """Broadcast when a user ends a meeting."""
    await ws_manager.broadcast_to_company(company_id, {
        "type": "meeting_ended",
        "user_id": user_id,
        "data": meeting_data
    })
```

### 6.2 Wire Broadcasts to Session Endpoints
**File**: `backend/app/routers/sessions.py`

**ADD broadcasts after each session action (at end of endpoint functions):**

```python
# - [ ] Task 6.2.1: Add WebSocket broadcasts to session endpoints
# Import at top:
from ..websocket.manager import (
    broadcast_session_started,
    broadcast_session_ended,
    broadcast_break_started,
    broadcast_break_ended,
    broadcast_meeting_started,
    broadcast_meeting_ended,
)

# Add at end of start_session:
await broadcast_session_started(current_user.company_id, current_user.id, {...})

# Add at end of end_session:
await broadcast_session_ended(current_user.company_id, current_user.id, {...})

# etc. for breaks and meetings
```

## Phase 6 Completion Checklist
- [ ] New WebSocket message types added
- [ ] Broadcasts wired to session endpoints
- [ ] Existing WebSocket messages (timer_started, timer_stopped) unchanged
- [ ] Test WebSocket connections still work
- [ ] ALL existing tests pass
- [ ] Commit: `git add -A && git commit -m "Phase 6: WebSocket broadcasts for sessions"`

**⛔ STOP HERE IF ANY CHECK FAILS - DO NOT PROCEED TO PHASE 7**

---

# PHASE 7-10: FRONTEND (Follow Same Pattern)

## Phases 7-10 will follow the same careful, incremental approach:

### Phase 7: Frontend Stores
- [ ] Create `sessionStore.ts`
- [ ] Add session state to existing stores (additive only)
- [ ] Test existing functionality unchanged

### Phase 8: Frontend Components
- [ ] Create SessionWidget, BreakControls, MeetingControls
- [ ] Add to TimePage (additive, don't remove existing)
- [ ] Test all existing features work

### Phase 9: Reports Integration
- [ ] Add task breakdown to reports (additive)
- [ ] Test existing reports unchanged

### Phase 10: Final Testing
- [ ] Full regression test
- [ ] Payroll calculation verification
- [ ] Export verification
- [ ] WebSocket verification

---

# 🚨 EMERGENCY ROLLBACK PROCEDURES

## If Something Breaks:

### 1. Immediate Rollback (No Commit Yet)
```bash
git checkout -- .
git clean -fd
```

### 2. Rollback After Commit
```bash
git revert HEAD
# Or reset to last known good:
git reset --hard <last-good-commit>
```

### 3. Database Rollback
```bash
cd backend
alembic downgrade -1
```

### 4. Full Reset
```bash
git checkout main
git branch -D feature/micro-task-management
# Start fresh
```

---

# ✅ FINAL VALIDATION CHECKLIST

Before considering implementation complete:

- [ ] All 10 phases completed and committed
- [ ] ALL existing tests pass (100%)
- [ ] Payroll calculation produces identical results for existing data
- [ ] Reports show identical totals for existing data
- [ ] Timer start/stop works exactly as before
- [ ] WebSocket connections stable
- [ ] Export functions work correctly
- [ ] New features (sessions, breaks, meetings) work correctly
- [ ] Feature flag ready for gradual rollout
- [ ] Documentation updated

---

**END OF IMPLEMENTATION GUIDE**

*Copilot: Follow this guide EXACTLY. Complete one phase at a time. Do NOT skip steps. STOP if any test fails.*
