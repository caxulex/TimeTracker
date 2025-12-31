# TimeTracker - AI Features QA Testing Checklist

**Generated:** December 31, 2025  
**Application:** TimeTracker  
**URL:** https://timetracker.shaemarcus.com/  
**AI Features Version:** Phase 1-5 Complete

---

## Overview

This checklist covers all AI features in TimeTracker. Tests are organized in two sections:
1. **Automated Tests** - Can be performed by the AI assistant via terminal/API
2. **Manual Tests** - Must be performed by a human in the browser

---

## AI Feature Inventory

| Feature ID | Feature Name | Backend | Frontend | Integration | Feature Flag |
|------------|--------------|---------|----------|-------------|--------------|
| `ai_suggestions` | Time Entry Suggestions | ✅ | ✅ | TimePage | `ai_suggestions` |
| `anomaly_detection` | Anomaly Detection | ✅ | ✅ | DashboardPage | `anomaly_detection` |
| `payroll_forecast` | Payroll Forecast | ✅ | ✅ | AdminReportsPage | `payroll_forecast` |
| `weekly_summary` | Weekly Summary | ✅ | ✅ | DashboardPage | `weekly_summary` |
| `overtime_risk` | Overtime Risk | ✅ | ✅ | AdminReportsPage | `overtime_risk` |
| `project_budget` | Project Budget | ✅ | ✅ | AdminReportsPage | `project_budget` |
| `cash_flow` | Cash Flow | ✅ | ✅ | AdminReportsPage | `cash_flow` |
| `nlp_time_entry` | NLP Chat Entry | ✅ | ✅ | TimePage | `nlp_time_entry` |
| `user_insights` | User Insights | ✅ | ✅ | DashboardPage | `user_insights` |
| `project_health` | Project Health | ✅ | ✅ | Not integrated | `project_health` |
| `burnout_detection` | Burnout Detection | ✅ | ✅ | Not integrated | `burnout_detection` |
| `task_estimation` | Task Estimation | ✅ | ✅ | Not integrated | `task_estimation` |

---

# PART 1: AUTOMATED TESTS (AI Assistant)

## 1. Build & Compilation Tests

### 1.1 Frontend TypeScript Compilation
- [x] Run `npm run build` in frontend directory ✅
- [x] Verify no TypeScript errors ✅
- [x] Verify no missing imports ✅
- [x] Check bundle size is reasonable (<2MB) ✅ (1.2MB gzipped: 302KB)

### 1.2 Backend Python Syntax
- [x] Run `python -m py_compile` on AI modules ✅
- [x] Verify no import errors in routers ✅
- [x] Check alembic migrations are up to date ✅

---

## 2. Backend API Endpoint Tests

**Summary:** 44 total AI endpoints registered (30 AI services + 14 feature toggles)

### 2.1 AI Status Endpoint
```bash
GET /api/ai/status
```
- [x] Endpoint registered ✅
- [ ] Returns 200 OK (needs live test)
- [ ] Returns provider status (needs live test)

### 2.2 Feature Toggle Endpoints (14 endpoints verified)
```bash
GET /api/ai/features           # List all features ✅
GET /api/ai/features/me        # Get my features ✅
GET /api/ai/features/me/{id}   # Get specific feature ✅
PUT /api/ai/features/me/{id}   # Toggle my feature ✅
GET /api/ai/features/check/{id} # Quick check ✅
```
- [x] All endpoints registered ✅

### 2.3 Admin Feature Endpoints
```bash
GET /api/ai/features/admin              ✅
PUT /api/ai/features/admin/{id}         ✅
GET /api/ai/features/admin/users/{uid}  ✅
PUT /api/ai/features/admin/users/{uid}/{fid}  ✅
DELETE /api/ai/features/admin/users/{uid}/{fid}  ✅
POST /api/ai/features/admin/batch-override ✅
```
- [x] All admin endpoints registered ✅

### 2.4 Suggestions Endpoints
```bash
POST /api/ai/suggestions/time-entry ✅
POST /api/ai/suggestions/feedback ✅
```
- [x] Endpoints registered ✅

### 2.5 Anomaly Detection Endpoints
```bash
POST /api/ai/anomalies/scan ✅
GET /api/ai/anomalies ✅
GET /api/ai/anomalies/all ✅
POST /api/ai/anomalies/dismiss ✅
```
- [x] Endpoints registered ✅

