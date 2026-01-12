# Multi-Tenancy Security Audit Report

**Date:** January 12, 2026  
**Auditor:** GitHub Copilot  
**Scope:** Backend routers for cross-company data leak vulnerabilities

---

## 🔴 CRITICAL VULNERABILITIES (Data Leak Risk)

### 1. **admin.py - `/admin/time-entries` endpoint (Lines 76-145)**
**Risk Level:** 🔴 CRITICAL  
**Function:** `get_admin_time_entries()`

**Issue:** No company_id filtering applied to the query. An admin from XYZ Corp can see ALL time entries from all companies including the main platform.

```python
# Line 91-109: Query has NO company filter
query = (
    select(TimeEntry, User.name.label("user_name"), ...)
    .join(User, TimeEntry.user_id == User.id)
    .join(Project, TimeEntry.project_id == Project.id)
    .where(
        TimeEntry.start_time >= start_datetime,
        TimeEntry.start_time <= end_datetime
    )
)
# MISSING: apply_company_filter(query, User.company_id, company_id)
```

---

### 2. **admin.py - `/admin/workers-report` endpoint (Lines 172-237)**
**Risk Level:** 🔴 CRITICAL  
**Function:** `get_workers_report()`

**Issue:** Lists ALL active users from the entire database without company filtering.

```python
# Line 191-195: NO company filter on user query
user_query = select(User).where(User.is_active == True)

if team_id:
    team_users = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
    user_query = user_query.where(User.id.in_(team_users))
# MISSING: apply_company_filter(user_query, User.company_id, company_id)
```

---

### 3. **approvals.py - ALL endpoints (Lines 1-255)**
**Risk Level:** 🔴 CRITICAL  
**Functions:** `get_pending_approvals()`, `approve_time_entry()`, `reject_time_entry()`, `bulk_approval()`, `get_approval_stats()`, `reset_approval_status()`

**Issue:** The ENTIRE approvals router has ZERO company filtering. Any manager can approve/reject time entries from any company.

```python
# Line 59: No company filter
query = select(TimeEntry).where(TimeEntry.approval_status == "pending")

# Line 94: No company filter  
result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))

# Line 127: No company filter
result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))

# Line 165: No company filter
select(TimeEntry).where(TimeEntry.id.in_(request.entry_ids))
```

---

### 4. **time_entries.py - GET `/{entry_id}` endpoint (Lines 586-615)**
**Risk Level:** 🔴 CRITICAL  
**Function:** `get_time_entry()`

**Issue:** No company validation. Any user can view any time entry by ID if they know the ID.

```python
# Line 590: Direct select without company filter
result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))
entry = result.scalar_one_or_none()

# Line 597-598: Role check doesn't verify company
if current_user.role not in ["super_admin", "admin", "company_admin"] and entry.user_id != current_user.id:
    raise HTTPException(...)  # Admin from other company can still access!
```

---

### 5. **time_entries.py - PUT `/{entry_id}` endpoint (Lines 617-680)**
**Risk Level:** 🔴 CRITICAL  
**Function:** `update_time_entry()`

**Issue:** No company validation. A super_admin from another company can modify entries.

```python
# Line 623: No company filter
result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))

# Line 630-631: Only checks user ownership OR super_admin - no company check
if entry.user_id != current_user.id and current_user.role != "super_admin":
    raise HTTPException(...)
```

---

### 6. **time_entries.py - DELETE `/{entry_id}` endpoint (Lines 682-716)**
**Risk Level:** 🔴 CRITICAL  
**Function:** `delete_time_entry()`

**Issue:** Same as above - no company validation for deletion.

```python
# Line 687: No company filter
result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))
```

---

### 7. **users.py - PUT `/{user_id}/role` endpoint (Lines 477-510)**
**Risk Level:** 🔴 CRITICAL  
**Function:** `change_user_role()`

**Issue:** No company filtering. An admin from XYZ Corp could change roles of main platform users.

```python
# Line 484: No company filter
result = await db.execute(select(User).where(User.id == user_id))
```

---

### 8. **users.py - Team Assignment during user creation (Lines 227-238)**
**Risk Level:** 🔴 HIGH  
**Function:** `create_user()`

**Issue:** No validation that the team_ids belong to the admin's company. An admin could assign a new user to teams from other companies.

```python
# Line 229-235: Only checks if team exists, not company
for team_id in user_data.team_ids:
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if not team:
        raise HTTPException(...)
    # MISSING: Verify team.company_id == current_user.company_id
```

---

## 🟠 HIGH RISK - WebSocket Broadcasting Issues

### 9. **time_entries.py - `broadcast_to_all()` calls (Lines 279, 343, 358, 437, 660, 709)**
**Risk Level:** 🟠 HIGH  

**Issue:** Multiple WebSocket broadcasts send data to ALL connected users without company filtering. When a user starts/stops/updates/deletes a timer, ALL users from ALL companies receive the notification.

**Affected broadcasts:**
- Line 279: `timer_started` - Leaks user names, project names across companies
- Line 343: `timer_stopped` - Leaks user activity across companies  
- Line 358: `time_entry_completed` - Leaks work details across companies
- Line 437: `time_entry_created` - Leaks manual entries across companies
- Line 660: `time_entry_updated` - Leaks updates across companies
- Line 709: `time_entry_deleted` - Leaks deletions across companies

