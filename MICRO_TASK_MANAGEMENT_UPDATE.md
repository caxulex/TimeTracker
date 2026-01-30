# TimeTracker Micro-Task Management Feature - Full Assessment

> **Created**: January 30, 2026  
> **Status**: Assessment Complete - Ready for Implementation  
> **Estimated Effort**: 40-60 hours of development  
> **Complexity**: High (Database schema changes, new business logic, significant UI updates)

---

## �️ COMPATIBILITY & RISK ANALYSIS

> **CRITICAL**: This section identifies all potential breaking changes and provides mitigation strategies to ensure zero downtime and backward compatibility.

### Risk Assessment Summary

| Risk Area | Risk Level | Impact | Mitigation |
|-----------|------------|--------|------------|
| Database Migration | 🔴 HIGH | Data loss possible | Additive-only changes, nullable FK |
| Payroll Calculation | 🔴 HIGH | Wrong pay amounts | Preserve `duration_seconds`, no logic change |
| Reports/Dashboard | 🟡 MEDIUM | Incorrect totals | Existing queries stay untouched |
| WebSocket/Real-time | 🟡 MEDIUM | UI desync | Add new message types only |
| Timer API | 🟡 MEDIUM | Timer fails | Keep existing endpoints working |
| Export Functions | 🟢 LOW | Export fails | No schema changes to TimeEntry |
| Multi-tenancy | 🟢 LOW | Data leaks | New tables follow same patterns |

---

### 🔴 CRITICAL: Payroll System Compatibility

**Current Payroll Logic** (from `payroll_service.py`):
```python
# HOURLY: Uses duration_seconds from TimeEntry
total_seconds = sum(te.duration_seconds or 0 for te in time_entries)
total_hours = Decimal(total_seconds) / Decimal("3600")

# DAILY: Uses unique start_time dates
for te in time_entries:
    worked_days.add(te.start_time.date())

# MONTHLY: Uses pay_rate.base_rate (no time entries needed)
```

**✅ SAFE - No changes needed because:**
1. `TimeEntry.duration_seconds` will ALWAYS be populated when timer stops
2. `TimeEntry.start_time` stays the same
3. New `work_session_id` field is **nullable** - existing entries work fine
4. New `pause_seconds` field is **nullable, defaults to 0**
5. Payroll queries filter by `TimeEntry.is_running == False` - unchanged

**⚠️ NEW CONSIDERATION: Break/Meeting Time in Payroll**
- Breaks should NOT count toward paid hours (already excluded - no TimeEntry created during break)
- Meetings SHOULD count toward paid hours (global timer runs, creates meeting time)
- **Decision needed**: Should meeting time be a separate TimeEntry or tracked differently?

**RECOMMENDED**: Create TimeEntries for meeting time with a special `entry_type` field:
```python
# Add to TimeEntry model
entry_type: Mapped[str] = mapped_column(String(20), default="task", nullable=False)
# Values: "task", "meeting", "break" (break entries have 0 duration for audit)
```

---

### 🔴 CRITICAL: Reports & Dashboard Compatibility

**Current Duration Calculation** (from `reports.py`):
```python
def calculate_entry_duration_for_period(entry, period_start, period_end, now):
    # Uses: entry.start_time, entry.end_time, entry.duration_seconds
    if entry.end_time is None:
        entry_end = now  # Running timer
    else:
        entry_end = entry.end_time
```

**✅ SAFE - Why this still works:**
1. Task TimeEntries have normal `start_time`, `end_time`, `duration_seconds`
2. Meeting TimeEntries (if created) have same structure
3. Break TimeEntries are NOT created (or have 0 duration)
4. Running timer detection: `entry.end_time is None` - **unchanged**

**⚠️ POTENTIAL ISSUE: "Running Timer" Detection**
Current code checks `TimeEntry.end_time == None` for running timers.

**NEW STATES TO HANDLE:**
| State | end_time | is_running | NEW: is_paused |
|-------|----------|------------|----------------|
| Working on task | NULL | True | False |
| On break | NULL | True | **True** |
| In meeting | NULL | True | **True** (task paused) |
| Task completed | timestamp | False | False |

