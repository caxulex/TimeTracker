# Long-Timer Email Audit

Date: 2026-06-19
Branch: audit/long-timer-email
Scope: findings only, no application code changes

## 1. Trigger path, cadence, and scan scope

The long-timer email is triggered by the standalone backend script `backend/scripts/send_long_timer_warnings.py`, which is run by the production `scheduler-hourly` container in `docker-compose.prod.yml`.

Scheduler wiring:

```yaml
# docker-compose.prod.yml
scheduler-hourly:
  command:
    - |
      echo "Hourly scheduler started. Will run long-timer warning job every hour."
      while true; do
        echo "[Scheduler-Hourly] Running long-timer warning job..."
        python scripts/send_long_timer_warnings.py || echo "[Scheduler-Hourly] job exited non-zero (continuing)"
        sleep 3600
      done
```

Script entry point:

```python
async def main() -> None:
    ...
    async with Session() as db:
        try:
            summary = await send_long_timer_warnings(db, email_service)
            print(f"[long-timer-warnings] {summary}")
```

Candidate scan in the script:

```python
result = await db.execute(
    select(TimeEntry)
    .where(
        TimeEntry.end_time.is_(None),
        TimeEntry.long_timer_email_sent_at.is_(None),
        TimeEntry.start_time < cutoff,
    )
    .options(...)
)
```

Findings:

- It runs every hour.
- In the current workspace code, it does not scan all entries.
- It scans entries with `end_time IS NULL`, `long_timer_email_sent_at IS NULL`, and `start_time < now - 9h`.
- It does not filter on `is_running == True`.
- I found no second code path in this workspace that writes `long_timer_email_sent_at`; the only assignment is in `backend/scripts/send_long_timer_warnings.py`.

Important discrepancy with the production examples:

- The current workspace code does have an `end_time IS NULL` gate.
- That gate does not fully match the reported production example where an already-ended task still received a warning.
- If the production facts are correct, one of these must also be true:
  - production was on an older/different revision when the email fired, or
  - the row was in an inconsistent state when scanned, or
  - the stored notion of “ended” did not correspond to `end_time` being populated at send time.
- What is clear from the current code is that there is no `is_running` gate, so an inconsistent row with `end_time = NULL` can still qualify.

## 2. Exact elapsed expression used by the email trigger

The script uses gross elapsed wall-clock time from `start_time` to `now`, with no subtraction of `pause_seconds`.

Threshold cutoff:

```python
LONG_TIMER_THRESHOLD_HOURS = 9
...
cutoff = now - timedelta(hours=LONG_TIMER_THRESHOLD_HOURS)
...
TimeEntry.start_time < cutoff
```

Email subject/body duration calculation:

```python
duration_hours = (now - entry.start_time).total_seconds() / 3600.0
```

What it does not do:

- It does not subtract `pause_seconds`.
- It does not look at `is_paused` / `paused_at`.
- It does not use `duration_seconds`.
- It does not use `COALESCE(end_time, now())` in the elapsed arithmetic.
- It does not use `is_running` as a gate.

Current-code conclusion:

- Yes, the trigger is effectively `now - start_time` for its elapsed logic.
- No, it is not pause-aware.
- It partially respects completion only through `end_time IS NULL` in the candidate query.
- It does not explicitly respect `is_running`.

## 3. Shared helper and blast radius

### 3.1 Shared helper that already exists

There is already a shared backend helper in `backend/app/utils/timer_elapsed.py`:

```python
def compute_display_elapsed_seconds(entry: Any, now: datetime | None = None) -> int:
    ...
    if is_paused and paused_at is not None:
        end_ref = paused_at
    else:
        end_ref = now

    pause_seconds = int(getattr(entry, "pause_seconds", 0) or 0)
    elapsed = int((end_ref - start).total_seconds()) - pause_seconds
    return max(elapsed, 0)
```

This helper is pause-aware for active timers and freezes elapsed time while currently paused.

### 3.2 Current consumers of `compute_display_elapsed_seconds`

Direct backend consumers found in this workspace:

