# TimeTracker - QA Testing Checklist

**Generated:** December 23, 2025  
**Application:** TimeTracker  
**URL:** https://timetracker.shaemarcus.com/

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
- [ ] Navigate to `/login`
- [ ] Verify email field validation (required, valid format)
- [ ] Verify password field validation (required, min 6 characters)
- [ ] Test login with valid credentials → redirects to `/dashboard`
- [ ] Test login with invalid email → shows error
- [ ] Test login with invalid password → shows error
- [ ] Verify password visibility toggle (eye icon)
- [ ] Verify "Welcome back" success notification appears

### 1.2 Register (Public)
- [ ] Navigate to `/register`
- [ ] Verify all required fields validation
- [ ] Test successful registration
- [ ] Test duplicate email registration → shows error

### 1.3 Request Account (Public)
- [ ] Navigate to `/request-account`
- [ ] Verify form fields: Name, Email, Phone, Job Title, Department
- [ ] Submit valid request
- [ ] Verify success message: "We have received your information"
- [ ] Verify "What happens next?" info box displays correctly
- [ ] Verify auto-redirect to login after 5 seconds

### 1.4 Logout (Both Roles)
- [ ] Click logout button
- [ ] Verify session is terminated
- [ ] Verify redirect to login page
- [ ] Verify cannot access protected routes after logout

---

## 2. Dashboard

### 2.1 Personal Dashboard (Both Roles)
- [ ] Navigate to `/dashboard`
- [ ] Verify "Today" hours display
- [ ] Verify "This Week" hours display
- [ ] Verify daily breakdown chart renders
- [ ] Verify project distribution pie chart renders
- [ ] Verify Timer Widget is present and functional

### 2.2 Team Overview Panel (Admin Only)
- [ ] Verify panel visible for admin users
- [ ] Verify panel hidden for regular users
- [ ] Verify "Team Today" hours display
- [ ] Verify "Team This Week" hours display
- [ ] Verify "Active Users Today" count
- [ ] Verify "Running Timers" count
- [ ] Verify "Today's Activity by User" list

### 2.3 Admin Alerts Panel (Admin Only)
- [ ] Verify alerts panel visible for admin users
- [ ] Verify alerts panel hidden for regular users

---

## 3. Time Tracking

### 3.1 Timer Widget (Both Roles)
- [ ] Navigate to `/time`
- [ ] Start timer without project → verify it works
- [ ] Start timer with project selected
- [ ] Start timer with project and task selected
- [ ] Verify timer counts up in real-time
- [ ] Stop timer → verify time entry created
- [ ] Verify entry appears in list immediately

### 3.2 Manual Entry Creation (Both Roles)
- [ ] Click "Add Manual Entry" button
- [ ] Fill in start time, end time, description
- [ ] Select project (optional)
- [ ] Select task (optional)
- [ ] Submit → verify entry created
- [ ] Verify duration calculated correctly

### 3.3 View Time Entries (Both Roles)
- [ ] Verify entries grouped by date
- [ ] Verify each entry shows: description, project, duration, times
- [ ] Verify pagination works if many entries

### 3.4 Edit Time Entry (Both Roles)
- [ ] Click edit on an entry
- [ ] Modify description
- [ ] Modify project/task
- [ ] Save changes → verify updated
- [ ] Verify "Entry Updated" notification

### 3.5 Delete Time Entry (Both Roles)
- [ ] Click delete on an entry
- [ ] Confirm deletion
- [ ] Verify entry removed from list
- [ ] Verify "Entry Deleted" notification

### 3.6 Filter by Project (Both Roles)
- [ ] Select a project from filter dropdown
- [ ] Verify only entries for that project shown
- [ ] Select "All Projects" → verify all entries shown

---

## 4. Projects

### 4.1 View Projects (Both Roles)
- [ ] Navigate to `/projects`
- [ ] Verify project cards display with name, description, color
- [ ] Verify team assignment shown if applicable