### 2.6 Forecasting Endpoints
```bash
POST /api/ai/forecast/payroll ✅
POST /api/ai/forecast/overtime-risk ✅
POST /api/ai/forecast/project-budget ✅
GET /api/ai/forecast/cash-flow ✅
```
- [x] Endpoints registered ✅

### 2.7 NLP Endpoints
```bash
POST /api/ai/nlp/parse ✅
POST /api/ai/nlp/confirm ✅
```
- [x] Endpoints registered ✅

### 2.8 Reporting Endpoints
```bash
POST /api/ai/reports/weekly-summary ✅
POST /api/ai/reports/project-health ✅
POST /api/ai/reports/user-insights ✅
```
- [x] Endpoints registered ✅

### 2.9 ML Endpoints (Phase 4)
```bash
POST /api/ai/ml/anomalies/scan ✅
POST /api/ai/ml/burnout/assess ✅
POST /api/ai/ml/burnout/team-scan ✅
POST /api/ai/ml/baseline/calculate ✅
```
- [x] Endpoints registered ✅

### 2.10 Task Estimation Endpoints
```bash
POST /api/ai/estimation/task ✅
POST /api/ai/estimation/batch ✅
POST /api/ai/estimation/train ✅
GET /api/ai/estimation/profile ✅
GET /api/ai/estimation/stats ✅
```
- [x] Endpoints registered ✅

### 2.11 Search & Analytics Endpoints (Phase 5)
```bash
POST /api/ai/search/similar-tasks ✅
POST /api/ai/search/time-suggestions ✅
POST /api/ai/analytics/team ✅
POST /api/ai/analytics/compare-teams ✅
```
- [x] Endpoints registered ✅

---

## 3. Frontend Component Tests

**Summary:** 16 AI components, 42 React hooks, 26 API functions

### 3.1 AI Component Exports (16 total)
- [x] AIFeatureToggle ✅
- [x] AIFeaturePanel ✅
- [x] AdminAISettings ✅
- [x] SuggestionDropdown ✅
- [x] AnomalyAlertPanel ✅
- [x] PayrollForecastPanel ✅
- [x] OvertimeRiskPanel ✅
- [x] ProjectBudgetPanel ✅
- [x] CashFlowChart ✅
- [x] ChatInterface ✅
- [x] WeeklySummaryPanel ✅
- [x] ProjectHealthCard ✅
- [x] UserInsightsPanel ✅
- [x] BurnoutRiskPanel ✅
- [x] TaskEstimationCard ✅

### 3.2 React Hooks (42 total)
- [x] useAIFeatures.ts: 15 hooks ✅
- [x] useAIServices.ts: 9 hooks ✅
- [x] useForecastingServices.ts: 8 hooks ✅
- [x] useNLPServices.ts: 3 hooks ✅
- [x] useReportingServices.ts: 7 hooks ✅

### 3.3 API Client Functions (26 total)
- [x] aiServices.ts: 17 functions ✅
- [x] forecastingServices.ts: 4 functions ✅
- [x] nlpServices.ts: 2 functions ✅
- [x] reportingServices.ts: 3 functions ✅

---

## 4. Router Registration Tests

### 4.1 Backend Main.py Registration
- [x] `ai_features.router` imported ✅
- [x] `ai_router` imported ✅
- [x] AI Features router registered at `/api` ✅
- [x] AI Services router registered at `/api` ✅

### 4.2 Frontend Integration Verification
Pages with AI components integrated:
- [x] TimePage: SuggestionDropdown + ChatInterface ✅
- [x] DashboardPage: AnomalyAlertPanel + WeeklySummaryPanel + UserInsightsPanel ✅
- [x] AdminReportsPage: PayrollForecastPanel + OvertimeRiskPanel + ProjectBudgetPanel + CashFlowChart ✅
- [x] AdminSettingsPage: AdminAISettings ✅
- [x] SettingsPage: AIFeaturePanel ✅

---

# PART 2: MANUAL TESTS (Human Tester)

## 5. Feature Toggle System (Admin)

### 5.1 Access Admin AI Settings
- [ ] Login as admin user
- [ ] Navigate to Settings → Admin Settings (if exists) OR `/admin`
- [ ] Verify "AI Features" tab/section exists
- [ ] Verify list of all AI features displayed

### 5.2 Toggle Global Features
- [ ] Toggle OFF `ai_suggestions` feature
- [ ] Verify toggle updates immediately
- [ ] Verify success notification
- [ ] Toggle ON `ai_suggestions` feature
- [ ] Verify toggle updates

