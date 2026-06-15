# Break/Task Timer Integrity Investigation (2026-06-15)

## Scope
Read-only investigation of break behavior across backend + frontend, with attempted historical overlap audit.
No application code or data was modified.

## Executive Summary
- Backend break handling is already implemented as **pause/resume** (Option B), not stop/restart.
- On break start, the active `TimeEntry` is marked paused (`is_paused=true`, `paused_at=now`), and on break end it is resumed while accumulating `pause_seconds`.
- The observed "Current Task keeps ticking" behavior is most likely a **frontend state reconciliation bug**, not backend break logic.
- Likely root cause: `timerStore.applyServerState` early-returns when the same entry ID is returned, and therefore skips updating `isPaused` when a break starts/ends.
- Historical data quantification against the configured DB could not be completed in this environment because the configured PostgreSQL endpoint (`localhost:5434`) is unreachable here.

---

## Part A - Backend Logic Findings

### 1) How breaks are stored
Break data model and related tables:
- `session_breaks` table via migration `017_add_micro_task_management.py`.
- ORM model: `SessionBreak` in `backend/app/models/__init__.py`.
- Related session model: `WorkSession` (`work_sessions` table) with relationship to `SessionBreak`.
- Time pause metadata on entries (also introduced in migration 017):
  - `time_entries.is_paused`
  - `time_entries.paused_at`
  - `time_entries.pause_seconds`

Evidence:
- `backend/alembic/versions/017_add_micro_task_management.py`
- `backend/app/models/__init__.py`

### 2) What happens to active TimeEntry when break starts
Endpoint: `POST /api/work-sessions/break/start`

Current behavior:
- Finds active work session.
- Prevents starting break if another break/meeting is active.
- For each running entry in session:
  - sets `entry.is_paused = True`
  - sets `entry.paused_at = now`
- Sets `session.status = "break"`
- Creates a `SessionBreak` row with `start_time=now`.

Important:
- **`end_time` is NOT set on break start**.
- Entry remains open and is explicitly paused.

Evidence:
- `backend/app/routers/work_sessions.py` (`start_break`)

### 3) Backend code paths handling break start/end
Primary path:
- `backend/app/routers/work_sessions.py`
  - `start_break`
  - `end_break`

Supporting paths:
- `backend/app/routers/time_entries.py`
  - `GET /api/time/timer` returns `current_entry.is_paused` / `paused_at` / `pause_seconds`.
- `backend/app/utils/timer_elapsed.py`
  - Freeze elapsed while paused at `(paused_at - start_time) - pause_seconds`.
- `backend/app/routers/work_sessions.py` helper `_refresh_active_timer_cache`
  - Rebuilds active timer cache using pause-aware elapsed computation.
- `backend/app/routers/websocket.py`
  - Broadcasts `break_started`, `break_ended`, and canonical `timer_updated` events.

Searched terms mapped:
- `break_started`, `start_break`, `is_paused`, `paused_at`, `pause_seconds` in routers/services/utils.
- No distinct backend functions named `pause_entry`/`resume_entry`; pause/resume occurs inline in break handlers.

### 4) What happens when break ends
Endpoint: `POST /api/work-sessions/break/end`

Current behavior:
- Finds active break (`session_breaks.end_time IS NULL`).
- Sets break `end_time` and `duration_seconds`.
- Updates `session.total_break_seconds` and `session.status = "active"`.
- For paused entries:
  - sets `is_paused = False`
  - increments `pause_seconds += (now - paused_at)`
  - clears `paused_at`

Important:
- **No new TimeEntry is created on break end.**
- **Original entry is resumed** (pause model).
- User does not need to manually restart after break.

Evidence:
- `backend/app/routers/work_sessions.py` (`end_break`)

### 5) Related meeting behavior (for contrast)
- Meeting start stops current entry and creates a separate meeting entry.
- Meeting end stops meeting entry and creates a new resumed work entry.
- This is stop/new-entry behavior for meetings only, not breaks.

Evidence:
- `backend/app/routers/work_sessions.py` (`start_meeting`, `end_meeting`)
- `backend/alembic/versions/018_add_meeting_time_entry_tracking.py`

---

## Part A - Frontend Behavior Findings

### Break button and API wiring
Break UI handler:
- `frontend/src/components/sessions/BreakControls.tsx`
  - `handleStartBreak` -> `sessionsApi.startBreak(...)` -> `fetchTimer(true)`
  - `handleEndBreak` -> `sessionsApi.endBreak()` -> `fetchTimer(true)`

API client endpoints:
- `frontend/src/api/client.ts`
  - `sessionsApi.startBreak` -> `POST /api/work-sessions/break/start`
  - `sessionsApi.endBreak` -> `POST /api/work-sessions/break/end`
  - `timeEntriesApi.getTimer` -> `GET /api/time/timer`

Timer display source:
- `frontend/src/components/sessions/SessionWidget.tsx`
  - Current Task timer renders `taskElapsedSeconds` from `timerStore.elapsedSeconds`.
  - Pause label uses `timerStore.isPaused`.

### Likely frontend defect causing observed ticking
In `frontend/src/stores/timerStore.ts`, function `applyServerState`:
- Computes `isPaused` from server entry (`entry.is_paused`).
- Then checks if `isSameEntry` (`current.currentEntry?.id === entry.id`).
- If same entry, it returns early after only clearing loading/error.

Effect:
- Break start keeps the same entry ID but flips `is_paused` false -> true.
- Early return skips writing updated `isPaused` to store.
- `updateElapsed()` continues incrementing because it only stops when `isPaused===true`.

