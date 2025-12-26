# TimeTracker - QA Testing Checklist

**Generated:** December 23, 2025  
**Last Updated:** December 24, 2025  
**Application:** TimeTracker  
**URL:** https://timetracker.shaemarcus.com/

---

## Pre-Testing Code Fixes Status

| Issue | Status | Notes |
|-------|--------|-------|
| Password validation - RegisterPage | ✅ Fixed | Now shows 12+ char requirement |
| Password validation - SettingsPage | ✅ Fixed | Now shows 12+ char requirement |
| Password validation - LoginPage | ✅ Fixed | Removed misleading 6-char validation |
| Password validation - StaffPage | ✅ Fixed | Now shows 12+ char requirement |
| Invalid Date in Admin | ✅ Fixed | Added created_at to UserResponse |
| Permanent Delete 500 Error | ✅ Fixed | Removed TimeModification reference |
| Unified Staff Creation | ✅ Fixed | AdminPage now uses 4-step wizard |

---

## User Roles

| Role | Description |
|------|-------------|
| **super_admin** | Full system access, can manage all users including other admins |
| **admin** | Full access to admin features, cannot modify super_admins |
| **regular_user/worker** | Standard access to time tracking, projects, tasks, teams, personal reports |

---

## 1. Authentication & Onboarding

### 1.1 Login (Public)
- [x] Navigate to `/login` ✅
- [x] Verify email field validation (required, valid format) ✅
- [x] Verify password field validation (required only - no minLength) ✅
- [x] Test login with valid credentials → redirects to `/dashboard` ✅
- [x] Test login with invalid email → shows error ✅
- [x] Test login with invalid password → shows error ✅
- [x] Verify password visibility toggle (eye icon) ✅
- [x] Verify "Welcome back" success notification appears ✅

### 1.2 Register (Public)
- [x] Navigate to `/register` ✅
- [x] Verify all required fields validation ✅
- [x] Verify password requires 12+ chars with complexity hint ✅
- [x] Test successful registration ✅
- [x] Test duplicate email registration → shows error ✅

### 1.3 Request Account (Public)
- [x] Navigate to `/request-account` ✅
- [x] Verify form fields: Name, Email, Phone, Job Title, Department ✅
- [x] Submit valid request ✅
- [x] Verify success message: "We have received your information" ✅
- [x] Verify "What happens next?" info box displays correctly ✅
- [x] Verify auto-redirect to login after 5 seconds ✅

### 1.4 Logout (Both Roles)
- [x] Click logout button ✅
- [x] Verify session is terminated ✅
- [x] Verify redirect to login page ✅
- [x] Verify cannot access protected routes after logout ✅

---

## 2. Dashboard

### 2.1 Personal Dashboard (Both Roles)
- [x] Navigate to `/dashboard` ✅
- [x] Verify "Today" hours display ✅
- [x] Verify "This Week" hours display ✅
- [x] Verify daily breakdown chart renders ✅
- [x] Verify project distribution pie chart renders ✅
- [x] Verify Timer Widget is present and functional ✅

### 2.2 Team Overview Panel (Admin Only)
- [x] Verify panel visible for admin users ✅
- [ ] Verify panel hidden for regular users
- [x] Verify "Team Today" hours display ✅
- [x] Verify "Team This Week" hours display ✅
- [x] Verify "Active Users Today" count ✅
- [x] Verify "Running Timers" count ✅
- [x] Verify "Today's Activity by User" list ✅

### 2.3 Admin Alerts Panel (Admin Only)
- [x] Verify alerts panel visible for admin users ✅
- [ ] Verify alerts panel hidden for regular users

---

## 3. Time Tracking

### 3.1 Timer Widget (Both Roles)
- [x] Navigate to `/time` ✅
- [x] Start timer without project → ⚠️ **Requires project** (shows "Please select a project before starting the timer")
- [x] Start timer with project selected ✅
- [x] Start timer with project and task selected ✅
- [x] Verify timer counts up in real-time ✅
- [x] Stop timer → verify time entry created ✅
- [x] Verify entry appears in list immediately ✅