- `backend/app/routers/time_entries.py`
- `backend/app/routers/websocket.py`
- `backend/app/routers/work_sessions.py`
- `backend/app/routers/reports.py`
- `backend/app/services/duration_service.py`

Indirect consumer chain:

- `backend/app/ai/services/reporting_service.py`
  - delegates to `app.services.duration_service.calculate_entry_duration_for_period(...)`
  - that helper uses `compute_display_elapsed_seconds(...)` for running entries

This means the shared pause-aware current-task logic already affects:

- active timer API payloads
- websocket active timer updates
- “Who’s working now” / work-session live timer displays
- reports that include running entries
- AI reporting weekly metrics via `reporting_service`

### 3.3 Frontend long-timer banner

The frontend long-timer banner is already built on pause-aware running elapsed, not gross elapsed.

Banner gate:

```tsx
const level = useMemo(() => {
  if (!isRunning || !currentEntry) return null;
  return getCurrentBannerLevel(elapsedSeconds, lastDismissedLevel);
}, [isRunning, currentEntry, elapsedSeconds, lastDismissedLevel]);
```

Threshold logic:

```ts
// First banner fires at 6h, then again at every 2h step (8h, 10h, ...).
export function getCurrentBannerLevel(elapsedSeconds: number, lastDismissedLevel: number | null)
```

The store computes `elapsedSeconds` with pause handling:

```ts
const computeElapsed = (startTime, paused, pausedAtIso, accumulatedPauseSeconds) => {
  let elapsed = calculateElapsed(startTime);
  elapsed -= accumulatedPauseSeconds;
  if (paused && pausedAtIso) {
    elapsed -= calculateElapsed(pausedAtIso);
  }
  return Math.max(0, elapsed);
};
```

Conclusion for the frontend banner:

- Its 6h/8h/10h thresholds are based on pause-aware live elapsed.
- It already requires `isRunning` and `currentEntry`.
- It is not using the buggy gross `now - start_time` email logic.

### 3.4 Overtime / burnout / anomaly / payroll blast radius

This is mixed, not a single shared path.

Payroll:

- `backend/app/services/payroll_service.py` uses completed entries only:
  - `TimeEntry.is_running == False`
  - sums stored `duration_seconds`
- Weekly overtime grouping uses `duration_seconds`, not live gross elapsed.
- Payroll is not using the long-timer email logic.

Classical anomaly detection:

- `backend/app/ai/services/anomaly_service.py` builds daily hours from completed entries only.
- It uses raw `(entry.end_time - entry.start_time).total_seconds() / 3600`, not `duration_seconds` and not the shared pause-aware helper.
- That is a separate pause-awareness issue for anomaly metrics, but not a consumer of the long-timer email path.

ML burnout risk:

- `backend/app/ai/services/ml_anomaly_service.py` filters `TimeEntry.is_running == False`.
- Daily hours are computed from `e.duration_seconds`.
- Burnout overtime frequency is based on stored completed-entry totals, not the live email logic.

Forecasting overtime risk:

- `backend/app/ai/services/forecasting_service.py` is the main related blast-radius item.
- `_get_user_hours(...)` explicitly includes running timers and computes them as raw `now - entry.start_time`:

```python
for entry in running_entries:
    if entry.start_time:
        ...
        running_seconds += (now - entry_start).total_seconds()
```

- That means projected overtime risk currently shares the same gross-elapsed flaw for running timers:
  - no `pause_seconds` subtraction
  - no `is_paused` / `paused_at` freeze
  - no `end_time` check on the running-hours calculation path beyond `is_running == True`

Bottom line on blast radius:

- Confirmed directly affected by the same gross-live-elapsed pattern:
  - `backend/scripts/send_long_timer_warnings.py`
  - `backend/app/ai/services/forecasting_service.py::_get_user_hours`
- Already using the shared pause-aware helper and therefore not part of this bug shape:
  - timer API / websocket / work-session live displays
  - frontend long-timer banner thresholds
  - reporting duration helpers