This aligns with reproduction:
- Status bar can show break from session state, while task timer keeps ticking from stale timer state.

Evidence:
- `frontend/src/stores/timerStore.ts` (`applyServerState`, `updateElapsed`)
- `frontend/src/components/sessions/BreakControls.tsx` (`fetchTimer(true)` after break actions)

### Test coverage gap
Current tests include same-entry early-return behavior but do not assert pause-flag transitions on same entry ID.
- Existing test: "applyServerState clears isLoading on same-entry early return".
- Missing test: same entry with `is_paused` changed should update `isPaused` and freeze elapsed.

Evidence:
- `frontend/src/stores/timerStore.test.ts`

---

## Part B - Existing Data Audit (Read-only)

## DB access status
Configured DB URL resolves to local Postgres:
- `postgresql+asyncpg://postgres:postgres@localhost:5434/time_tracker`

Attempted read-only overlap aggregation, but connection failed:
- `ConnectionRefusedError [WinError 1225]` to `localhost:5434`
- Docker engine is also unavailable in this environment, so local DB container could not be started here.

Because of that, the required production overlap counts cannot be computed from this environment at this time.

## Query prepared for overlap quantification (run against production DB)
```sql
WITH entry_break_overlap AS (
  SELECT
    te.id AS time_entry_id,
    te.user_id,
    te.work_session_id,
    te.start_time,
    te.end_time,
    COALESCE(te.pause_seconds,0) AS pause_seconds,
    SUM(
      GREATEST(
        0,
        EXTRACT(EPOCH FROM (
          LEAST(COALESCE(te.end_time, NOW()), sb.end_time)
          - GREATEST(te.start_time, sb.start_time)
        ))
      )
    )::bigint AS break_overlap_seconds
  FROM time_entries te
  JOIN session_breaks sb
    ON sb.work_session_id = te.work_session_id
   AND sb.end_time IS NOT NULL
   AND te.start_time < sb.end_time
   AND COALESCE(te.end_time, NOW()) > sb.start_time
  GROUP BY te.id, te.user_id, te.work_session_id, te.start_time, te.end_time, te.pause_seconds
)
SELECT
  COUNT(*) FILTER (WHERE break_overlap_seconds > 0) AS overlapping_entries,
  COALESCE(SUM(break_overlap_seconds) FILTER (WHERE break_overlap_seconds > 0),0)::bigint AS total_overlap_seconds,
  COUNT(*) FILTER (WHERE break_overlap_seconds > pause_seconds) AS suspected_inflated_entries,
  COALESCE(SUM(break_overlap_seconds - pause_seconds) FILTER (WHERE break_overlap_seconds > pause_seconds),0)::bigint AS suspected_inflated_seconds
FROM entry_break_overlap;
```

## Required output fields (pending DB access)
- Affected entries with break overlap: **PENDING (DB unreachable in this environment)**
- Estimated overlap hours: **PENDING (DB unreachable in this environment)**
- Suspected inflated entries (`break_overlap_seconds > pause_seconds`): **PENDING**
- Suspected inflated hours: **PENDING**

---

## Part C - Architectural Decision

## Recommended option: **Option B (Pause/Resume)**
Reasoning:
- The backend already has a pause model (`is_paused`, `paused_at`, `pause_seconds`) and break endpoints are implemented around it.
- Existing utility logic (`compute_display_elapsed_seconds`) and active-timer cache already support pause semantics.
- Option A (stop/restart) would be a behavior regression vs current UX and require broader workflow/UI changes.
- Option C (deduct overlaps during reporting only) increases hidden complexity and risk of inconsistent math.

Conclusion:
- Keep Option B and fix synchronization bug in frontend timer state handling.

---

## Migration Plan for Historical Data Correction

Decision tree:
1. Run overlap audit query against production DB.
2. If `suspected_inflated_entries = 0`, no data migration needed.
3. If non-zero:
   - Create a one-time corrective migration script that updates only closed entries where `break_overlap_seconds > pause_seconds`.
   - Set `pause_seconds = break_overlap_seconds` (or add missing delta) for break-overlap correction.
   - Recompute `duration_seconds = max(0, end_time - start_time - pause_seconds)`.
   - Log before/after snapshots to an audit table or CSV for rollback traceability.
4. Rebuild affected aggregates/reports after correction.

Safety constraints:
- Run in transaction batches.
- Dry-run mode first (counts only).
- Restrict to date range where bug was active.
- Keep idempotent (re-runs produce zero additional changes).

---

## Implementation Checklist (for chosen option B)

1. Frontend fix in `timerStore.applyServerState`:
   - Remove or narrow same-entry early return so pause-state transitions update `isPaused`, `currentEntry`, and `elapsedSeconds`.
2. Add frontend tests:
   - same entry ID with `is_paused: false -> true` updates store and freezes elapsed.
   - same entry ID with `is_paused: true -> false` resumes elapsed.
3. Add integration test flow:
   - start timer -> start break -> wait -> confirm task elapsed unchanged -> end break -> confirm resumed.
4. Validate UI consistency:
   - Session widget and Timer widget both show paused state during break.
5. Run production overlap audit query.
6. If needed, execute data correction migration script with dry-run + audited execution.
7. Post-fix monitoring:
   - temporary metric: entries where `break_overlap_seconds > pause_seconds` per day should trend to zero.

---

## Final Assessment
- Backend break persistence logic is consistent with Option B and appears correct.
- The urgent bug is highly likely in frontend timer state reconciliation, causing the on-screen task timer to continue counting despite backend pause state.
- Historical data impact remains **unquantified in this environment** due to DB connectivity constraints; run the provided SQL against production DB to finalize migration/no-migration decision.
