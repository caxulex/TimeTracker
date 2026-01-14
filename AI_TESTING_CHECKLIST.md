# AI Features Full Test Checklist - January 14, 2026

## Overview

This checklist covers all AI features in TimeTracker for production testing.

**Production URL**: https://timetracker.shaemarcus.com
**Test Accounts Required**: Admin account + Regular user account

---

## Pre-Test Setup

- [ ] Login as admin user
- [ ] Go to **Admin → Settings → AI Features** to ensure AI is enabled
- [ ] Verify API key is configured (Gemini or OpenAI)

---

## Test Categories

### 1. 🔧 Admin AI Settings (Admin Only)

**Location**: Admin → Settings → AI Features tab

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 1.1 | View AI Features | Go to Admin Settings → AI Features | See list of all AI features with toggles | |
| 1.2 | Toggle Feature | Click toggle on any feature | Feature enables/disables, shows success message | |
| 1.3 | View Usage Stats | Check usage statistics section | See API call counts, token usage | |
| 1.4 | Set Per-User Override | Select a user, override a feature | User's feature setting changes | |

---

### 2. 👤 User AI Preferences (All Users)

**Location**: Settings → AI panel

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 2.1 | View Preferences | Go to Settings page | See AI preferences panel | |
| 2.2 | Toggle Personal Preference | Toggle a feature (that admin allows) | Preference saves, shows confirmation | |
| 2.3 | Disabled by Admin | Try to enable feature admin disabled | Should be grayed out or hidden | |

---

### 3. 💡 AI Suggestions (Time Entry)

**Location**: Time Page → Create time entry

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 3.1 | Suggestions Load | Click "+ Add Entry" or start timer | Suggestions dropdown appears after a moment | |
| 3.2 | Select Suggestion | Click on a suggestion | Project/task auto-fills | |
| 3.3 | Recent Pattern Suggestions | Have some time entries, then add new | Should see suggestions based on your patterns | |
| 3.4 | Feedback Submission | After selecting suggestion, rate it | Feedback should submit (check console/network) | |

---

### 4. 🚨 Anomaly Detection (Admin Only)

**Location**: Dashboard (admin view)

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 4.1 | View Anomaly Panel | Login as admin, go to Dashboard | See "Anomaly Alerts" panel | |
| 4.2 | Scan for Anomalies | Click "Scan" or "Refresh" button | Should scan and show any unusual patterns | |
| 4.3 | Dismiss Anomaly | If anomalies exist, click dismiss | Should ask for reason, then dismiss | |
| 4.4 | Severity Indicators | Check anomaly cards | Should show severity (critical/warning/info) | |

---

### 5. 📊 Payroll Forecast (Admin Only)

**Location**: Admin → Reports → Overview tab

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 5.1 | View Forecast Panel | Go to Admin Reports | See "Payroll Forecast" panel | |
| 5.2 | Change Period Type | Select Weekly/Bi-weekly/Monthly | Forecast updates for selected period | |
| 5.3 | View Confidence Intervals | Check forecast details | Should show low/medium/high estimates | |
| 5.4 | Trend Analysis | Check if trend info shown | Should indicate up/down/stable trend | |

---

### 6. 📈 Weekly Summary (All Users)

**Location**: Dashboard page

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 6.1 | View Summary Panel | Go to Dashboard | See "AI Weekly Summary" or similar panel | |
| 6.2 | Expand/Collapse | Click to expand the panel | Should show detailed AI-generated summary | |
| 6.3 | Insights & Tips | Read the summary content | Should have productivity insights/recommendations | |
| 6.4 | Refresh Summary | Click refresh if available | Should regenerate summary | |

---

### 7. 💬 NLP Chat Time Entry

**Location**: Time Page (chat icon or chat tab)

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 7.1 | Open Chat | Click chat icon on Time page | Chat interface opens | |
| 7.2 | Natural Language Parse | Type: "I worked on Project X for 2 hours" | Should parse and show preview | |
| 7.3 | Confirm Entry | Click confirm/create | Time entry should be created | |
| 7.4 | Complex Input | Type: "Yesterday from 9am to 11am on meetings" | Should correctly parse date/time/task | |
| 7.5 | Error Handling | Type gibberish | Should show helpful error message | |