### 3.2 Manual Entry Creation (Both Roles)
- [x] Click "Add Manual Entry" button ✅
- [x] Fill in start time, end time, description ✅
- [x] Select project (optional) ✅
- [x] Select task (optional) ✅
- [x] Submit → verify entry created ✅
- [x] Verify duration calculated correctly ✅

### 3.3 View Time Entries (Both Roles)
- [x] Verify entries grouped by date ✅
- [x] Verify each entry shows: description, project, duration, times ✅
- [x] Verify pagination works if many entries ✅

### 3.4 Edit Time Entry (Both Roles)
- [x] Click edit on an entry ✅
- [x] Modify description ✅
- [x] Modify project/task ✅
- [x] Save changes → verify updated ✅
- [x] Verify "Entry Updated" notification ✅

### 3.5 Delete Time Entry (Both Roles)
- [x] Click delete on an entry ✅
- [x] Confirm deletion ✅
- [x] Verify entry removed from list ✅
- [x] Verify "Entry Deleted" notification ✅

### 3.6 Filter by Project (Both Roles)
- [x] Select a project from filter dropdown ✅
- [x] Verify only entries for that project shown ✅
- [x] Select "All Projects" → verify all entries shown ✅

---

## 4. Projects

### 4.1 View Projects (Both Roles)
- [x] Navigate to `/projects` ✅
- [x] Verify project cards display with name, description, color ✅
- [x] Verify team assignment shown if applicable ✅

### 4.2 Create Project (Admin Only)
- [x] Click "New Project" button (verify visible for admin) ✅
- [ ] Verify button hidden for regular users
- [x] Fill in project name, description ✅
- [x] Select color ✅
- [x] Assign to team (optional) ✅
- [x] Submit → verify project created ✅
- [x] Verify success notification ✅

### 4.3 Edit Project (Admin Only)
- [x] Click edit on a project (admin only) ✅
- [x] Modify name, description, color ✅
- [x] Save → verify changes applied ✅

### 4.4 Archive/Restore Project (Admin Only)
- [x] Archive a project ✅
- [x] Verify confirmation dialog appears ✅
- [x] Click "Show Archived" toggle ✅
- [x] Verify archived project appears (only archived shown) ✅
- [x] Restore the project ✅
- [x] Verify confirmation dialog appears ✅
- [x] Verify project back in active list ✅

### 4.5 Delete Project (Admin Only)
- [x] Click delete on a project ✅
- [x] Verify confirmation dialog appears ✅
- [x] Confirm → verify project deleted ✅

---

## 5. Tasks

### 5.1 View Tasks (Both Roles)
- [x] Navigate to `/tasks` ✅
- [x] Verify tasks grouped by status columns (To Do, In Progress, Done) ✅
- [x] Verify task cards show title, project, assignee ✅

### 5.2 Create Task (Both Roles)
- [x] Click "New Task" button ✅
- [x] Fill in title, description ✅
- [x] Select project ✅
- [x] Set due date ✅
- [x] Submit → verify task created in "To Do" column ✅

### 5.3 Edit Task (Both Roles)
- [x] Click edit on a task ✅
- [x] Modify title, description ✅
- [x] Save → verify changes ✅

### 5.4 Change Task Status (Both Roles)
- [x] Change task from "To Do" to "In Progress" ✅
- [x] Verify task moves to correct column ✅
- [x] Change task to "Done" ✅
- [x] Verify task in Done column ✅

### 5.5 Delete Task (Both Roles)
- [x] Delete a task ✅
- [x] Confirm deletion ✅
- [x] Verify task removed ✅

### 5.6 Filter Tasks (Both Roles)
- [x] Filter by project ✅
- [x] Filter by status ✅
- [x] Clear filters → verify all tasks shown ✅

---

## 6. Teams

### 6.1 View Teams (Both Roles)
- [x] Navigate to `/teams` ✅
- [x] Verify team list with member counts ✅
- [x] Click on a team to view details ✅
- [x] Verify team members listed with roles ✅

### 6.2 Create Team (Admin Only)
- [x] Click "Create Team" (admin only) ✅
- [x] Enter team name ✅
- [x] Submit → verify team created ✅

