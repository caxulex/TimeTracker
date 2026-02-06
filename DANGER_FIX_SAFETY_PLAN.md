# 🛡️ Danger Fix Safety Plan — Feb 6, 2026

## Purpose

This document tracks all fixes being applied to resolve dangers identified in the
session's recent changes (task switching, break/meeting timer, nullable `project_id`).
**Read this before every edit to remember context and avoid regressions.**

---

## 📐 Current Working Logic (DO NOT BREAK)

### Timer Behavior Rules

| State     | Session Clock (global) | Task Timer | Running TimeEntry |
|-----------|:---------------------:|:----------:|:-----------------:|
| Working   | ✅ Ticking            | ✅ Ticking | `is_running=true, project_id=N` |
| Break     | ❄️ Paused             | ❄️ Paused  | `is_paused=true` (same entry) |
| Meeting   | ✅ Ticking            | ❄️ Paused  | Old entry STOPPED → new entry with `project_id=NULL` |
| Idle      | ❄️ No session         | ❄️ None    | No entry |

### Break Flow (work_sessions.py)

1. `POST /break/start` → checks no active break/meeting → pauses running TimeEntry (`is_paused=true, paused_at=now`) → session status="break"
2. `POST /break/end` → finds active break → ends it → resumes paused entries (`is_paused=false`, adds pause_seconds) → session status="active"

### Meeting Flow (work_sessions.py)

1. `POST /meeting/start` → checks no active break/meeting → **STOPS** running TimeEntry (sets `end_time`, `is_running=false`) → stores its ID in `paused_entry_id` → creates NEW meeting TimeEntry (`project_id=NULL`, `description="[Meeting] ..."`) → session status="meeting"
2. `POST /meeting/end` → finds active meeting → stops meeting TimeEntry → creates BRAND NEW resumed TimeEntry (copies `project_id, task_id, description` from paused entry) → session status="active"

### /timer Endpoint Logic (time_entries.py, lines 150-280)

1. Check for active WorkSession → if none, auto-stop orphan entries, return `is_running=false`
2. Check if in a meeting (WorkSession.meetings where `end_time IS NULL`)
   - If yes: return the **paused task entry** (from `paused_entry_id`) with `is_paused=true, is_running=true`
   - Frontend sees `isPaused=true` → freezes task timer display
3. Normal case: find entry with `end_time IS NULL` → return it with calculated elapsed

### /stop Endpoint Logic (time_entries.py, lines 441-510)

- Finds entry where `end_time IS NULL` → sets `end_time`, `duration_seconds`, `is_running=false`
- Gets project/task names → broadcasts via WebSocket
- **⚠️ DANGER: No check for meeting/break state — will stop the MEETING entry if called during meeting**

### /switch Endpoint Logic (time_entries.py, lines 525-650)

- Finds entry where `end_time IS NULL` → stops it → creates new entry with new project/task
- Links new entry to same `work_session_id`
- **⚠️ DANGER: No check for meeting/break state — will stop the MEETING entry if called during meeting**

### /active Endpoint (time_entries.py, ~line 295)

- ✅ Already uses `outerjoin(Project)` — safe for meeting entries

### Frontend TimerWidget (TimerWidget.tsx)

- Project/task dropdowns: `disabled={isLoading}` only
- Stop button: enabled whenever `isRunning=true`
- **⚠️ DANGER: No check for `isPaused` — user can stop/switch during meeting/break**

### Frontend timerStore (timerStore.ts)

- `fetchTimer()` → sets `isPaused` from backend response
- `updateElapsed()` → correctly checks `!isPaused` before incrementing
- `switchTimer()` → resets `elapsedSeconds: 0`, keeps `isRunning: true`

### Session Clock (sessionStore.ts)

- `global_timer_seconds = elapsed - total_break_seconds` (meetings NOT subtracted — correct)
- `current_break_duration` subtracted if break is active

---

## 🔴 Dangers to Fix

### Fix #1: /stop — Add meeting/break guard
**File:** `backend/app/routers/time_entries.py` lines ~441-460
**Problem:** `/stop` finds `TimeEntry WHERE end_time IS NULL`. During a meeting, the running entry IS the meeting entry (`project_id=NULL`). Stopping it corrupts state:
- SessionMeeting record stays open (no `end_time`)
- Session stuck in "meeting" status
- Paused task entry never resumed
**Fix:** After finding the entry, check if user has an active meeting or break. If so, return 400.
**Guard logic:**
```python
# Check for active meeting — don't allow /stop during meeting
session_result = await db.execute(
    select(WorkSession)
    .where(and_(WorkSession.user_id == current_user.id, WorkSession.end_time.is_(None)))
    .options(selectinload(WorkSession.meetings), selectinload(WorkSession.breaks))
)
active_session = session_result.scalar_one_or_none()
if active_session:
    for mtg in active_session.meetings:
        if mtg.end_time is None:
            raise HTTPException(status_code=400, detail="Cannot stop timer during a meeting. End the meeting first.")
    for brk in active_session.breaks:
        if brk.end_time is None:
            raise HTTPException(status_code=400, detail="Cannot stop timer during a break. End the break first.")
```
**Must still work after:** Normal stop (working state), stop with no running timer (404)

