# TimeTracker Manual Testing Checklist

> **Date:** January 8, 2026  
> **Tester:** _______________  
> **Environment:** ☐ Local ☐ Staging ☐ Production  
> **Build Version:** _______________

---

## 📋 How to Use This Checklist

1. Mark each item as you test: ✅ Pass | ❌ Fail | ⏭️ Skip
2. Add notes for any failures or issues
3. Test in order - some features depend on others
4. Save this file with your test date for records

---

## 🔐 1. Authentication & Authorization

### 1.1 Login Flow
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 1.1.1 | Navigate to `/login` - page loads correctly | ☐ | |
| 1.1.2 | Login with valid email/password | ☐ | |
| 1.1.3 | Login with invalid email - shows error | ☐ | |
| 1.1.4 | Login with wrong password - shows error | ☐ | |
| 1.1.5 | Login with empty fields - shows validation | ☐ | |
| 1.1.6 | "Remember me" checkbox works | ☐ | |
| 1.1.7 | Redirects to dashboard after login | ☐ | |

### 1.2 Logout Flow
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 1.2.1 | Logout button visible in header/menu | ☐ | |
| 1.2.2 | Click logout - redirects to login | ☐ | |
| 1.2.3 | After logout, protected pages redirect to login | ☐ | |
| 1.2.4 | Session cleared (check localStorage) | ☐ | |

### 1.3 Password Reset
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 1.3.1 | "Forgot password" link on login page | ☐ | |
| 1.3.2 | Enter email - success message shown | ☐ | |
| 1.3.3 | Reset email received (check inbox/spam) | ☐ | |
| 1.3.4 | Reset link works - password form loads | ☐ | |
| 1.3.5 | New password can be set | ☐ | |
| 1.3.6 | Can login with new password | ☐ | |
| 1.3.7 | Old password no longer works | ☐ | |

### 1.4 Registration (if not white-labeled)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 1.4.1 | Register link visible on login page | ☐ | |
| 1.4.2 | Registration form loads | ☐ | |
| 1.4.3 | Can create new account | ☐ | |
| 1.4.4 | Duplicate email prevented | ☐ | |
| 1.4.5 | Password validation enforced | ☐ | |

### 1.5 Account Request (white-label mode)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 1.5.1 | "Request Account" link visible | ☐ | |
| 1.5.2 | Account request form loads | ☐ | |
| 1.5.3 | Submit request - success message | ☐ | |
| 1.5.4 | Admin sees request in admin panel | ☐ | |

---

## ⏱️ 2. Timer & Time Tracking

### 2.1 Timer Widget
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 2.1.1 | Timer widget visible on dashboard | ☐ | |
| 2.1.2 | Timer shows 00:00:00 initially | ☐ | |
| 2.1.3 | Click Start - timer begins counting | ☐ | |
| 2.1.4 | Timer display updates every second | ☐ | |
| 2.1.5 | Click Stop - timer stops | ☐ | |
| 2.1.6 | Time entry created after stop | ☐ | |
| 2.1.7 | Can select project before starting | ☐ | |
| 2.1.8 | Can add description before/during | ☐ | |
| 2.1.9 | Timer persists after page refresh | ☐ | |
| 2.1.10 | Timer persists across browser tabs | ☐ | |

### 2.2 Time Entries Page
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 2.2.1 | Navigate to `/time` - page loads | ☐ | |
| 2.2.2 | Today's entries displayed | ☐ | |
| 2.2.3 | Can filter by date range | ☐ | |
| 2.2.4 | Can filter by project | ☐ | |
| 2.2.5 | Total hours calculated correctly | ☐ | |

### 2.3 Manual Time Entry
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 2.3.1 | "Add Entry" button visible | ☐ | |
| 2.3.2 | Manual entry form opens | ☐ | |
| 2.3.3 | Can set start/end time | ☐ | |
| 2.3.4 | Can select project | ☐ | |
| 2.3.5 | Can add description | ☐ | |
| 2.3.6 | Entry saved successfully | ☐ | |
| 2.3.7 | Duration calculated correctly | ☐ | |

### 2.4 Edit/Delete Time Entry
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 2.4.1 | Can click to edit entry | ☐ | |
| 2.4.2 | Edit form pre-filled with data | ☐ | |
| 2.4.3 | Changes save correctly | ☐ | |
| 2.4.4 | Can delete entry | ☐ | |
| 2.4.5 | Confirmation shown before delete | ☐ | |
| 2.4.6 | Entry removed after delete | ☐ | |

---

## 📁 3. Projects Management