- Using separate completed-entry math, not this live helper:
  - payroll
  - ML burnout risk
- Using separate raw end-minus-start math on completed entries:
  - classical anomaly detection

## 4. Corrected definition and best fix point

Requested target definition from the brief:

```text
on_task_seconds = (COALESCE(end_time, now()) - start_time) - pause_seconds
alert only for still-running entries
```

Assessment:

- This is directionally correct for completed entries and running entries that are not currently paused.
- In this codebase, it is not quite sufficient for a currently paused running entry, because the active pause interval is tracked by `is_paused` + `paused_at` and is only folded into `pause_seconds` on resume.
- If you use `COALESCE(end_time, now()) - start_time - pause_seconds` while the timer is actively paused, you still overcount the in-progress pause.

The existing shared helper already encodes the missing paused-state behavior:

```python
if is_paused and paused_at is not None:
    end_ref = paused_at
else:
    end_ref = now
elapsed = (end_ref - start_time) - pause_seconds
```

Best single fix point:

- Add or extend a shared helper in `backend/app/utils/timer_elapsed.py` for canonical on-task elapsed.
- That helper should accept `start_time`, `end_time`, `is_paused`, `paused_at`, and `pause_seconds`.
- It should return pause-aware on-task seconds for both closed and running entries.

Recommended shape:

```text
if end_time is not null:
  end_ref = end_time
elif is_paused and paused_at is not null:
  end_ref = paused_at
else:
  end_ref = now

on_task_seconds = max(0, end_ref - start_time - pause_seconds)
```

Affected callers to update first:

1. `backend/scripts/send_long_timer_warnings.py`
   - candidate evaluation
   - email subject/body `duration_hours`
2. `backend/app/ai/services/forecasting_service.py::_get_user_hours`
   - running timer contribution to projected overtime

Optional follow-up review target:

- `backend/app/ai/services/anomaly_service.py` uses raw `end_time - start_time` on completed entries, so it is not the same live bug, but it is worth separately checking for pause correctness.

## 5. Backlog #17 / `test_long_timer_email`

Current state in this workspace:

- I ran the focused test file `backend/tests/test_long_timer_email.py`.
- Result: `9 passed`.
- So the “pre-existing failing test” is not currently failing here.

What the test file does cover:

- sends for timers older than 9 hours
- does not send under 9 hours
- does not send for completed timers
- does not duplicate sends
- stamps `long_timer_email_sent_at`
- does not stamp on email failure

What it encodes:

- It encodes the current intended gate that completed timers should be ignored.
- It does not encode pause-aware elapsed.
- It does not create a running entry with non-zero `pause_seconds`.
- It does not test an actively paused timer.
- It does not assert `is_running` vs `end_time` consistency.

Implication:

- The test is related to this feature, but it does not currently protect against the gross-vs-net elapsed bug reported from production.
- It also does not explain the production example of an email sent after a timer had ended, because the current test suite asserts the opposite behavior for rows with `end_time` populated.

Recommended test additions when implementation starts:

1. running timer older than 9h gross but under 9h net because of `pause_seconds` should not email
2. actively paused timer should freeze at `paused_at` and should not accrue additional email elapsed
3. inconsistent row with `end_time IS NULL` and `is_running = False` should be explicitly rejected if the fix chooses `is_running` as part of the running gate
4. forecasting `_get_user_hours(...)` should subtract pause time from running entries

## Final summary

Confirmed in the current workspace:

- The email job is `backend/scripts/send_long_timer_warnings.py`, run hourly by `scheduler-hourly`.
- Its trigger is gross elapsed wall-clock from `start_time` to `now`.
- It ignores `pause_seconds`.
- It does not use `is_running`.
- It only gates on `end_time IS NULL` and `long_timer_email_sent_at IS NULL`.
- The frontend long-timer banner is already pause-aware and running-only.
- The main same-pattern blast radius outside email is forecasting overtime risk, which also uses raw `now - start_time` for running entries.
- The current `test_long_timer_email` file is green and does not cover the reported pause bug.