### Fix #2: /switch — Add meeting/break guard
**File:** `backend/app/routers/time_entries.py` lines ~525-545
**Problem:** Same as #1 — `/switch` would kill the meeting entry and start a new task entry.
**Fix:** Same guard as #1, after finding `old_entry`.
**Must still work after:** Normal task switch (working state), switch with no timer (404)

### Fix #3: INNER JOINs → outerjoin (9 locations)
**Files & lines:**
1. `reports.py:421` — `select(TimeEntry, Project.name).join(Project, ...)`
2. `reports.py:479` — `select(...).join(Task, ...).join(Project, ...)`
3. `reports.py:570` — `select(TimeEntry, Project.name, User.name).join(Project, ...)`
4. `reports.py:684` — `select(...).join(Project, ...).outerjoin(Task, ...)`
5. `reports.py:1305` — `select(...).join(Project, ...)`
6. `admin.py:102` — `select(...).join(Project, ...)`
7. `admin.py:348` — `select(TimeEntry, User.name, Project.name).join(Project, ...)`
8. `websocket.py:239` — `select(...).join(Project, ...)`
9. `suggestion_service.py:250` — `select(...).join(Project, ...)`

**Problem:** Meeting entries have `project_id=NULL`. `INNER JOIN` drops them. Reports undercount hours.
**Fix:** Change `.join(Project, ...)` to `.outerjoin(Project, ...)` in all 9 locations.
**Handle NULL:** Where `project_name` is used, treat `None` as `"Meeting"` or `"(No Project)"`.
**Must still work after:** All reports still show correct totals for normal task entries. Meeting entries appear with "(No Project)" or "Meeting" label.

### Fix #4: Unguarded project_name lookups (3 locations)
**File:** `backend/app/routers/time_entries.py`
1. **Line ~465** (`/stop`): `select(Project.name).where(Project.id == entry.project_id)` — returns None when `project_id` is None
2. **Line ~870** (GET `/{entry_id}`): same pattern
3. **Line ~959** (PUT `/{entry_id}`): same pattern

**Fix:** Add `if entry.project_id:` guard, else `project_name = None` (or "Meeting")
**Must still work after:** Normal entries with project_id still get their project name

### Fix #5: Frontend — disable controls during meeting/break
**File:** `frontend/src/components/time/TimerWidget.tsx`
**Problem:** Dropdowns and Stop button are enabled during meeting/break (when `isPaused=true`)
**Fix:** Disable project dropdown, task dropdown, and Stop button when `isPaused` is true
**Must still work after:** Controls work normally when not paused; description input stays editable

### Fix #6: Duplicate WorkSession query in /timer
**File:** `backend/app/routers/time_entries.py` lines 158-210
**Problem:** Two separate `SELECT WorkSession WHERE ...` queries for the same session:
1. Line 158: plain select (orphan check)
2. Line 197: select with `selectinload(meetings)` (meeting detection)
**Fix:** Merge into one query with eager loading from the start
**Must still work after:** Orphan cleanup logic, meeting detection, normal timer return

---

## ✅ Completion Checklist

- [x] Fix #1: /stop meeting/break guard added
- [x] Fix #2: /switch meeting/break guard added  
- [x] Fix #3: All 9 INNER JOINs changed to outerjoin
- [x] Fix #4: 3 project_name lookups guarded
- [x] Fix #5: Frontend controls disabled during meeting/break
- [x] Fix #6: Duplicate WorkSession query merged
- [ ] All existing features still work:
  - [ ] Start/stop timer (normal flow)
  - [ ] Task switching while working
  - [ ] Break start/end
  - [ ] Meeting start/end (pauses task, resumes after)
  - [ ] Session clock counts breaks but not meetings
  - [ ] Reports show correct totals
  - [ ] Admin dashboard shows correct data
  - [ ] WebSocket broadcasts work
  - [ ] /active endpoint shows active timers
  - [ ] Manual time entry creation works

---

## 📝 Change Log

| # | Fix | Status | Files Modified |
|---|-----|--------|----------------|
| 1 | /stop guard | ✅ Done | time_entries.py |
| 2 | /switch guard | ✅ Done | time_entries.py |
| 3 | INNER → outerjoin | ✅ Done | reports.py, admin.py, websocket.py, suggestion_service.py |
| 4 | project_name guards | ✅ Done | time_entries.py |
| 5 | Frontend disable controls | ✅ Done | TimerWidget.tsx |
| 6 | Merge duplicate query | ✅ Done | time_entries.py |