### 3.1 Project List
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 3.1.1 | Navigate to `/projects` - page loads | ☐ | |
| 3.1.2 | Projects list displayed | ☐ | |
| 3.1.3 | Project cards show name, client, status | ☐ | |
| 3.1.4 | Can search/filter projects | ☐ | |
| 3.1.5 | Pagination works (if many projects) | ☐ | |

### 3.2 Create Project
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 3.2.1 | "New Project" button visible | ☐ | |
| 3.2.2 | Create form opens | ☐ | |
| 3.2.3 | Can enter project name | ☐ | |
| 3.2.4 | Can select client | ☐ | |
| 3.2.5 | Can set billable rate | ☐ | |
| 3.2.6 | Can set project color | ☐ | |
| 3.2.7 | Project created successfully | ☐ | |
| 3.2.8 | New project appears in list | ☐ | |

### 3.3 Edit/Archive Project
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 3.3.1 | Can click to edit project | ☐ | |
| 3.3.2 | Edit form pre-filled | ☐ | |
| 3.3.3 | Changes save correctly | ☐ | |
| 3.3.4 | Can archive project | ☐ | |
| 3.3.5 | Archived projects hidden by default | ☐ | |
| 3.3.6 | Can view archived projects | ☐ | |
| 3.3.7 | Can restore archived project | ☐ | |

---

## 👥 4. Teams Management

### 4.1 Team List
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 4.1.1 | Navigate to `/teams` - page loads | ☐ | |
| 4.1.2 | Teams list displayed | ☐ | |
| 4.1.3 | Team member count shown | ☐ | |

### 4.2 Create/Edit Team
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 4.2.1 | Can create new team | ☐ | |
| 4.2.2 | Can add members to team | ☐ | |
| 4.2.3 | Can remove members from team | ☐ | |
| 4.2.4 | Can edit team name | ☐ | |
| 4.2.5 | Can delete team | ☐ | |

---

## 📊 5. Reports

### 5.1 Basic Reports
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 5.1.1 | Navigate to `/reports` - page loads | ☐ | |
| 5.1.2 | Date range picker works | ☐ | |
| 5.1.3 | Filter by project works | ☐ | |
| 5.1.4 | Filter by user works | ☐ | |
| 5.1.5 | Report data displays correctly | ☐ | |
| 5.1.6 | Total hours calculated | ☐ | |

### 5.2 Export Reports
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 5.2.1 | Export to CSV works | ☐ | |
| 5.2.2 | Export to PDF works | ☐ | |
| 5.2.3 | Export to Excel works | ☐ | |
| 5.2.4 | Exported data matches display | ☐ | |

### 5.3 Charts/Visualizations
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 5.3.1 | Charts render correctly | ☐ | |
| 5.3.2 | Chart updates with filters | ☐ | |
| 5.3.3 | Chart legend works | ☐ | |
| 5.3.4 | Hover/tooltip shows data | ☐ | |

---

## 💰 6. Payroll System

### 6.1 Pay Rates
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 6.1.1 | Navigate to `/pay-rates` - page loads | ☐ | |
| 6.1.2 | User pay rates displayed | ☐ | |
| 6.1.3 | Can set hourly rate | ☐ | |
| 6.1.4 | Can set overtime rate | ☐ | |
| 6.1.5 | Rate changes saved | ☐ | |

### 6.2 Payroll Periods
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 6.2.1 | Navigate to `/payroll-periods` - loads | ☐ | |
| 6.2.2 | Current period shown | ☐ | |
| 6.2.3 | Can create new period | ☐ | |
| 6.2.4 | Can close period | ☐ | |
| 6.2.5 | Period totals calculated | ☐ | |

### 6.3 Payroll Reports
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 6.3.1 | Navigate to `/payroll-reports` - loads | ☐ | |
| 6.3.2 | Select employee - data loads | ☐ | |
| 6.3.3 | Hours breakdown correct | ☐ | |
| 6.3.4 | Earnings calculated correctly | ☐ | |
| 6.3.5 | Can export payroll report | ☐ | |

---

## 🤖 7. AI Features

### 7.1 AI Settings
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.1.1 | AI preferences in settings | ☐ | |
| 7.1.2 | Can enable/disable AI features | ☐ | |
| 7.1.3 | Settings persist after save | ☐ | |

### 7.2 Smart Descriptions (Phase 1.1)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.2.1 | "AI Suggest" button visible | ☐ | |
| 7.2.2 | Click generates description | ☐ | |
| 7.2.3 | Description relevant to project | ☐ | |
| 7.2.4 | Can accept/edit suggestion | ☐ | |

