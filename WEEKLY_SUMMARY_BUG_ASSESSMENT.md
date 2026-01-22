# Weekly Summary Bug Assessment

## Issue Description
The Weekly Summary panel shows **0.0h Total Hours** for the admin user even though they have logged time entries this week. The displayed date range also appears incorrect (18/1/2026 - 24/1/2026 suggests Saturday-Saturday instead of Monday-Sunday).

## Root Cause Analysis

### Primary Bug: Timezone Mismatch in Date Comparison

**Location:** `backend/app/ai/services/reporting_service.py` - `_gather_weekly_metrics()` method (lines 450-520)

**The Problem:**
```python
# Line 213-215 - Week calculation uses naive local time
today = date.today()  # ❌ Server's LOCAL date, timezone-unaware
week_start = today - timedelta(days=today.weekday())
week_end = week_start + timedelta(days=6)

# Line 493-497 - Query compares UTC timestamps with local dates
entries_result = await self.db.execute(
    select(TimeEntry)
    .where(
        and_(
            TimeEntry.user_id.in_(user_ids),
            func.date(TimeEntry.start_time) >= week_start,  # ❌ Comparing UTC to local date
            func.date(TimeEntry.start_time) <= week_end,
            TimeEntry.is_running == False
        )
    )
)
```

### Why This Causes 0 Hours

1. **Time entries are stored in UTC** (with timezone info):
   - `start_time=datetime.now(timezone.utc)` in `time_entries.py` line 270
   - Model uses `DateTime(timezone=True)` - stores UTC timestamps

2. **Week boundaries calculated in server local time**:
   - `date.today()` returns the server's local date
   - If server is in UTC and user creates entry at 5 PM on Jan 20 (UTC), that's stored as `2026-01-20 17:00:00+00`
   
3. **Database comparison issue**:
   - `func.date(TimeEntry.start_time)` extracts date from UTC timestamp
   - Depending on PostgreSQL settings, this could extract the UTC date
   - But `week_start` is a Python `date` object from local time
   - **Result:** Entries may fall outside the calculated week boundaries

### Example Scenario

Let's say today is **January 22, 2026 (Wednesday)** and server is in **UTC-5** timezone:

- Server local time: Jan 22, 10:00 AM local
- Server `date.today()` = Jan 22
- `week_start` = Jan 20 (Monday)
- `week_end` = Jan 26 (Sunday)

But time entries created at, say, 8 AM local on Jan 21:
- Stored as: `2026-01-21 13:00:00+00` (UTC)
- `func.date()` in PostgreSQL extracts: Jan 21 (from UTC)
- This SHOULD match, but...

**The more likely scenario:**

If the server runs in **UTC** (common for cloud deployments):
- `date.today()` = UTC date
- But if user's browser sends local times that get converted incorrectly, or...
- If there's any offset in the PostgreSQL `func.date()` extraction...

### Secondary Bug: Display Date Format

**Location:** `frontend/src/components/ai/WeeklySummaryPanel.tsx`

The UI shows "18/1/2026 - 24/1/2026" which is **Saturday Jan 18 to Saturday Jan 24**, but:
- Monday Jan 20 through Sunday Jan 26 would be the correct week for Jan 22
- This suggests the backend is returning wrong dates, or there's an off-by-one error

## Affected Files

1. **Backend:**
   - `backend/app/ai/services/reporting_service.py` - Main bug location
   - Lines 213-215: Week boundary calculation
   - Lines 493-500: SQL query with date comparison
   - Lines 521-530: Last week comparison (same bug)

2. **Frontend:**
   - `frontend/src/components/ai/WeeklySummaryPanel.tsx` - Date display
   
## Fix Strategy

### Option 1: Use UTC Consistently (Recommended)

```python
from datetime import datetime, date, timedelta, timezone

# Calculate week boundaries in UTC
now_utc = datetime.now(timezone.utc)
today_utc = now_utc.date()
week_start = today_utc - timedelta(days=today_utc.weekday())
week_end = week_start + timedelta(days=6)

# Convert to datetime with timezone for proper comparison
week_start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
week_end_dt = datetime.combine(week_end, datetime.max.time()).replace(tzinfo=timezone.utc)

# Use timezone-aware datetime comparison instead of func.date()
entries_result = await self.db.execute(
    select(TimeEntry)
    .where(
        and_(
            TimeEntry.user_id.in_(user_ids),
            TimeEntry.start_time >= week_start_dt,  # ✅ Proper timezone comparison
            TimeEntry.start_time <= week_end_dt,
            TimeEntry.is_running == False
        )
    )
)
```

### Option 2: Extract Dates in Database with AT TIME ZONE

```python
from sqlalchemy import text

# Force PostgreSQL to interpret timestamps in UTC when extracting date
entries_result = await self.db.execute(
    select(TimeEntry)
    .where(
        and_(
            TimeEntry.user_id.in_(user_ids),
            func.date(func.timezone('UTC', TimeEntry.start_time)) >= week_start,
            func.date(func.timezone('UTC', TimeEntry.start_time)) <= week_end,
            TimeEntry.is_running == False
        )
    )
)
```

## Recommended Fix (Option 1 - Full Implementation)

The fix should:
1. Use `datetime.now(timezone.utc).date()` for week boundary calculation
2. Convert week boundaries to full UTC datetimes for proper comparison
3. Use direct datetime comparison instead of `func.date()` extraction
4. Apply same fix to all related queries (last week comparison, daily breakdown, etc.)

## Testing Steps

1. Create a time entry with a known timestamp (e.g., `2026-01-22 10:00:00 UTC`)
2. Call `/api/ai/reports/weekly-summary` endpoint
3. Verify the returned `total_hours` includes the entry
4. Verify `period_start` and `period_end` show correct Monday-Sunday range

## Files to Modify

1. `backend/app/ai/services/reporting_service.py`:
   - `generate_weekly_summary()` - week calculation
   - `_gather_weekly_metrics()` - all date queries
   - `_get_daily_breakdown()` - daily aggregation queries

## Priority: HIGH

This bug completely breaks the Weekly Summary feature for all users, showing 0 hours regardless of actual work logged.