### 6.3 Edit Team (Admin Only)
- [x] Edit team name ✅
- [x] Save → verify name updated ✅

### 6.4 Delete Team (Admin Only)
- [x] Delete a team ✅
- [x] Confirm deletion ✅
- [x] Verify team removed ✅

### 6.5 Manage Team Members (Admin Only)
- [x] Add a member to team ✅
- [x] Select user and role (member/leader) ✅
- [x] Verify member appears in team ✅
- [x] Remove a member from team ✅
- [x] Verify member removed ✅

---

## 7. Reports

### 7.1 Personal Reports (Both Roles)
- [x] Navigate to `/reports` ✅
- [x] Verify weekly summary displays ✅
- [x] Verify daily breakdown chart ✅
- [x] Verify project distribution pie chart ✅

### 7.2 Date Range Selection (Both Roles)
- [x] Select "This Week" → verify data updates ✅
- [x] Select "Last Week" → verify data updates ✅
- [x] Select "This Month" → verify data updates ✅
- [x] Select "Last Month" → verify data updates ✅
- [x] Select "Custom" → enter date range → verify data ✅

### 7.3 Export Reports (Both Roles)
- [x] Export to CSV → verify file downloads ✅
- [x] Export to Excel → verify file downloads ✅
- [x] Export to PDF → verify file downloads ✅
- [x] Verify exported data matches displayed data ✅

---

## 8. Settings

### 8.1 Update Profile (Both Roles)
- [x] Navigate to `/settings` ✅
- [x] Change name → save → verify updated ✅
- [x] Change email → save → verify updated ✅
- [x] Verify success notification ✅

### 8.2 Change Password (Both Roles)
- [x] Enter current password ✅
- [x] Enter new password ✅
- [x] Confirm new password ✅
- [x] Submit → verify success notification ✅
- [x] Logout and login with new password ✅

### 8.3 Preferences (Both Roles)
- [x] Verify Dark Mode toggle present ✅
- [x] Verify Email Notifications toggle present ✅

---

## 9. Staff Management (Admin Only)

### 9.1 View Staff List
- [x] Navigate to `/staff` ✅
- [x] Verify staff list displays ✅
- [x] Verify search by name works ✅
- [x] Verify search by email works ✅
- [x] Verify search by job title works ✅
- [x] Verify search by department works ✅
- [x] Verify pagination works ✅

### 9.2 Create Staff Member
- [x] Click "Add Staff" button ✅
- [x] **Step 1 - Basic Info:** Fill name, email, password, role ✅
- [x] **Step 2 - Contact:** Fill phone, address, emergency contact ✅
- [x] **Step 3 - Employment:** Fill job title, department, employment type, start date ✅
- [x] **Step 4 - Payroll:** Fill pay rate, rate type, overtime multiplier, currency ✅
- [x] **Step 5 - Teams:** Assign to teams ✅
- [x] Submit → verify staff created ✅

### 9.3 Credentials Summary Modal
- [x] After creating staff, verify modal appears ✅
- [x] Verify all credentials displayed (name, email, phone, password, job title, department) ✅
- [x] Click "Copy to Clipboard" ✅
- [x] Verify "Copied!" feedback ✅
- [x] Paste clipboard → verify formatted message with login URL ✅
- [x] Close modal ✅

### 9.4 Edit Staff Profile
- [x] Select a staff member ✅
- [x] Click edit ✅
- [x] Modify details ✅
- [x] Save → verify changes applied ✅

### 9.5 Activate/Deactivate Staff
- [x] Deactivate a staff member ✅
- [x] Verify status shows "Inactive" ✅
- [x] Verify correct notification message ✅
- [x] Activate the staff member ✅
- [x] Verify status shows "Active" ✅

### 9.6 Permanently Delete Staff
- [x] Click permanent delete on a user ✅
- [x] Verify first confirmation dialog ✅
- [x] Verify second confirmation (type to confirm) ✅
- [x] Confirm → verify user deleted ✅
- [x] Verify cannot delete yourself ✅
- [x] Verify cannot delete super_admin ✅