### 7.3 Task Categorization (Phase 1.2)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.3.1 | "Auto-categorize" button visible | ☐ | |
| 7.3.2 | Click suggests category | ☐ | |
| 7.3.3 | Tag suggestions provided | ☐ | |
| 7.3.4 | Can accept suggestions | ☐ | |

### 7.4 Time Entry Validation (Phase 2.1)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.4.1 | Enter 16+ hour entry | ☐ | |
| 7.4.2 | Warning message appears | ☐ | |
| 7.4.3 | Suggestion for correction | ☐ | |

### 7.5 Break Reminders (Phase 2.2)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.5.1 | Work 2+ hours without break | ☐ | |
| 7.5.2 | Break reminder appears | ☐ | |
| 7.5.3 | Can dismiss reminder | ☐ | |

### 7.6 Daily Summary (Phase 3.1)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.6.1 | Navigate to AI Reports | ☐ | |
| 7.6.2 | Generate daily summary | ☐ | |
| 7.6.3 | Summary shows time breakdown | ☐ | |
| 7.6.4 | Productivity insights shown | ☐ | |

### 7.7 Weekly Analysis (Phase 3.2)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.7.1 | Generate weekly report | ☐ | |
| 7.7.2 | Work patterns visualized | ☐ | |
| 7.7.3 | Peak productivity times shown | ☐ | |

### 7.8 Productivity Alerts (Phase 4.1)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.8.1 | Alerts panel visible | ☐ | |
| 7.8.2 | Alerts generated for anomalies | ☐ | |
| 7.8.3 | Can dismiss alerts | ☐ | |

### 7.9 AI Reports (Phase 4.2)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.9.1 | AI report generation available | ☐ | |
| 7.9.2 | Report includes narrative | ☐ | |
| 7.9.3 | Recommendations provided | ☐ | |

### 7.10 Semantic Search (Phase 5.1)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.10.1 | AI search box visible | ☐ | |
| 7.10.2 | Natural language query works | ☐ | |
| 7.10.3 | Relevant results returned | ☐ | |

### 7.11 Team Analytics (Phase 5.2) - Admin Only
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 7.11.1 | Team analytics accessible | ☐ | |
| 7.11.2 | Team productivity metrics shown | ☐ | |
| 7.11.3 | Individual comparisons available | ☐ | |

---

## 🏢 8. Multi-Tenancy

### 8.1 Data Isolation
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 8.1.1 | Login as Company A user | ☐ | |
| 8.1.2 | Only Company A data visible | ☐ | |
| 8.1.3 | Cannot access Company B URLs | ☐ | |
| 8.1.4 | API returns only company data | ☐ | |

### 8.2 Company Switching (Admin)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 8.2.1 | Platform admin sees all companies | ☐ | |
| 8.2.2 | Can switch company context | ☐ | |
| 8.2.3 | Data changes per company | ☐ | |

---

## 🎨 9. White-Label Branding

### 9.1 Logo & App Name
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 9.1.1 | Custom app name in header | ☐ | |
| 9.1.2 | Custom logo displays | ☐ | |
| 9.1.3 | Custom favicon shows | ☐ | |

### 9.2 Colors & Theme
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 9.2.1 | Primary color on buttons | ☐ | |
| 9.2.2 | Secondary color on accents | ☐ | |
| 9.2.3 | Colors consistent across pages | ☐ | |

### 9.3 White-Label Mode
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 9.3.1 | Registration hidden (if enabled) | ☐ | |
| 9.3.2 | "Powered by" hidden (if enabled) | ☐ | |
| 9.3.3 | Support email customized | ☐ | |
| 9.3.4 | Support URL customized | ☐ | |

---

## ⚙️ 10. Admin Panel

### 10.1 User Management
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 10.1.1 | Navigate to Admin > Users | ☐ | |
| 10.1.2 | User list displays | ☐ | |
| 10.1.3 | Can create new user | ☐ | |
| 10.1.4 | Can edit user | ☐ | |
| 10.1.5 | Can deactivate user | ☐ | |
| 10.1.6 | Can assign roles | ☐ | |
| 10.1.7 | Can reset user password | ☐ | |

### 10.2 Company Settings
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 10.2.1 | Navigate to Admin > Settings | ☐ | |
| 10.2.2 | Company name editable | ☐ | |
| 10.2.3 | Timezone settings work | ☐ | |
| 10.2.4 | Settings persist after save | ☐ | |