### 5.3 Feature Status Indicators
- [ ] Verify enabled features show green indicator
- [ ] Verify disabled features show red/gray indicator
- [ ] Verify feature descriptions display correctly

### 5.4 Per-User Overrides (Admin)
- [ ] Select a regular user
- [ ] Override their `ai_suggestions` to OFF
- [ ] Verify override indicator shows
- [ ] Remove override
- [ ] Verify user returns to global setting

---

## 6. Feature Toggle System (User)

### 6.1 Access User AI Preferences
- [ ] Login as regular user
- [ ] Navigate to `/settings`
- [ ] Verify "AI Features" section visible
- [ ] Verify list shows available features

### 6.2 Toggle Personal Preferences
- [ ] Toggle OFF a feature
- [ ] Verify change saves
- [ ] Toggle ON a feature
- [ ] Verify change saves

### 6.3 Admin Override Handling
- [ ] As admin, override user's feature to OFF
- [ ] As user, verify feature shows as disabled
- [ ] Verify user cannot toggle it ON
- [ ] Verify "Admin disabled" message shown

### 6.4 Global Disable Handling
- [ ] As admin, disable feature globally
- [ ] As user, verify feature not visible OR shows disabled
- [ ] Verify user cannot enable it

---

## 7. AI Suggestions (TimePage)

### 7.1 Suggestions Panel Visibility
- [ ] Navigate to `/time`
- [ ] Click "Add Manual Entry" button
- [ ] Verify AI Suggestions panel appears at top of modal
- [ ] Verify "✨ Show AI Suggestions" button if collapsed

### 7.2 Suggestions Loading
- [ ] Open manual entry modal
- [ ] Verify suggestions load automatically
- [ ] Verify loading spinner shows briefly
- [ ] Verify suggestions display with confidence %

### 7.3 Suggestion Selection
- [ ] Click on a suggestion
- [ ] Verify project field auto-fills
- [ ] Verify task field auto-fills (if applicable)
- [ ] Verify description auto-fills (if applicable)
- [ ] Verify suggestion panel closes

### 7.4 Suggestion Feedback
- [ ] Select a suggestion → verify positive feedback sent
- [ ] Reject a suggestion (X button) → verify negative feedback sent
- [ ] Create entry with different project → verify implicit feedback

### 7.5 Feature Disabled State
- [ ] As admin, disable `ai_suggestions`
- [ ] As user, open manual entry modal
- [ ] Verify suggestions panel NOT visible
- [ ] Re-enable feature
- [ ] Verify panel reappears

---

## 8. NLP Chat Interface (TimePage)

### 8.1 Chat Panel Visibility
- [ ] Navigate to `/time`
- [ ] Verify "Quick Entry with AI" card visible (purple gradient)
- [ ] Verify expand/collapse works

### 8.2 Natural Language Parsing
- [ ] Type: "2 hours yesterday on Project Alpha"
- [ ] Submit
- [ ] Verify duration parsed: 2 hours
- [ ] Verify date parsed: yesterday's date
- [ ] Verify project matched (if exists)

### 8.3 Parse Confirmation
- [ ] After parsing, verify confirmation UI shows
- [ ] Verify parsed fields editable
- [ ] Click Confirm → verify entry created
- [ ] Verify success notification

### 8.4 Parse Errors
- [ ] Type: "invalid gibberish text"
- [ ] Submit
- [ ] Verify error/low confidence message
- [ ] Verify can retry

### 8.5 Feature Disabled State
- [ ] As admin, disable `nlp_time_entry`
- [ ] Refresh page
- [ ] Verify chat panel NOT visible
- [ ] Re-enable feature
- [ ] Verify panel reappears

---

## 9. Anomaly Detection (DashboardPage - Admin)

### 9.1 Panel Visibility
- [ ] Login as admin
- [ ] Navigate to `/dashboard`
- [ ] Verify "🤖 AI Anomaly Detection" section visible
- [ ] Verify panel displays anomaly list or empty state

### 9.2 Anomaly Display
- [ ] Verify anomalies show severity (critical/warning/info)
- [ ] Verify user name displayed
- [ ] Verify description of anomaly
- [ ] Verify recommendation shown

### 9.3 Scan on Demand
- [ ] Click "Scan" or refresh button
- [ ] Verify loading indicator
- [ ] Verify results update