**SOLUTION**: Add `is_paused` field to TimeEntry:
```python
is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

**MIGRATION**: All existing entries get `is_paused = False` (default)

---

### 🔴 CRITICAL: Existing API Endpoint Behavior

**Must NOT break these endpoints:**

| Endpoint | Current Behavior | New Behavior | Breaking? |
|----------|------------------|--------------|-----------|
| `POST /api/time/start` | Creates TimeEntry, rejects if one running | Same + links to session | ❌ No |
| `POST /api/time/stop` | Stops running entry | Same, session stays active | ❌ No |
| `GET /api/time/timer` | Returns running entry or null | Same + adds session info | ❌ No |
| `GET /api/time/active` | List all running timers | Same + adds break/meeting status | ❌ No |
| `GET /api/reports/*` | Uses TimeEntry data | Same queries work | ❌ No |

**✅ STRATEGY: Additive Changes Only**
- Add NEW endpoints for session management
- Add NEW optional fields to responses
- Keep ALL existing endpoints working identically

---

### 🟡 MEDIUM: WebSocket Real-time Updates

**Current WebSocket Messages:**
```python
# Broadcasted when timer starts
{"type": "timer_started", "data": {...}}

# Broadcasted when timer stops
{"type": "timer_stopped", "data": {...}}

# Broadcasted when entry completed
{"type": "time_entry_completed", "data": {...}}
```

**NEW Messages to Add (additive, non-breaking):**
```python
{"type": "session_started", "data": {...}}
{"type": "session_ended", "data": {...}}
{"type": "break_started", "data": {...}}
{"type": "break_ended", "data": {...}}
{"type": "meeting_started", "data": {...}}
{"type": "meeting_ended", "data": {...}}
{"type": "task_switched", "data": {...}}
```

**✅ SAFE**: Old frontend ignores unknown message types

---

### 🟡 MEDIUM: ActiveTimers Component ("Who's Working Now")

**Current Display:**
- User name, project, task, elapsed time
- Green dot = running

**NEW States to Display:**
| State | Visual | Color |
|-------|--------|-------|
| Working | Green dot, pulsing | 🟢 |
| On Break | Orange dot, "On Break" | 🟠 |
| In Meeting | Blue dot, "In Meeting" | 🔵 |
| Offline | Gray dot | ⚫ |

**REQUIRED CHANGES:**
1. API response adds `status` field: "working", "break", "meeting"
2. Frontend displays appropriate icon/color
3. **Backward compatible**: If `status` missing, assume "working"

---

### 🟢 LOW RISK: Export Functions

**Current Export** (from `export.py`):
```python
entries.append({
    "date": entry.start_time.strftime("%Y-%m-%d"),
    "start_time": entry.start_time.strftime("%H:%M:%S"),
    "end_time": entry.end_time.strftime(...) if entry.end_time else "Running",
    "duration": format_duration(duration),
    "project": row[1] or "No Project",
    "task": row[2] or "No Task",
    "description": entry.description or ""
})
```

**✅ NO CHANGES NEEDED:**
- TimeEntry structure unchanged
- New fields are additive (ignored in export)
- Session data not needed in time entry export

---

### 🟢 LOW RISK: Multi-tenancy Isolation

**Current Pattern:**
```python
company_id = get_company_filter(current_user)
query = query.where(User.company_id == company_id)
```

**NEW Tables Must Follow Same Pattern:**
```python
# WorkSession
company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=True)

# SessionBreak - inherits via WorkSession
# SessionMeeting - inherits via WorkSession
```

**✅ SAFE**: Copy existing multi-tenant patterns exactly

---

## 📋 DATABASE MIGRATION SAFETY CHECKLIST

### Pre-Migration Verification
- [ ] Full database backup taken
- [ ] Migration tested on staging/dev first
- [ ] Rollback script prepared and tested
- [ ] All new columns are NULLABLE or have defaults
- [ ] No columns removed from existing tables
- [ ] No column types changed in existing tables

### Migration Script Rules
```python
# ✅ SAFE: Add nullable column
op.add_column('time_entries', 
    sa.Column('work_session_id', sa.Integer(), nullable=True))

# ✅ SAFE: Add column with default
op.add_column('time_entries',
    sa.Column('is_paused', sa.Boolean(), nullable=False, server_default='false'))

# ❌ DANGEROUS: Remove column
# op.drop_column('time_entries', 'some_column')  # NEVER DO THIS

# ❌ DANGEROUS: Change column type
# op.alter_column('time_entries', 'duration_seconds', type_=...)  # AVOID
```

### Post-Migration Verification
- [ ] All existing queries still work
- [ ] Payroll calculations unchanged
- [ ] Reports show correct totals
- [ ] Running timers still display correctly
- [ ] WebSocket connections stable

---

## 🧪 REQUIRED REGRESSION TESTS

### Before Implementation, Write Tests For:

1. **Payroll Calculation Tests**
   - [ ] Hourly employee with existing time entries → same pay
   - [ ] Monthly employee → same pay
   - [ ] Daily employee → same pay
   - [ ] Mixed entries (old + new format) → correct total

2. **Report Accuracy Tests**
   - [ ] Dashboard today/week/month totals unchanged
   - [ ] Weekly summary unchanged
   - [ ] Project breakdown unchanged
   - [ ] Team timesheet unchanged

3. **Timer Operation Tests**
   - [ ] Start timer (no session) → auto-creates session
   - [ ] Stop timer → session stays active
   - [ ] Start new timer → uses existing session
   - [ ] End session → stops any running timer

4. **Break/Meeting Tests**
   - [ ] Start break → both timers pause
   - [ ] End break → both timers resume
   - [ ] Start meeting → only task pauses
   - [ ] End meeting → task resumes

5. **Export Tests**
   - [ ] Excel export includes all entries
   - [ ] PDF export formatted correctly
   - [ ] CSV export complete

---

## ⚠️ IMPLEMENTATION WARNINGS

### DO NOT:
1. ❌ Remove or rename any existing columns
2. ❌ Change the `duration_seconds` calculation logic
3. ❌ Modify existing API response structures
4. ❌ Change WebSocket message types that frontend depends on
5. ❌ Break the `is_running` flag meaning
6. ❌ Change how `end_time == None` indicates running timer

### MUST DO:
1. ✅ Make all new FK columns nullable
2. ✅ Provide default values for new boolean columns
3. ✅ Add new endpoints instead of modifying existing
4. ✅ Add new response fields as optional
5. ✅ Test payroll calculation before and after
6. ✅ Keep backward compatibility for 2+ releases

---

This document outlines all tasks required to implement a **Micro-Task Management** feature that allows users to:
1. Track a **Global/Daily Timer** (workday session) started once per day
2. Track **Task Timers** that can be rapidly switched without stopping the global timer
3. Use **Break/Lunch buttons** that pause the global timer
4. Use a **Meeting button** that pauses only the task timer (not the global timer)
5. Access **Task Reports** (admin sees all users, regular staff sees their own daily/weekly/monthly reports)

---

## 🔍 Current System Analysis

### Current Timer Architecture
The existing system has a **single timer model**:

**Database Model** (`backend/app/models/__init__.py`):
```python
class TimeEntry(Base):
    id, user_id, project_id, task_id
    start_time, end_time, duration_seconds
    description, is_running
    created_at, updated_at
```

**Current Limitations**:
- ❌ Only ONE timer can run at a time per user
- ❌ Starting a new task requires stopping the current timer
- ❌ No concept of "global workday session" vs "task timer"
- ❌ No break/lunch tracking with pause functionality
- ❌ No meeting mode that pauses task but tracks global work time
- ❌ Task reports only show time by task, not daily/weekly/monthly personal summaries

**Existing Timer Endpoints** (`backend/app/routers/time_entries.py`):
- `GET /api/time/timer` - Get current timer status
- `POST /api/time/start` - Start timer (fails if already running)
- `POST /api/time/stop` - Stop running timer

**Frontend Timer** (`frontend/src/stores/timerStore.ts`, `frontend/src/components/time/TimerWidget.tsx`):
- Single timer store with `isRunning`, `currentEntry`, `elapsedSeconds`
- Start/Stop button only
- No break or meeting functionality

---

## 🎯 Feature Requirements Breakdown

### Requirement 1: Two-Timer System (LINKED, NOT INDEPENDENT)

> ⚠️ **CRITICAL RELATIONSHIP**: The Global Timer and Task Timer are **LINKED**:
> - If Global Timer is ON → There MUST be an active task
> - If a Task is ON → Global Timer MUST be running
> - They start together, they run together
> - The ONLY exception: Break/Lunch pauses BOTH

| Component | Description |
|-----------|-------------|
| **Global Timer** | Tracks total workday/work time; runs whenever user is "working" |
| **Task Timer** | Tracks time on the CURRENT specific task |
| **Relationship** | **LINKED** - Starting a task starts/continues global timer. Stopping all tasks means no global time tracked. |

**Timer States:**
| State | Global Timer | Task Timer | Description |
|-------|--------------|------------|-------------|
| **Working on Task** | ✅ RUNNING | ✅ RUNNING | Normal work - both timers counting |
| **Break/Lunch** | ⏸️ PAUSED | ⏸️ PAUSED | User not working - nothing counts |
| **In Meeting** | ✅ RUNNING | ⏸️ PAUSED | Working (in meeting) but not on specific task |
| **No Task Started** | ⏹️ STOPPED | ⏹️ STOPPED | Workday not started or ended |

### Requirement 2: Seamless Task Switching (CRITICAL FEATURE)

> 🔥 **KEY FEATURE**: User can switch tasks INSTANTLY without any gap in time tracking

| Feature | Behavior |
|---------|----------|
| **Switch Task** | One-click/one-action to change from Task A to Task B |
| **No Stop Required** | User does NOT need to stop timer first |
| **No Gap** | Global timer NEVER stops during switch |
| **Atomic Operation** | Backend handles: stop Task A → start Task B in single transaction |
| **UI** | Quick dropdown or button to select new task while timer running |

**Example Flow:**
```
9:00 AM - Start Task A (Global: 0:00, Task A: 0:00)
10:30 AM - Switch to Task B (Global: 1:30, Task A: 1:30 SAVED, Task B: 0:00)
11:00 AM - Switch to Task C (Global: 2:00, Task B: 0:30 SAVED, Task C: 0:00)
... Global timer NEVER stopped, tasks seamlessly switched
```

### Requirement 3: Break/Lunch Button
| Feature | Behavior |
|---------|----------|
| **Break Button** | Pauses **BOTH** Global timer AND Task timer |
| **Lunch Button** | Same as break (configurable duration tracking) |
| **Resume** | Unpauses both timers, records break duration |
| **Effect** | NO work time counted during break - user is not working |

**Break Flow:**
```
10:00 AM - Working on Task A (Global: 1:00, Task A: 0:30)
10:00 AM - Start Break (Global: PAUSED at 1:00, Task A: PAUSED at 0:30)
10:15 AM - End Break (Global: RESUMES at 1:00, Task A: RESUMES at 0:30)
10:45 AM - Stop Task A (Global: 1:30, Task A: 1:00) - break time NOT counted
```

### Requirement 4: Meeting Button
| Feature | Behavior |
|---------|----------|
| **Meeting Button** | Pauses ONLY the current task timer; Global timer CONTINUES |
| **Why?** | User IS working (in meeting), just not on their specific task |
| **End Meeting** | Resumes task timer from where it left off |
| **Meeting Time** | Tracked separately; counts toward global work time but NOT toward task time |

**Meeting Flow:**
```
10:00 AM - Working on Task A (Global: 1:00, Task A: 0:30)
10:00 AM - Start Meeting (Global: RUNNING, Task A: PAUSED at 0:30)
10:30 AM - End Meeting (Global: 1:30, Task A: RESUMES at 0:30)
11:00 AM - Check totals (Global: 2:00, Task A: 1:00, Meeting: 0:30)
```

**Key Distinction:**
- **Break** = Not working → Global PAUSES
- **Meeting** = Working (but not on task) → Global CONTINUES, Task PAUSES

### Requirement 5: Task Reports
| User Role | Access |
|-----------|--------|
| **Admin** | All users' task reports (daily/weekly/monthly) |
| **Regular Staff** | Only their own task reports |
| **Report Types** | Daily breakdown, weekly summary, monthly summary |

---

## ✅ Implementation Tasks

### Phase 1: Database Schema Changes
**Priority: CRITICAL - Must be done first**  
**Estimated: 6-8 hours**

#### Task 1.1: Create New Database Models
- [ ] Create `WorkSession` model (global daily timer)
  ```python
  class WorkSession(Base):
      __tablename__ = "work_sessions"
      id: int
      user_id: int (FK to users)
      date: date  # One session per day
      start_time: datetime
      end_time: datetime (nullable, null = still active)
      total_seconds: int (computed)
      break_seconds: int (total break time)
      meeting_seconds: int (total meeting time)
      status: Enum("active", "paused", "completed")
      created_at, updated_at
  ```

- [ ] Create `SessionBreak` model (tracks breaks/lunch)
  ```python
  class SessionBreak(Base):
      __tablename__ = "session_breaks"
      id: int
      work_session_id: int (FK to work_sessions)
      break_type: Enum("break", "lunch", "other")
      start_time: datetime
      end_time: datetime (nullable)
      duration_seconds: int
      notes: str (optional)
  ```

- [ ] Create `SessionMeeting` model (tracks meetings)
  ```python
  class SessionMeeting(Base):
      __tablename__ = "session_meetings"
      id: int
      work_session_id: int (FK to work_sessions)
      start_time: datetime
      end_time: datetime (nullable)
      duration_seconds: int
      description: str (optional, meeting subject)
  ```

- [ ] Modify existing `TimeEntry` model
  ```python
  # Add new fields:
  work_session_id: int (FK to work_sessions, nullable for backward compat)
  paused_at: datetime (nullable, for meeting pause)
  pause_seconds: int (total pause time for this entry)
  ```

#### Task 1.2: Create Alembic Migration
- [ ] Write migration script for new tables
- [ ] Write migration to add new columns to `time_entries`
- [ ] Add proper indexes for performance
- [ ] Test migration on dev database
- [ ] Test rollback capability

**Files to modify/create**:
- `backend/app/models/__init__.py` - Add new models
- `backend/alembic/versions/xxx_add_micro_task_management.py` - Migration

---

### Phase 2: Backend API Development
**Priority: HIGH**  
**Estimated: 12-16 hours**

#### Task 2.1: Work Session Endpoints
- [ ] `POST /api/sessions/start` - Start daily work session
  - Creates new WorkSession if none exists for today
  - Returns error if session already active
  - Auto-creates session on first task start (optional)
  
- [ ] `POST /api/sessions/end` - End daily work session
  - Stops any running task timers
  - Calculates final totals
  - Marks session as completed

- [ ] `GET /api/sessions/current` - Get current session status
  - Returns active session with elapsed time
  - Includes break/meeting totals
  - Shows current task if any

- [ ] `GET /api/sessions/history` - Get session history
  - Paginated list of past sessions
  - Filter by date range

#### Task 2.2: Break/Lunch Endpoints
- [ ] `POST /api/sessions/break/start` - Start break
  - Pauses work session
  - Pauses current task timer (if any)
  - Creates SessionBreak record
  - Params: `break_type` (break/lunch)

- [ ] `POST /api/sessions/break/end` - End break
  - Resumes work session
  - Resumes task timer (if was running)
  - Updates SessionBreak with duration

- [ ] `GET /api/sessions/breaks` - Get breaks for session
  - List all breaks for current/specified session

#### Task 2.3: Meeting Endpoints
- [ ] `POST /api/sessions/meeting/start` - Start meeting
  - Does NOT pause work session (global timer continues)
  - DOES pause current task timer
  - Creates SessionMeeting record
  - Optional: `description` param

- [ ] `POST /api/sessions/meeting/end` - End meeting
  - Resumes task timer
  - Updates SessionMeeting with duration

- [ ] `GET /api/sessions/meetings` - Get meetings for session

#### Task 2.4: Seamless Task Switching (CRITICAL)
- [ ] `POST /api/time/switch-task` - **Atomic task switch without stopping timer**
  - **MUST be atomic** - single transaction, no time gaps
  - Stops current task timer (records time to DB)
  - Immediately starts new task timer (same millisecond)
  - Global timer NEVER interrupted
  - Same project or different project supported
  - Request body: `{ new_project_id, new_task_id, description? }`
  - Returns: `{ stopped_entry, started_entry, global_elapsed_seconds }`
  
- [ ] Implement **linked timer logic** in all endpoints:
  - Starting a task → Global session auto-starts if not running
  - No active task allowed without global session
  - No global session without at least starting one task
  
- [ ] Modify `POST /api/time/start` - Enforce linked timer rules
  - If no active session → auto-start session + start task
  - If session paused (on break) → reject with error "End break first"
  - Link time entry to work session

- [ ] Modify `POST /api/time/stop` - Handle linked timer state
  - Stop task timer
  - Global session stays active (user may switch to another task)
  - If user wants to end workday, use separate `/sessions/end` endpoint

#### Task 2.5: Schemas & Validation
- [ ] Create Pydantic schemas for all new endpoints
- [ ] Add validation for **LINKED TIMER business rules**:
  - ✅ Starting task → auto-starts global session if needed
  - ❌ Can't have global session running without a task (except during meeting)
  - ❌ Can't start task while on break → "End break first"
  - ❌ Can't start break during meeting → "End meeting first"
  - ❌ Can't start meeting during break → "End break first"
  - ❌ Can't switch tasks during break → "End break first"
  - ✅ Can switch tasks during meeting → ends meeting, starts new task
  - ✅ Session must be active for all task operations

**Files to create/modify**:
- `backend/app/routers/sessions.py` - NEW: All session endpoints
- `backend/app/routers/time_entries.py` - Modify existing
- `backend/app/schemas/sessions.py` - NEW: Pydantic schemas
- `backend/app/main.py` - Register new router

---

### Phase 3: Task Reports API
**Priority: HIGH**  
**Estimated: 8-10 hours**

#### Task 3.1: Personal Task Reports
- [ ] `GET /api/reports/tasks/daily` - Daily task breakdown
  - All tasks worked on for a specific date
  - Time per task
  - Break/meeting time
  - Total work time vs task time

- [ ] `GET /api/reports/tasks/weekly` - Weekly task summary
  - Tasks by day for the week
  - Daily totals
  - Weekly total
  - Most worked tasks

- [ ] `GET /api/reports/tasks/monthly` - Monthly task overview
  - Weekly breakdowns
  - Task distribution
  - Trends vs previous month

#### Task 3.2: Admin Task Reports
- [ ] `GET /api/reports/admin/tasks/daily` - All users' daily tasks
  - Admin only
  - Filter by user, team, project
  - Aggregated view option

- [ ] `GET /api/reports/admin/tasks/weekly` - All users' weekly tasks
  - Same filters as daily
  - Comparison view

- [ ] `GET /api/reports/admin/tasks/monthly` - All users' monthly tasks
  - Department/team summaries
  - Individual breakdowns

#### Task 3.3: Export Support
- [ ] Extend existing export endpoints for new report types
- [ ] CSV export for task reports
- [ ] PDF export for task reports

**Files to create/modify**:
- `backend/app/routers/reports.py` - Add new endpoints
- `backend/app/routers/export.py` - Extend for task reports

---

### Phase 4: Frontend State Management
**Priority: HIGH**  
**Estimated: 8-10 hours**

#### Task 4.1: Session Store
- [ ] Create `sessionStore.ts` - Zustand store for work session
  ```typescript
  interface SessionState {
    currentSession: WorkSession | null;
    isSessionActive: boolean;
    isOnBreak: boolean;
    isInMeeting: boolean;
    sessionElapsedSeconds: number;
    breakElapsedSeconds: number;
    meetingElapsedSeconds: number;
    
    // Actions
    startSession: () => Promise<void>;
    endSession: () => Promise<void>;
    startBreak: (type: 'break' | 'lunch') => Promise<void>;
    endBreak: () => Promise<void>;
    startMeeting: (description?: string) => Promise<void>;
    endMeeting: () => Promise<void>;
  }
  ```

#### Task 4.2: Modify Timer Store
- [ ] Update `timerStore.ts` for task-only tracking
  ```typescript
  interface TimerState {
    // Existing fields...
    workSessionId: number | null;
    isPausedForMeeting: boolean;
    pauseSeconds: number;
    
    // New action
    switchTask: (newTaskData: TaskSwitchData) => Promise<void>;
  }
  ```

#### Task 4.3: API Client Updates
- [ ] Add session API methods to `api/client.ts`
- [ ] Add task report API methods
- [ ] Handle new response types

**Files to create/modify**:
- `frontend/src/stores/sessionStore.ts` - NEW
- `frontend/src/stores/timerStore.ts` - Modify
- `frontend/src/api/client.ts` - Add new endpoints
- `frontend/src/types/index.ts` - Add new types

---

### Phase 5: Frontend UI Components
**Priority: HIGH**  
**Estimated: 12-15 hours**

#### Task 5.1: Session Control Widget
- [ ] Create `SessionWidget.tsx` - Global session controls
  - Start/End Workday button
  - Session elapsed time display
  - Visual indicator (green when active)
  - Compact mode for header

#### Task 5.2: Break/Meeting Controls
- [ ] Create `BreakControls.tsx`
  - Break button (coffee icon)
  - Lunch button (utensils icon)
  - Active break timer display
  - Resume button when on break

- [ ] Create `MeetingControls.tsx`
  - Meeting toggle button
  - Meeting timer display
  - Optional meeting description input
  - End meeting button

#### Task 5.3: Enhanced Timer Widget with Seamless Task Switching
- [ ] Modify `TimerWidget.tsx` for **instant task switching**
  - **Quick Switch Dropdown**: Always visible when timer running
    - Shows all available tasks grouped by project
    - Single click = instant switch (no confirmation)
    - Keyboard shortcut support (e.g., Ctrl+T to open)
  - **"Switch Task" button**: Alternative to dropdown
    - Opens task selector modal
    - Recent tasks shown first
  - Current task clearly displayed with project badge
  - Task elapsed time (separate from global time)
  - **NO "Stop" required before switching** - this is key UX

- [ ] Add visual states:
  - 🟢 Normal working (green pulse) - Global ON, Task ON
  - 🟠 On break (orange, paused icon) - Global PAUSED, Task PAUSED
  - 🔵 In meeting (blue, meeting icon) - Global ON, Task PAUSED
  - ⚫ Session ended (gray) - Nothing running

- [ ] Show both timers clearly:
  ```
  ┌─────────────────────────────────────────────┐
  │ 🟢 WORKDAY: 4:32:15              [End Day]  │
  │ ─────────────────────────────────────────── │
  │ Current Task: Fix login bug                 │
  │ Project: TimeTracker                        │
  │ Task Time: 1:15:42    [Switch Task ▼]       │
  │ ─────────────────────────────────────────── │
  │ [☕ Break] [🍽️ Lunch] [📅 Meeting]          │
  └─────────────────────────────────────────────┘
  ```

#### Task 5.4: Combined Dashboard Widget
- [ ] Create `WorkdayWidget.tsx` - All-in-one component
  - Session status at top
  - Task timer in middle
  - Break/Meeting buttons at bottom
  - Collapsible sections
  - Mobile responsive

**Files to create/modify**:
- `frontend/src/components/time/SessionWidget.tsx` - NEW
- `frontend/src/components/time/BreakControls.tsx` - NEW
- `frontend/src/components/time/MeetingControls.tsx` - NEW
- `frontend/src/components/time/WorkdayWidget.tsx` - NEW
- `frontend/src/components/time/TimerWidget.tsx` - MAJOR MODIFY
- `frontend/src/pages/TimePage.tsx` - Update layout

---

### Phase 6: Task Reports UI
**Priority: MEDIUM**  
**Estimated: 8-10 hours**

#### Task 6.1: Personal Task Reports Page
- [ ] Create `MyTaskReportsPage.tsx`
  - Date range selector (daily/weekly/monthly)
  - Task breakdown table
  - Time distribution chart
  - Break/meeting summary
  - Export buttons

#### Task 6.2: Admin Task Reports Page
- [ ] Create `AdminTaskReportsPage.tsx` (or extend `AdminReportsPage.tsx`)
  - User filter dropdown
  - Team/department filter
  - Same visualizations as personal
  - Comparison view option

#### Task 6.3: Report Components
- [ ] Create `TaskReportTable.tsx` - Reusable table
- [ ] Create `TaskDistributionChart.tsx` - Pie/Bar chart
- [ ] Create `WorkdaySummaryCard.tsx` - Stats card

**Files to create/modify**:
- `frontend/src/pages/MyTaskReportsPage.tsx` - NEW
- `frontend/src/pages/AdminTaskReportsPage.tsx` - NEW (or modify existing)
- `frontend/src/components/reports/TaskReportTable.tsx` - NEW
- `frontend/src/components/reports/TaskDistributionChart.tsx` - NEW

---

### Phase 7: Navigation & Routing
**Priority: MEDIUM**  
**Estimated: 2-3 hours**

#### Task 7.1: Route Updates
- [ ] Add route for `/my-task-reports`
- [ ] Add route for `/admin/task-reports` (admin only)
- [ ] Update navigation menu

#### Task 7.2: Navigation Menu
- [ ] Add "My Task Reports" link for all users
- [ ] Add "Team Task Reports" link for admins
- [ ] Update sidebar icons

**Files to modify**:
- `frontend/src/App.tsx` - Add routes
- `frontend/src/components/layout/Sidebar.tsx` - Add menu items

---

### Phase 8: WebSocket Integration
**Priority: MEDIUM**  
**Estimated: 4-5 hours**

#### Task 8.1: Real-time Session Updates
- [ ] Broadcast session start/end to admins
- [ ] Broadcast break/meeting status changes
- [ ] Update "Who's Working Now" with break/meeting status

#### Task 8.2: Frontend WebSocket Handlers
- [ ] Handle session status changes
- [ ] Update ActiveTimers component for new states
- [ ] Show break/meeting indicators in team view

**Files to modify**:
- `backend/app/routers/sessions.py` - Add WebSocket broadcasts
- `backend/websocket/manager.py` - Add new message types
- `frontend/src/contexts/WebSocketContext.tsx` - Handle new messages
- `frontend/src/components/ActiveTimers.tsx` - Show new states

---

### Phase 9: Testing
**Priority: HIGH**  
**Estimated: 6-8 hours**

#### Task 9.1: Backend Tests
- [ ] Unit tests for session endpoints
- [ ] Unit tests for break/meeting endpoints
- [ ] Unit tests for task switching
- [ ] Unit tests for task reports
- [ ] Integration tests for full workflow

#### Task 9.2: Frontend Tests
- [ ] Unit tests for sessionStore
- [ ] Unit tests for modified timerStore
- [ ] Component tests for new widgets
- [ ] E2E tests for full workflow

**Files to create**:
- `backend/tests/test_sessions.py` - NEW
- `backend/tests/test_task_reports.py` - NEW
- `frontend/src/stores/sessionStore.test.ts` - NEW
- `frontend/src/components/time/*.test.tsx` - NEW
- `frontend/e2e/sessions.spec.ts` - NEW

---

### Phase 10: Documentation & Polish
**Priority: MEDIUM**  
**Estimated: 3-4 hours**

#### Task 10.1: API Documentation
- [ ] Document all new endpoints in `docs/API.md`
- [ ] Add OpenAPI/Swagger annotations

#### Task 10.2: User Documentation
- [ ] Update `docs/USER_QUICK_START.md` with new features
- [ ] Create guide for micro-task management
- [ ] Add FAQ entries

#### Task 10.3: UI Polish
- [ ] Ensure mobile responsiveness
- [ ] Add loading states
- [ ] Add error handling
- [ ] Add success notifications

---

## 📊 Implementation Summary

| Phase | Tasks | Hours Est. | Priority |
|-------|-------|------------|----------|
| 1. Database Schema | 2 major tasks | 6-8 hrs | CRITICAL |
| 2. Backend API | 5 task groups | 12-16 hrs | HIGH |
| 3. Task Reports API | 3 task groups | 8-10 hrs | HIGH |
| 4. Frontend State | 3 stores | 8-10 hrs | HIGH |
| 5. UI Components | 4 component groups | 12-15 hrs | HIGH |
| 6. Reports UI | 3 pages | 8-10 hrs | MEDIUM |
| 7. Navigation | 2 tasks | 2-3 hrs | MEDIUM |
| 8. WebSocket | 2 task groups | 4-5 hrs | MEDIUM |
| 9. Testing | 2 test suites | 6-8 hrs | HIGH |
| 10. Documentation | 3 tasks | 3-4 hrs | MEDIUM |
| **TOTAL** | | **70-89 hrs** | |

---

## ⚠️ Technical Considerations

### Database Migration Strategy
1. **Backward Compatibility**: Existing `TimeEntry` records will have `work_session_id = NULL`
2. **Data Integrity**: Foreign key constraints with `ON DELETE CASCADE` for sessions
3. **Migration**: Run during maintenance window, test rollback first

### Performance Considerations
1. **Indexes**: Add indexes on `work_sessions(user_id, date)`, `session_breaks(work_session_id)`
2. **Caching**: Consider Redis caching for active session lookups
3. **Query Optimization**: Eager load relationships in reports

### UI/UX Considerations
1. **Mobile First**: Design for small screens first
2. **Quick Actions**: Minimize clicks for task switching
3. **Visual Feedback**: Clear states for active/paused/meeting
4. **Keyboard Shortcuts**: Consider hotkeys for power users

### WebSocket Considerations
1. **State Sync**: Ensure UI reflects real state on reconnect
2. **Race Conditions**: Handle concurrent start/stop requests
3. **Offline Mode**: Queue actions when disconnected

---

## 🚀 Recommended Implementation Order

1. **Week 1**: Phase 1 (Database) + Phase 2 (Backend API core)
2. **Week 2**: Phase 4 (Frontend State) + Phase 5 (UI Components)
3. **Week 3**: Phase 3 (Reports API) + Phase 6 (Reports UI)
4. **Week 4**: Phase 7-10 (Integration, Testing, Polish)

---

## 📝 Open Questions for User

1. ~~**Auto-start Session**: Should starting a task auto-start the work session if none exists?~~ ✅ **ANSWERED: YES** - Timers are linked, starting task auto-starts session
2. **Break Duration Limits**: Should there be configurable max break durations?
3. **Meeting Categories**: Should meetings have categories (internal/external/client)?
4. **Overtime Calculation**: How should overtime work with the new session model?
5. **Historical Data**: Should existing time entries be migrated to sessions?
6. **Default Task**: Should there be a "General Work" task for when user starts day but hasn't picked specific task?
7. **Meeting as Task?**: Should "In Meeting" automatically create a special "Meeting" task entry, or just pause current task and track meeting time separately?

---

## 🚀 DEPLOYMENT SAFETY PLAN

### Phase 1: Feature Flag Deployment (Zero Risk)

```python
# backend/app/core/feature_flags.py
FEATURE_FLAGS = {
    "micro_task_management": False,  # Start disabled
    "session_widget": False,
    "break_controls": False,
    "meeting_controls": False,
    "task_reports": False,
}
```

**Benefits:**
- Deploy code to production with feature disabled
- Enable for specific users/companies for testing
- Instant rollback by disabling flag
- No database changes required initially

### Phase 2: Database Migration (Low Risk)

**Migration Order:**
1. Add new tables (WorkSession, SessionBreak, SessionMeeting)
2. Add nullable columns to TimeEntry (`work_session_id`, `is_paused`, `pause_seconds`)
3. Create indexes for performance
4. Run migration during low-traffic window

**Rollback Plan:**
```sql
-- If needed, remove new columns (data loss only on new data)
ALTER TABLE time_entries DROP COLUMN IF EXISTS work_session_id;
ALTER TABLE time_entries DROP COLUMN IF EXISTS is_paused;
ALTER TABLE time_entries DROP COLUMN IF EXISTS pause_seconds;
DROP TABLE IF EXISTS session_meetings;
DROP TABLE IF EXISTS session_breaks;
DROP TABLE IF EXISTS work_sessions;
```

### Phase 3: Backend API Deployment (Medium Risk)

**Deployment Checklist:**
- [ ] New endpoints added (don't modify existing)
- [ ] Old endpoints still work identically
- [ ] WebSocket messages backward compatible
- [ ] Error handling comprehensive
- [ ] Logging added for debugging

### Phase 4: Frontend Deployment (Medium Risk)

**Deployment Checklist:**
- [ ] New components added
- [ ] Old components still work
- [ ] Feature flag controls visibility
- [ ] Graceful degradation if API fails
- [ ] Mobile responsive tested

### Phase 5: Gradual Rollout

| Week | Feature Flag Status | Users |
|------|-------------------|-------|
| 1 | Enabled for admin only | 1-5 users |
| 2 | Enabled for beta testers | 10-20 users |
| 3 | Enabled for one company | 50-100 users |
| 4 | Enabled for all | All users |

---

## 📊 MONITORING & ALERTING

### Key Metrics to Monitor Post-Deployment

```python
# Add to monitoring dashboard
metrics = {
    "timer_start_success_rate": "Should be >99.9%",
    "timer_stop_success_rate": "Should be >99.9%",
    "payroll_calculation_errors": "Should be 0",
    "report_generation_errors": "Should be 0",
    "websocket_connection_drops": "Should be <1%",
    "api_response_time_p99": "Should be <500ms",
}
```

### Alert Triggers
- 🚨 **CRITICAL**: Payroll calculation error → Immediate page
- 🚨 **CRITICAL**: Report total mismatch → Immediate page  
- ⚠️ **WARNING**: Timer API error rate >1% → Slack alert
- ⚠️ **WARNING**: WebSocket reconnection rate >5% → Slack alert

---

## ✅ FINAL COMPATIBILITY VERDICT

### Will This Break Existing Functionality?

| Component | Verdict | Reasoning |
|-----------|---------|-----------|
| **Payroll Calculations** | ✅ NO | Uses `duration_seconds` which stays unchanged |
| **Reports & Dashboard** | ✅ NO | Queries `TimeEntry` which stays unchanged |
| **Timer Start/Stop** | ✅ NO | Existing endpoints work, add new ones |
| **WebSocket Updates** | ✅ NO | Add new message types, old ones work |
| **Export Functions** | ✅ NO | Uses same `TimeEntry` fields |
| **User Permissions** | ✅ NO | Add new permissions, existing unchanged |
| **Multi-tenancy** | ✅ NO | New tables follow same patterns |
| **Historical Data** | ✅ NO | Old entries work, don't need session |

### Key Guarantees

1. **GUARANTEE**: All existing time entries remain valid and unchanged
2. **GUARANTEE**: Payroll calculations produce identical results
3. **GUARANTEE**: Reports show identical totals for existing data
4. **GUARANTEE**: Existing API clients continue working
5. **GUARANTEE**: WebSocket connections remain stable
6. **GUARANTEE**: Rolling back is possible at every phase

### Conditions for Safe Implementation

1. ✅ All new columns are **nullable** or have **defaults**
2. ✅ No existing columns are **removed** or **renamed**
3. ✅ No existing endpoints change **response structure**
4. ✅ Feature flags allow **gradual rollout**
5. ✅ Comprehensive **regression tests** before deployment
6. ✅ **Monitoring** in place before going live

---

├── src/stores/sessionStore.test.ts
├── src/components/time/SessionWidget.tsx
├── src/components/time/BreakControls.tsx
├── src/components/time/MeetingControls.tsx
├── src/components/time/WorkdayWidget.tsx
├── src/components/reports/TaskReportTable.tsx
├── src/components/reports/TaskDistributionChart.tsx
├── src/pages/MyTaskReportsPage.tsx
├── src/pages/AdminTaskReportsPage.tsx
└── e2e/sessions.spec.ts
```

### Files to Modify (10+)
```
backend/
├── app/models/__init__.py
├── app/routers/time_entries.py
├── app/routers/reports.py
├── app/main.py
└── websocket/manager.py

frontend/
├── src/stores/timerStore.ts
├── src/api/client.ts
├── src/types/index.ts
├── src/components/time/TimerWidget.tsx
├── src/pages/TimePage.tsx
├── src/App.tsx
└── src/components/layout/Sidebar.tsx
```

---

**End of Assessment**

*This document should be used as the implementation roadmap. Each task should be checked off as completed. Create separate branch for this feature: `feature/micro-task-management`*