### 10.3 Account Requests
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 10.3.1 | Navigate to Admin > Account Requests | ☐ | |
| 10.3.2 | Pending requests displayed | ☐ | |
| 10.3.3 | Can approve request | ☐ | |
| 10.3.4 | Can reject request | ☐ | |
| 10.3.5 | User created after approval | ☐ | |

### 10.4 Admin Reports
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 10.4.1 | Navigate to Admin > Reports | ☐ | |
| 10.4.2 | Company-wide reports available | ☐ | |
| 10.4.3 | Can filter by date range | ☐ | |
| 10.4.4 | Can export admin reports | ☐ | |

---

## 🔄 11. Real-Time Features

### 11.1 WebSocket Connection
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 11.1.1 | WebSocket connects on login | ☐ | |
| 11.1.2 | Connection indicator visible | ☐ | |
| 11.1.3 | Reconnects after disconnect | ☐ | |

### 11.2 Live Updates
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 11.2.1 | Open 2 browser tabs | ☐ | |
| 11.2.2 | Start timer in Tab 1 | ☐ | |
| 11.2.3 | Timer shows in Tab 2 | ☐ | |
| 11.2.4 | Time entry syncs across tabs | ☐ | |

---

## 📱 12. Responsive Design

### 12.1 Mobile View (< 768px)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 12.1.1 | Login page renders correctly | ☐ | |
| 12.1.2 | Dashboard usable | ☐ | |
| 12.1.3 | Navigation menu works | ☐ | |
| 12.1.4 | Timer widget usable | ☐ | |
| 12.1.5 | Forms are scrollable | ☐ | |

### 12.2 Tablet View (768px - 1024px)
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 12.2.1 | Layout adjusts properly | ☐ | |
| 12.2.2 | Tables readable | ☐ | |
| 12.2.3 | Charts render correctly | ☐ | |

---

## 🔒 13. Security

### 13.1 Session Security
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 13.1.1 | Session expires after timeout | ☐ | |
| 13.1.2 | Token refresh works | ☐ | |
| 13.1.3 | Invalid token redirects to login | ☐ | |

### 13.2 Input Validation
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 13.2.1 | XSS attempt blocked | ☐ | |
| 13.2.2 | SQL injection attempt blocked | ☐ | |
| 13.2.3 | Invalid data rejected | ☐ | |

### 13.3 Authorization
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 13.3.1 | Regular user can't access admin | ☐ | |
| 13.3.2 | User can only see own data | ☐ | |
| 13.3.3 | API returns 403 for unauthorized | ☐ | |

---

## 📧 14. Email System

### 14.1 Email Delivery
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 14.1.1 | Welcome email on registration | ☐ | |
| 14.1.2 | Password reset email | ☐ | |
| 14.1.3 | Invitation email | ☐ | |
| 14.1.4 | Email branding correct | ☐ | |

---

## 🐛 15. Error Handling

### 15.1 Error Messages
| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 15.1.1 | Network error shows message | ☐ | |
| 15.1.2 | Validation errors clear | ☐ | |
| 15.1.3 | 404 page renders | ☐ | |
| 15.1.4 | Server error handled gracefully | ☐ | |

---

## ✅ Test Summary

| Category | Total Tests | Passed | Failed | Skipped |
|----------|-------------|--------|--------|---------|
| 1. Authentication | 23 | | | |
| 2. Timer & Time | 20 | | | |
| 3. Projects | 15 | | | |
| 4. Teams | 5 | | | |
| 5. Reports | 12 | | | |
| 6. Payroll | 13 | | | |
| 7. AI Features | 28 | | | |
| 8. Multi-Tenancy | 6 | | | |
| 9. White-Label | 10 | | | |
| 10. Admin Panel | 15 | | | |
| 11. Real-Time | 5 | | | |
| 12. Responsive | 8 | | | |
| 13. Security | 9 | | | |
| 14. Email | 4 | | | |
| 15. Error Handling | 4 | | | |
| **TOTAL** | **177** | | | |

---

## 📝 Test Notes & Issues Found

### Critical Issues
| Issue | Location | Description | Priority |
|-------|----------|-------------|----------|
| | | | |

### Minor Issues
| Issue | Location | Description | Priority |
|-------|----------|-------------|----------|
| | | | |

### Suggestions
| Suggestion | Location | Description |
|------------|----------|-------------|
| | | |

---

## 🏁 Sign-Off

**Testing Completed:** ☐ Yes ☐ Partial ☐ No

**Tester Signature:** _______________

**Date:** _______________

**Overall Result:** ☐ Pass ☐ Pass with Issues ☐ Fail

---

*Template Version: 1.0*  
*Created: January 8, 2026*
