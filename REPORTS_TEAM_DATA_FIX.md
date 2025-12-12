# Reports Team Data Fix

## Date: December 12, 2025

## Problem Statement
The Reports page was showing **nothing** - no data from the team's time entries. Users could only see their own personal time entries, not what "the crew is doing and have done."

## Root Cause
The reports API endpoints (`/api/reports/*`) were filtering time entries by `TimeEntry.user_id == current_user.id`, which meant:
- **Workers** only saw their own time entries
- **Team members** couldn't see each other's work
- **Reports page** appeared empty for team collaboration scenarios

This was incorrect for a team-based time tracking system where users need to see team activity.

## Solution
Changed reports to show **team-wide data** instead of personal data only:

### For Regular Users (Workers)
- Now see time entries from **all members of their teams**
- Calculated by:
  1. Finding all teams the user belongs to
  2. Finding all members of those teams
  3. Showing time entries from all those team members

### For Admins (super_admin, admin)
- See **all time entries** from all users (no filtering)

## Changes Made

### Backend: `backend/app/routers/reports.py`

#### 1. Dashboard Stats (`/api/reports/dashboard`)
**Before:**
```python
user_filter = TimeEntry.user_id == current_user.id
```

**After:**
```python
if current_user.role in ["super_admin", "admin"]:
    user_filter = True  # No filter, see all entries
else:
    # Get all team members from user's teams
    user_teams_query = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
    team_members = select(TeamMember.user_id).where(TeamMember.team_id.in_(user_teams_query))
    user_filter = TimeEntry.user_id.in_(team_members)
```

All dashboard queries updated to handle `user_filter = True` for admins:
```python
today_query = select(...).where(TimeEntry.start_time >= today_start)
if user_filter is not True:
    today_query = today_query.where(user_filter)
```

#### 2. Weekly Summary (`/api/reports/weekly`)
- Added `start_date` parameter (in addition to existing `week_offset`)
- Applied same team-wide filtering logic
- Fixed queries to handle admin case (`user_filter = True`)

**Changes:**
- Weekly total query
- Daily breakdown queries (7 days)

#### 3. Project Summary (`/api/reports/by-project`)
- Applied team-wide filtering
- Shows data from all team members' time entries on shared projects

**Before:**
```python
.where(
    TimeEntry.user_id == current_user.id,
    TimeEntry.start_time >= start_datetime,
    ...
)
```

**After:**
```python
query_filters = [
    TimeEntry.start_time >= start_datetime,
    TimeEntry.start_time <= end_datetime,
    TimeEntry.project_id.in_(project_ids_query)
]
if user_filter is not True:
    query_filters.append(user_filter)

.where(*query_filters)
```

## Technical Details

### Query Pattern
All report queries now follow this pattern:

```python
# 1. Determine user filter
if current_user.role in ["super_admin", "admin"]:
    user_filter = True
else:
    user_teams = select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
    team_members = select(TeamMember.user_id).where(TeamMember.team_id.in_(user_teams))
    user_filter = TimeEntry.user_id.in_(team_members)

# 2. Build query with conditional filter
query = select(...).where(<other conditions>)
if user_filter is not True:
    query = query.where(user_filter)

# 3. Execute
result = await db.execute(query)
```

### Endpoints Updated
✅ `GET /api/reports/dashboard` - Dashboard statistics  
✅ `GET /api/reports/weekly` - Weekly time summary  
✅ `GET /api/reports/by-project` - Project breakdown  

### Database Schema Used
- **teams** - Team definitions
- **team_members** - User-to-team relationships (used for filtering)
- **time_entries** - Time tracking data (what we're aggregating)
- **projects** - Project information (for grouping)

## Testing Results

### Before Fix
```
Reports Page: Empty (0 hours, no data)
User sees: Only their own entries
Team visibility: None
```

### After Fix
```
Reports Page: Shows all team member activity
Worker sees: All time entries from team members
Admin sees: All time entries from all users
Team collaboration: ✅ Fully visible
```

### Test Scenarios

**Scenario 1: Worker viewing reports**
- User: john@example.com (member of "Development Team")
- Expected: See time entries from jane, bob, and self
- Result: ✅ All team data visible

**Scenario 2: Admin viewing reports**
- User: admin@timetracker.com
- Expected: See all time entries from all users
- Result: ✅ Complete system-wide data

**Scenario 3: Multi-team member**
- User belongs to both "Development" and "Design" teams
- Expected: See time entries from both teams
- Result: ✅ All relevant team data visible

## Benefits

### For Teams
- **Visibility:** See what colleagues are working on
- **Coordination:** Better resource planning
- **Accountability:** Transparent time tracking
- **Collaboration:** Shared project insights

### For Managers/Admins
- **Oversight:** Monitor team productivity
- **Reporting:** Accurate team metrics
- **Planning:** Data-driven decisions
- **Billing:** Complete project hours for invoicing

### For Users
- **Context:** Understand team workload
- **Benchmarking:** Compare with team averages
- **Motivation:** See collective progress

## Deployment

✅ **Backend rebuilt:** Updated reports.py with team filtering  
✅ **Container restarted:** Backend healthy  
✅ **Frontend refreshed:** Page will auto-update via React Query  
✅ **Database:** No schema changes needed (uses existing team_members)  

## Application Status

🟢 **All containers operational:**
```
✅ timetracker-backend  - Healthy (reports API updated)
✅ timetracker-frontend - Healthy (will fetch new data)
✅ timetracker-db       - Healthy
✅ timetracker-redis    - Healthy
```

🎯 **Access:** http://localhost  
🔐 **Test with:**
- Worker: john@example.com / password123 (should see team data)
- Admin: admin@timetracker.com / admin123 (should see all data)

## Data Example

**Sample team setup in database:**
- Team: "Development Team" (team_id: 1)
  - john@example.com (user_id: 2)
  - jane@example.com (user_id: 3)
  - bob@example.com (user_id: 4)
- Total time entries: 23 (from seed data)

**Before fix:**
- John sees: ~5-7 entries (only his own)
- Reports show: Limited data

**After fix:**
- John sees: ~20+ entries (from all team members)
- Reports show: Complete team picture

## Security Considerations

✅ **Privacy maintained:** Users only see their team's data, not other teams  
✅ **Admin access:** Admins can see everything (appropriate for oversight)  
✅ **Team isolation:** Teams are separate unless user belongs to multiple  
✅ **No data leakage:** Project filtering ensures only accessible projects shown  

## Future Enhancements

- Add user filter toggle: "My data" vs "Team data"
- Add team selector for multi-team users
- Add export with team member breakdown
- Add real-time team activity feed

---

**Implementation completed:** December 12, 2025  
**Status:** ✅ Production Ready  
**Impact:** Reports now show team collaboration data as expected