### 4.2 Create Project (Admin Only)
- [ ] Click "New Project" button (verify visible for admin)
- [ ] Verify button hidden for regular users
- [ ] Fill in project name, description
- [ ] Select color
- [ ] Assign to team (optional)
- [ ] Submit → verify project created
- [ ] Verify success notification

### 4.3 Edit Project (Admin Only)
- [ ] Click edit on a project (admin only)
- [ ] Modify name, description, color
- [ ] Save → verify changes applied

### 4.4 Archive/Restore Project (Admin Only)
- [ ] Archive a project
- [ ] Click "Show Archived" toggle
- [ ] Verify archived project appears
- [ ] Restore the project
- [ ] Verify project back in active list

---

## 5. Tasks

### 5.1 View Tasks (Both Roles)
- [ ] Navigate to `/tasks`
- [ ] Verify tasks grouped by status columns (To Do, In Progress, Done)
- [ ] Verify task cards show title, project, assignee

### 5.2 Create Task (Both Roles)
- [ ] Click "New Task" button
- [ ] Fill in title, description
- [ ] Select project
- [ ] Set due date
- [ ] Submit → verify task created in "To Do" column

### 5.3 Edit Task (Both Roles)
- [ ] Click edit on a task
- [ ] Modify title, description
- [ ] Save → verify changes

### 5.4 Change Task Status (Both Roles)
- [ ] Change task from "To Do" to "In Progress"
- [ ] Verify task moves to correct column
- [ ] Change task to "Done"
- [ ] Verify task in Done column

### 5.5 Delete Task (Both Roles)
- [ ] Delete a task
- [ ] Confirm deletion
- [ ] Verify task removed

### 5.6 Filter Tasks (Both Roles)
- [ ] Filter by project
- [ ] Filter by status
- [ ] Clear filters → verify all tasks shown

---

## 6. Teams

### 6.1 View Teams (Both Roles)
- [ ] Navigate to `/teams`
- [ ] Verify team list with member counts
- [ ] Click on a team to view details
- [ ] Verify team members listed with roles

### 6.2 Create Team (Admin Only)
- [ ] Click "Create Team" (admin only)
- [ ] Enter team name
- [ ] Submit → verify team created

### 6.3 Edit Team (Admin Only)
- [ ] Edit team name
- [ ] Save → verify name updated

### 6.4 Delete Team (Admin Only)
- [ ] Delete a team
- [ ] Confirm deletion
- [ ] Verify team removed

### 6.5 Manage Team Members (Admin Only)
- [ ] Add a member to team
- [ ] Select user and role (member/leader)
- [ ] Verify member appears in team
- [ ] Remove a member from team
- [ ] Verify member removed

---

## 7. Reports

### 7.1 Personal Reports (Both Roles)
- [ ] Navigate to `/reports`
- [ ] Verify weekly summary displays
- [ ] Verify daily breakdown chart
- [ ] Verify project distribution pie chart

### 7.2 Date Range Selection (Both Roles)
- [ ] Select "This Week" → verify data updates
- [ ] Select "Last Week" → verify data updates
- [ ] Select "This Month" → verify data updates
- [ ] Select "Last Month" → verify data updates
- [ ] Select "Custom" → enter date range → verify data

### 7.3 Export Reports (Both Roles)
- [ ] Export to CSV → verify file downloads
- [ ] Export to Excel → verify file downloads
- [ ] Export to PDF → verify file downloads
- [ ] Verify exported data matches displayed data

---

## 8. Settings

### 8.1 Update Profile (Both Roles)
- [ ] Navigate to `/settings`
- [ ] Change name → save → verify updated
- [ ] Change email → save → verify updated
- [ ] Verify success notification

### 8.2 Change Password (Both Roles)
- [ ] Enter current password
- [ ] Enter new password
- [ ] Confirm new password
- [ ] Submit → verify success notification
- [ ] Logout and login with new password