```python
# Example from Line 279 - broadcasts to ALL users:
await ws_manager.broadcast_to_all({
    "type": "timer_started",
    "data": {
        "user_id": current_user.id,
        "user_name": current_user.name,  # LEAKED TO ALL COMPANIES!
        "project_name": project.name,    # LEAKED TO ALL COMPANIES!
        ...
    }
})
```

---

### 10. **websocket.py - `broadcast_to_all()` function (Lines 82-86)**
**Risk Level:** 🟠 HIGH  
**Function:** `ConnectionManager.broadcast_to_all()`

**Issue:** The broadcast function has no company filtering capability. It sends to ALL connected users regardless of company.

```python
# Line 82-86: No company parameter or filtering
async def broadcast_to_all(self, message: dict, exclude_user: int = None):
    """Broadcast a message to all connected users"""
    for user_id in list(self.active_connections.keys()):
        if user_id != exclude_user:
            await self.send_personal_message(message, user_id)
```

**Recommended Fix:** Add a `broadcast_to_company()` method.

---

### 11. **websocket.py - `broadcast_to_team()` (Line 77-80)**
**Risk Level:** 🟡 MEDIUM  
**Function:** `ConnectionManager.broadcast_to_team()`

**Issue:** While team broadcasting is more scoped, there's no verification that the sender belongs to the same company as the team.

---

## 🟡 MEDIUM RISK - Partial or Missing Filters

### 12. **reports.py - `/by-project` endpoint (Lines 327-395)**
**Risk Level:** 🟡 MEDIUM  
**Function:** `get_time_by_project()`

**Issue:** For admin/super_admin, no company filtering is applied. Admins can see projects from other companies.

```python
# Lines 347-349: No company filter for admins
if current_user.role in ["super_admin", "admin"]:
    project_ids_query = select(Project.id)
    user_filter = True  # No filter, see all users
```

---

### 13. **ai_features.py - Admin endpoints (Lines 293-350)**
**Risk Level:** 🟡 MEDIUM  
**Functions:** `get_user_preferences_admin()`, `set_user_override()`

**Issue:** Company check exists but only for `company_admin` role. A platform `admin` could view/modify AI settings of any company's users.

```python
# Lines 305-308: Only company_admin is restricted
if current_user.role == "company_admin" and user.company_id != current_user.company_id:
    raise HTTPException(...)
# Regular "admin" role is NOT restricted!
```

---

### 14. **payroll.py - Payroll services (entire file)**
**Risk Level:** 🟡 MEDIUM  

**Issue:** The payroll router passes `company_id` in `list_payroll_periods()` but other endpoints don't consistently filter. The services need auditing.

```python
# Line 76-78: Filter only applied for non-super_admin
company_id = None if current_user.role == 'super_admin' else current_user.company_id
```

But individual payroll entries, adjustments, and period processing don't consistently apply company filters.

---

## 🟢 PROPERLY IMPLEMENTED (Good Examples)

These endpoints correctly implement multi-tenancy:

1. **teams.py** - `list_teams()`, `get_team()`, `create_team()`, `update_team()` - Uses `apply_company_filter()` correctly
2. **projects.py** - `list_projects()`, `get_project()` - Joins with Team and applies company filter
3. **users.py** - `list_users()`, `get_user()` - Uses `apply_company_filter()`
4. **reports.py** - `get_dashboard_stats()`, `get_weekly_summary()`, `get_team_report()`, `get_admin_dashboard()` - Properly filtered
5. **admin.py** - `get_activity_alerts()` - Correctly uses `apply_company_filter()`
6. **time_entries.py** - `list_time_entries()`, `get_active_timers()` - Properly filtered

---

## 📋 REMEDIATION CHECKLIST

### Immediate Actions Required:

| File | Function | Line | Fix Required |
|------|----------|------|--------------|
| admin.py | `get_admin_time_entries` | 91-109 | Add company filter via User join |
| admin.py | `get_workers_report` | 191 | Add `apply_company_filter()` to user query |
| approvals.py | ALL functions | All | Add company filtering to all queries |
| time_entries.py | `get_time_entry` | 590 | Join with User and filter by company |
| time_entries.py | `update_time_entry` | 623 | Add company validation |
| time_entries.py | `delete_time_entry` | 687 | Add company validation |
| users.py | `change_user_role` | 484 | Add company filter |
| users.py | `create_user` (teams) | 229 | Validate team belongs to company |
| time_entries.py | All broadcasts | Multiple | Use company-scoped broadcasting |
| websocket.py | `broadcast_to_all` | 82 | Add `broadcast_to_company()` method |

### Recommended Code Pattern:

```python
# For all admin endpoints accessing user data:
company_id = get_company_filter(current_user)
query = select(Model).join(User, Model.user_id == User.id)
query = apply_company_filter(query, User.company_id, company_id)

# For WebSocket broadcasting:
async def broadcast_to_company(self, message: dict, company_id: int, exclude_user: int = None):
    """Broadcast only to users in the same company"""
    for user_id, user_data in self.active_connections.items():
        if user_id != exclude_user:
            # Check company_id from cached user data
            if user_data.get("company_id") == company_id or company_id is None:
                await self.send_personal_message(message, user_id)
```

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| 🔴 CRITICAL | 8 | Direct data leak vulnerabilities |
| 🟠 HIGH | 3 | WebSocket cross-company broadcasting |
| 🟡 MEDIUM | 3 | Partial or inconsistent filtering |

**Total Issues Found: 14**

---

*This audit focuses on backend API security. Frontend validation alone is NOT sufficient protection.*