### 9.7 Manage Staff Teams
- [x] Open teams modal for a staff member ✅
- [x] Add to a team ✅
- [x] Remove from a team ✅
- [x] Verify changes reflected ✅

### 9.8 View Staff Time Entries
- [x] Open time modal for a staff member ✅
- [x] Verify their time entries displayed ✅

### 9.9 View Staff Analytics
- [x] Open analytics modal for a staff member ✅
- [x] Verify performance metrics displayed ✅

---

## 10. Account Requests Management (Admin Only)

### 10.1 View Requests
- [x] Navigate to `/account-requests` ✅
- [x] Verify "Pending" tab shows pending requests ✅
- [x] Verify "Approved" tab shows approved requests ✅
- [x] Verify "Rejected" tab shows rejected requests ✅
- [x] Verify "All" tab shows all requests ✅
- [x] Verify pending count badge ✅

### 10.2 Search Requests
- [x] Search by name ✅
- [x] Search by email ✅
- [x] Clear search → verify all shown ✅

### 10.3 Approve Request
- [x] Select a pending request ✅
- [x] Click "Approve" ✅
- [x] Add optional admin notes ✅
- [x] Confirm → verify redirects to Staff creation ✅
- [x] Verify form pre-filled with request data ✅
- [x] Verify suggested password auto-generated ✅
- [x] Complete staff creation ✅
- [x] Verify credentials summary modal appears ✅

### 10.4 Reject Request
- [x] Select a pending request ✅
- [x] Click "Reject" ✅
- [x] Add optional rejection notes ✅
- [x] Confirm → verify request status changed ✅

### 10.5 Delete Request
- [x] Delete a request ✅
- [x] Confirm → verify removed ✅

---

## 11. User Management / Admin Page (Admin Only)

### 11.1 View Users
- [ ] Navigate to `/admin`
- [ ] Verify user list displays
- [ ] Verify search functionality

### 11.2 Create User (Now redirects to Staff Page)
- [ ] Click "Add Staff Member" button
- [ ] Verify redirects to `/staff` page
- [ ] Verify 4-step creation wizard opens automatically
- [ ] Complete creation using full wizard (see section 9.2)

### 11.3 Change User Role
- [ ] Select a user
- [ ] Change role dropdown
- [ ] Verify role updated
- [ ] Verify cannot change own role

### 11.4 Toggle User Status
- [ ] Deactivate a user
- [ ] Activate a user
- [ ] Verify cannot deactivate yourself

---

## 12. Payroll - Pay Rates (Admin Only)

### 12.1 View Pay Rates
- [ ] Navigate to `/payroll/rates`
- [ ] Verify pay rates list displays

### 12.2 Create Pay Rate
- [ ] Click "Add Pay Rate"
- [ ] Select user
- [ ] Select rate type (hourly/daily/monthly/project)
- [ ] Enter base rate
- [ ] Select currency
- [ ] Set overtime multiplier
- [ ] Set effective dates
- [ ] Submit → verify created

### 12.3 Edit Pay Rate
- [ ] Edit an existing rate
- [ ] Modify values
- [ ] Add change reason
- [ ] Save → verify updated

### 12.4 View Rate History
- [ ] Click history on a pay rate
- [ ] Verify historical changes displayed

### 12.5 Delete Pay Rate
- [ ] Delete a pay rate
- [ ] Confirm → verify removed

---

## 13. Payroll - Periods (Admin Only)

### 13.1 View Periods
- [ ] Navigate to `/payroll/periods`
- [ ] Verify periods list with statuses

### 13.2 Create Period
- [ ] Click "Add Period"
- [ ] Enter name
- [ ] Select period type
- [ ] Set start/end dates
- [ ] Submit → verify created in Draft status

### 13.3 Period Workflow
- [ ] Process a draft period → verify status changes to Processing
- [ ] Approve period → verify status changes to Approved
- [ ] Mark as Paid → verify status changes to Paid

### 13.4 View Period Details
- [ ] Click on a period
- [ ] Verify payroll entries displayed for each user