### 9.4 Dismiss Anomaly
- [ ] Click dismiss on an anomaly
- [ ] Enter reason
- [ ] Confirm
- [ ] Verify anomaly removed from list

### 9.5 Non-Admin Access
- [ ] Login as regular user
- [ ] Navigate to `/dashboard`
- [ ] Verify anomaly panel NOT visible

### 9.6 Feature Disabled State
- [ ] As admin, disable `anomaly_detection`
- [ ] Refresh dashboard
- [ ] Verify panel NOT visible

---

## 10. Weekly Summary (DashboardPage)

### 10.1 Panel Visibility
- [ ] Navigate to `/dashboard`
- [ ] Verify "📊 AI Weekly Summary" section visible
- [ ] Verify collapsible (if configured)

### 10.2 Summary Content
- [ ] Expand panel
- [ ] Verify AI-generated text summary
- [ ] Verify metrics displayed (total hours, projects, etc.)
- [ ] Verify insights list
- [ ] Verify attention items (if any)

### 10.3 Refresh Summary
- [ ] Click refresh button
- [ ] Verify loading state
- [ ] Verify new summary generated

### 10.4 Feature Disabled State
- [ ] Disable `weekly_summary` feature
- [ ] Refresh page
- [ ] Verify panel NOT visible

---

## 11. User Insights (DashboardPage)

### 11.1 Panel Visibility
- [ ] Navigate to `/dashboard`
- [ ] Verify "🧠 AI Productivity Insights" section visible

### 11.2 Insights Content
- [ ] Verify productivity score displayed
- [ ] Verify work patterns shown
- [ ] Verify recommendations listed
- [ ] Verify trend indicators (up/down/stable)

### 11.3 Feature Disabled State
- [ ] Disable `user_insights` feature
- [ ] Refresh page
- [ ] Verify panel NOT visible

---

## 12. Payroll Forecast (AdminReportsPage)

### 12.1 Panel Visibility
- [ ] Login as admin
- [ ] Navigate to `/admin/reports`
- [ ] Verify "🤖 AI Payroll Forecast" section in Overview tab

### 12.2 Forecast Display
- [ ] Verify period selector (weekly/bi-weekly/monthly)
- [ ] Verify forecast periods displayed
- [ ] Verify predicted amounts
- [ ] Verify confidence intervals
- [ ] Verify trend indicators

### 12.3 Period Type Change
- [ ] Change period type
- [ ] Verify forecast updates
- [ ] Verify different periods shown

### 12.4 Non-Admin Access
- [ ] Login as regular user
- [ ] Navigate to `/admin/reports`
- [ ] Verify redirect (no access)

### 12.5 Feature Disabled State
- [ ] Disable `payroll_forecast`
- [ ] Refresh page
- [ ] Verify panel NOT visible

---

## 13. Overtime Risk (AdminReportsPage)

### 13.1 Panel Visibility
- [ ] Navigate to `/admin/reports` (Overview tab)
- [ ] Verify "⏰ AI Overtime Risk Analysis" section

### 13.2 Risk Display
- [ ] Verify employee list with risk levels
- [ ] Verify risk badges (low/medium/high/critical)
- [ ] Verify projected hours shown
- [ ] Verify estimated overtime cost
- [ ] Verify recommendations

### 13.3 Days Ahead Filter
- [ ] Change days ahead (7/14/30)
- [ ] Verify list updates

### 13.4 Feature Disabled State
- [ ] Disable `overtime_risk`
- [ ] Refresh page
- [ ] Verify panel NOT visible

---

## 14. Project Budget (AdminReportsPage)

### 14.1 Panel Visibility
- [ ] Navigate to `/admin/reports` (Overview tab)
- [ ] Verify "💰 AI Project Budget Forecast" section

### 14.2 Budget Display
- [ ] Verify project list
- [ ] Verify budget utilization %
- [ ] Verify burn rate
- [ ] Verify projected completion
- [ ] Verify risk indicators

### 14.3 Feature Disabled State
- [ ] Disable `project_budget`
- [ ] Refresh page
- [ ] Verify panel NOT visible

---

## 15. Cash Flow (AdminReportsPage)

### 15.1 Panel Visibility
- [ ] Navigate to `/admin/reports` (Overview tab)
- [ ] Verify "📈 AI Cash Flow Projection" section

### 15.2 Chart Display
- [ ] Verify weekly bars/chart
- [ ] Verify cumulative line
- [ ] Verify payroll obligations
- [ ] Verify tooltips on hover

