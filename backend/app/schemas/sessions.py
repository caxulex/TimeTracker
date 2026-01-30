"""
Pydantic schemas for Work Sessions, Breaks, and Meetings.

Part of the Micro-Task Management feature.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


# ============================================
# SESSION BREAK SCHEMAS
# ============================================

class SessionBreakBase(BaseModel):
    """Base schema for session breaks."""
    break_type: str = "short"  # "short", "lunch", "other"


class SessionBreakCreate(SessionBreakBase):
    """Schema for creating a new break."""
    pass


class SessionBreakResponse(SessionBreakBase):
    """Schema for break response."""
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
    """Base schema for session meetings."""
    title: Optional[str] = None
    meeting_type: str = "internal"  # "internal", "external", "client"


class SessionMeetingCreate(SessionMeetingBase):
    """Schema for creating a new meeting."""
    pass


class SessionMeetingResponse(SessionMeetingBase):
    """Schema for meeting response."""
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
    """Base schema for work sessions."""
    pass


class WorkSessionCreate(WorkSessionBase):
    """Schema for creating a new work session."""
    pass


class WorkSessionResponse(WorkSessionBase):
    """Schema for work session response."""
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
    """Work session with nested breaks and meetings."""
    breaks: List[SessionBreakResponse] = []
    meetings: List[SessionMeetingResponse] = []


# ============================================
# SESSION STATUS SCHEMA (for real-time updates)
# ============================================

class SessionStatusResponse(BaseModel):
    """
    Current session status for a user.
    Used for real-time UI updates showing:
    - Whether user has an active session
    - Current status (working, break, meeting, idle)
    - Timer values for both global and task timers
    """
    has_active_session: bool
    session: Optional[WorkSessionResponse] = None
    current_status: str  # "working", "break", "meeting", "idle"
    global_timer_seconds: int = 0  # Total session time (minus breaks)
    task_timer_seconds: int = 0    # Current task time
    current_break: Optional[SessionBreakResponse] = None
    current_meeting: Optional[SessionMeetingResponse] = None


# ============================================
# SESSION HISTORY/REPORT SCHEMAS
# ============================================

class SessionSummary(BaseModel):
    """Summary of a completed session for reports."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    date: datetime
    total_work_seconds: int
    total_break_seconds: int
    total_meeting_seconds: int
    net_work_seconds: int  # work - breaks
    task_count: int  # Number of tasks worked on
    status: str


class DailySessionReport(BaseModel):
    """Daily report showing session breakdown."""
    date: str  # YYYY-MM-DD
    sessions: List[SessionSummary] = []
    total_work_hours: float
    total_break_hours: float
    total_meeting_hours: float
    net_work_hours: float