---

### 8. ⚠️ Overtime Risk Panel (Admin)

**Location**: Admin → Reports

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 8.1 | View Panel | Go to Admin Reports | See Overtime Risk section | |
| 8.2 | Risk Indicators | Check user list | Shows risk level per user (high/medium/low) | |
| 8.3 | Projected Hours | Look at projections | Shows estimated overtime hours | |

---

### 9. 💰 Project Budget Forecast (Admin)

**Location**: Admin → Reports

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 9.1 | View Panel | Go to Admin Reports | See Project Budget section | |
| 9.2 | Budget vs Actual | Check project data | Shows budget utilization | |
| 9.3 | Projections | Look at forecast | Shows if project will be over/under budget | |

---

### 10. 💵 Cash Flow Chart (Admin)

**Location**: Admin → Reports

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 10.1 | View Chart | Go to Admin Reports | See Cash Flow chart | |
| 10.2 | Date Range | Change date range if option exists | Chart updates | |
| 10.3 | Projections | Check future months | Shows projected cash flow | |

---

### 11. 🧑‍💼 User Insights (Dashboard)

**Location**: Dashboard page

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 11.1 | View Panel | Go to Dashboard | See User Insights panel | |
| 11.2 | Productivity Metrics | Check the insights | Shows productivity score, trends | |
| 11.3 | Recommendations | Look for tips | AI provides improvement suggestions | |

---

### 12. 🔥 API Status Check

**Location**: Admin → Settings → AI Features

| # | Test | Steps | Expected Result | Pass/Fail |
|---|------|-------|-----------------|-----------|
| 12.1 | Check API Status | Look for status indicator | Shows "Connected" or API health | |
| 12.2 | API Provider | Verify provider shown | Shows Gemini/OpenAI as configured | |

---

## Quick API Tests (Network Tab)

Open browser DevTools (F12) → Network tab, then:

| Feature | Trigger | Expected API Call |
|---------|---------|-------------------|
| Suggestions | Open new time entry | `POST /api/ai/suggestions/time-entry` |
| Weekly Summary | Load Dashboard | `POST /api/ai/reports/weekly-summary` |
| Anomaly Scan | Dashboard (admin) | `POST /api/ai/anomalies/scan` or `GET /api/ai/anomalies/all` |
| NLP Parse | Send chat message | `POST /api/ai/nlp/parse` |
| NLP Confirm | Click confirm | `POST /api/ai/nlp/confirm` |
| Payroll Forecast | Admin Reports | `POST /api/ai/forecasting/payroll` |
| Feature List | Settings page | `GET /api/ai/features/` |

---

## Test Results Summary

**Date**: _______________  
**Tester**: _______________

| Category | Tests | Passed | Failed | Notes |
|----------|-------|--------|--------|-------|
| Admin AI Settings | 4 | | | |
| User AI Preferences | 3 | | | |
| AI Suggestions | 4 | | | |
| Anomaly Detection | 4 | | | |
| Payroll Forecast | 4 | | | |
| Weekly Summary | 4 | | | |
| NLP Chat Entry | 5 | | | |
| Overtime Risk | 3 | | | |
| Project Budget | 3 | | | |
| Cash Flow | 3 | | | |
| User Insights | 3 | | | |
| API Status | 2 | | | |
| **TOTAL** | **42** | | | |

---

## Common Issues & Troubleshooting

### AI Not Responding
1. Check API key is configured in Admin → Settings → AI Features
2. Check API status shows "Connected"
3. Check browser console for errors
4. Check network tab for 401/403/500 errors

### Suggestions Not Appearing
1. Ensure `ai_suggestions` feature is enabled (both admin and user)
2. Need some time entry history for pattern-based suggestions
3. Check network tab for API call success

### NLP Not Understanding
1. Use clear format: "[Task] for [duration]" or "[Task] from [time] to [time]"
2. Include project name if you have multiple projects
3. Check that `ai_nlp_entry` feature is enabled

### Anomalies Not Showing
1. Need sufficient time entry data (1+ week recommended)
2. Must be logged in as admin
3. Click "Scan" to trigger analysis

---

## Post-Test Actions

- [ ] Document any bugs found
- [ ] Report feature requests
- [ ] Update SESSION_REPORT with results