### 15.3 Feature Disabled State
- [ ] Disable `cash_flow`
- [ ] Refresh page
- [ ] Verify panel NOT visible

---

## 16. Cross-Feature Tests

### 16.1 All Features Disabled
- [ ] As admin, disable ALL AI features
- [ ] As user, navigate through app
- [ ] Verify NO AI panels visible anywhere
- [ ] Verify app still functions normally

### 16.2 All Features Enabled
- [ ] As admin, enable ALL AI features
- [ ] Verify all panels appear in correct locations
- [ ] Verify no layout issues
- [ ] Verify no console errors

### 16.3 Mixed States
- [ ] Enable some features, disable others
- [ ] Verify only enabled features visible
- [ ] Verify disabled features hidden

---

## 17. Error Handling

### 17.1 API Errors
- [ ] Simulate backend down
- [ ] Verify graceful error messages in AI panels
- [ ] Verify app doesn't crash

### 17.2 Rate Limiting
- [ ] Make many rapid API calls
- [ ] Verify rate limit message if triggered
- [ ] Verify recovery after cooldown

### 17.3 Invalid Data
- [ ] Submit invalid NLP text
- [ ] Verify helpful error message
- [ ] Verify can retry

---

## 18. Performance

### 18.1 Initial Load
- [ ] Clear cache
- [ ] Load dashboard
- [ ] Verify AI panels don't block page load
- [ ] Verify skeleton/loading states show

### 18.2 Panel Refresh
- [ ] Click refresh on AI panel
- [ ] Verify only that panel reloads
- [ ] Verify other panels unaffected

### 18.3 Large Data Sets
- [ ] Test with many time entries
- [ ] Verify suggestions still fast
- [ ] Verify anomaly scan completes

---

## 19. Mobile Responsiveness

### 19.1 AI Panels on Mobile
- [ ] Open dashboard on mobile
- [ ] Verify AI panels stack vertically
- [ ] Verify panels scrollable
- [ ] Verify touch interactions work

### 19.2 Chat Interface on Mobile
- [ ] Open TimePage on mobile
- [ ] Verify chat input usable
- [ ] Verify keyboard doesn't block input
- [ ] Verify confirmation dialog fits screen

---

## 20. Accessibility

### 20.1 Keyboard Navigation
- [ ] Tab through AI panels
- [ ] Verify focus indicators
- [ ] Verify buttons activatable via Enter

### 20.2 Screen Reader
- [ ] Verify AI panels have proper headings
- [ ] Verify loading states announced
- [ ] Verify error messages announced

---

# Test Execution Log

| Date | Tester | Section | Test Type | Issues Found | Status |
|------|--------|---------|-----------|--------------|--------|
| | | | Auto/Manual | | |
| | | | | | |
| | | | | | |

---

# Quick Reference: Feature Flag IDs

| Feature Flag ID | UI Location | Who Sees It |
|-----------------|-------------|-------------|
| `ai_suggestions` | TimePage modal | All users |
| `anomaly_detection` | DashboardPage | Admin only |
| `payroll_forecast` | AdminReportsPage | Admin only |
| `weekly_summary` | DashboardPage | All users |
| `overtime_risk` | AdminReportsPage | Admin only |
| `project_budget` | AdminReportsPage | Admin only |
| `cash_flow` | AdminReportsPage | Admin only |
| `nlp_time_entry` | TimePage | All users |
| `user_insights` | DashboardPage | All users |
| `project_health` | Not integrated | - |
| `burnout_detection` | Not integrated | - |
| `task_estimation` | Not integrated | - |

---

# API Quick Test Commands

```bash
# Get AI status
curl -X GET https://timetracker.shaemarcus.com/api/ai/status

# Get my features (requires auth)
curl -X GET https://timetracker.shaemarcus.com/api/ai/features/me \
  -H "Authorization: Bearer <token>"

# Get suggestions
curl -X POST https://timetracker.shaemarcus.com/api/ai/suggestions/time-entry \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"partial_description": "", "use_ai": true, "limit": 5}'

# Parse NLP
curl -X POST https://timetracker.shaemarcus.com/api/ai/nlp/parse \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text": "2 hours yesterday on testing"}'

# Get weekly summary
curl -X POST https://timetracker.shaemarcus.com/api/ai/reports/weekly-summary \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

**Total Test Cases:** 120+  
**Automated Tests:** 40+  
**Manual Tests:** 80+  

*Generated: December 31, 2025*