### 13.5 Filter by Status
- [ ] Filter by Draft
- [ ] Filter by Processing
- [ ] Filter by Approved
- [ ] Filter by Paid

---

## 14. Payroll - Reports (Admin Only)

### 14.1 View Payables Report
- [ ] Navigate to `/payroll/reports`
- [ ] Verify summary metrics display
- [ ] Verify detailed breakdown table

### 14.2 Filter Report
- [ ] Filter by period
- [ ] Filter by date range
- [ ] Clear filters

### 14.3 Export Payroll Report
- [ ] Export to CSV → verify download
- [ ] Export to Excel → verify download

---

## 15. Admin Analytics / Reports (Admin Only)

### 15.1 Overview Tab
- [ ] Navigate to `/admin/reports`
- [ ] Verify Today/Week/Month metrics
- [ ] Verify active users count
- [ ] Verify running timers count
- [ ] Verify charts render

### 15.2 Teams Tab
- [ ] Click "Teams" tab
- [ ] Verify team-by-team breakdown
- [ ] Verify member counts
- [ ] Verify top performers list

### 15.3 Individuals Tab
- [ ] Click "Individuals" tab
- [ ] Verify user list with hours
- [ ] Toggle period (today/week/month)
- [ ] Click on a user → verify navigates to detail page

---

## 16. Real-Time Features

### 16.1 WebSocket Connection
- [ ] Open browser console
- [ ] Verify WebSocket connection established
- [ ] Verify no connection errors

### 16.2 Live Updates
- [ ] Start a timer in one tab
- [ ] Open dashboard in another tab
- [ ] Stop timer → verify dashboard updates without refresh
- [ ] Create time entry → verify reports update

---

## 17. Access Control Testing

### 17.1 Admin Routes Protection
- [ ] As regular user, navigate to `/admin` → verify redirect to dashboard
- [ ] As regular user, navigate to `/staff` → verify redirect
- [ ] As regular user, navigate to `/account-requests` → verify redirect
- [ ] As regular user, navigate to `/payroll/rates` → verify redirect
- [ ] As regular user, navigate to `/payroll/periods` → verify redirect
- [ ] As regular user, navigate to `/payroll/reports` → verify redirect
- [ ] As regular user, navigate to `/admin/reports` → verify redirect

### 17.2 Admin UI Elements Hidden
- [ ] As regular user, verify "New Project" button hidden
- [ ] As regular user, verify project edit/archive hidden
- [ ] As regular user, verify team create/edit/delete hidden
- [ ] As regular user, verify Payroll menu hidden in sidebar
- [ ] As regular user, verify Admin Reports hidden in sidebar
- [ ] As regular user, verify Staff menu hidden
- [ ] As regular user, verify Account Requests hidden

---

## 18. Error Handling

### 18.1 Network Errors
- [ ] Disable network → perform action → verify error message
- [ ] Re-enable network → retry → verify recovery

### 18.2 Validation Errors
- [ ] Submit empty required fields → verify validation messages
- [ ] Submit invalid email format → verify error
- [ ] Submit mismatched passwords → verify error

### 18.3 API Errors
- [ ] Test duplicate email creation → verify error message
- [ ] Test unauthorized access → verify error handling

---

## 19. Responsive Design

### 19.1 Mobile View (< 768px)
- [ ] Verify sidebar collapses to hamburger menu
- [ ] Verify forms are usable on mobile
- [ ] Verify tables scroll horizontally
- [ ] Verify modals are full-width on mobile

### 19.2 Tablet View (768px - 1024px)
- [ ] Verify layout adapts appropriately
- [ ] Verify all features accessible

### 19.3 Desktop View (> 1024px)
- [ ] Verify full layout displays
- [ ] Verify sidebar always visible

---

## Test Execution Log

| Date | Tester | Section Tested | Issues Found | Status |
|------|--------|----------------|--------------|--------|
| | | | | |
| | | | | |
| | | | | |

---

## Notes

- Total Features: 78
- Total Test Cases: 150+
- Estimated Testing Time: 4-6 hours (full pass)

---

*Last Updated: December 23, 2025*