### 8.3 Preferences (Both Roles)
- [ ] Verify Dark Mode toggle present
- [ ] Verify Email Notifications toggle present

---

## 9. Staff Management (Admin Only)

### 9.1 View Staff List
- [ ] Navigate to `/staff`
- [ ] Verify staff list displays
- [ ] Verify search by name works
- [ ] Verify search by email works
- [ ] Verify search by job title works
- [ ] Verify search by department works
- [ ] Verify pagination works

### 9.2 Create Staff Member
- [ ] Click "Add Staff" button
- [ ] **Step 1 - Basic Info:** Fill name, email, password, role
- [ ] **Step 2 - Contact:** Fill phone, address, emergency contact
- [ ] **Step 3 - Employment:** Fill job title, department, employment type, start date
- [ ] **Step 4 - Payroll:** Fill pay rate, rate type, overtime multiplier, currency
- [ ] **Step 5 - Teams:** Assign to teams
- [ ] Submit → verify staff created

### 9.3 Credentials Summary Modal
- [ ] After creating staff, verify modal appears
- [ ] Verify all credentials displayed (name, email, phone, password, job title, department)
- [ ] Click "Copy to Clipboard"
- [ ] Verify "Copied!" feedback
- [ ] Paste clipboard → verify formatted message with login URL
- [ ] Close modal

### 9.4 Edit Staff Profile
- [ ] Select a staff member
- [ ] Click edit
- [ ] Modify details
- [ ] Save → verify changes applied

### 9.5 Activate/Deactivate Staff
- [ ] Deactivate a staff member
- [ ] Verify status shows "Inactive"
- [ ] Verify correct notification message
- [ ] Activate the staff member
- [ ] Verify status shows "Active"

### 9.6 Permanently Delete Staff
- [ ] Click permanent delete on a user
- [ ] Verify first confirmation dialog
- [ ] Verify second confirmation (type to confirm)
- [ ] Confirm → verify user deleted
- [ ] Verify cannot delete yourself
- [ ] Verify cannot delete super_admin

### 9.7 Manage Staff Teams
- [ ] Open teams modal for a staff member
- [ ] Add to a team
- [ ] Remove from a team
- [ ] Verify changes reflected

### 9.8 View Staff Time Entries
- [ ] Open time modal for a staff member
- [ ] Verify their time entries displayed

### 9.9 View Staff Analytics
- [ ] Open analytics modal for a staff member
- [ ] Verify performance metrics displayed

---

## 10. Account Requests Management (Admin Only)

### 10.1 View Requests
- [ ] Navigate to `/account-requests`
- [ ] Verify "Pending" tab shows pending requests
- [ ] Verify "Approved" tab shows approved requests
- [ ] Verify "Rejected" tab shows rejected requests
- [ ] Verify "All" tab shows all requests
- [ ] Verify pending count badge

### 10.2 Search Requests
- [ ] Search by name
- [ ] Search by email
- [ ] Clear search → verify all shown

### 10.3 Approve Request
- [ ] Select a pending request
- [ ] Click "Approve"
- [ ] Add optional admin notes
- [ ] Confirm → verify redirects to Staff creation
- [ ] Verify form pre-filled with request data
- [ ] Verify suggested password auto-generated
- [ ] Complete staff creation
- [ ] Verify credentials summary modal appears

### 10.4 Reject Request
- [ ] Select a pending request
- [ ] Click "Reject"
- [ ] Add optional rejection notes
- [ ] Confirm → verify request status changed

### 10.5 Delete Request
- [ ] Delete a request
- [ ] Confirm → verify removed

---

## 11. User Management / Admin Page (Admin Only)

### 11.1 View Users
- [ ] Navigate to `/admin`
- [ ] Verify user list displays
- [ ] Verify search functionality

### 11.2 Create User (Quick)
- [ ] Click "Add User"
- [ ] Fill email, password, name
- [ ] Select role
- [ ] Submit → verify user created

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
