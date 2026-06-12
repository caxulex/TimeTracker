# Avg Hours/Day Transparency Investigation

## Surfaces inventory (Part A)

| # | Surface | File:Line | Numerator | Denominator | Copy shown |
|---|---|---|---|---|---|
| 1 | My Reports (Reports page; preset week/month/custom) | frontend/src/pages/ReportsPage.tsx:181, frontend/src/pages/ReportsPage.tsx:182, frontend/src/pages/ReportsPage.tsx:380 | totalHours (from weeklyData.total_seconds) | dailyChartData.length | Avg Hours/Day + "across {N} days" |
| 2 | User Detail (Admin user profile detail card) | frontend/src/pages/UserDetailPage.tsx:200, frontend/src/pages/UserDetailPage.tsx:202, frontend/src/pages/UserDetailPage.tsx:205 | userData.month_hours (from backend) | active_days_this_month (from backend) | "Avg Hours/Day" + "{N} active days" |
| 3 | Admin Reports -> Individual user modal/card | frontend/src/pages/AdminReportsPage.tsx:737, frontend/src/pages/AdminReportsPage.tsx:739 | selectedUserDetail.month_hours (from backend) | active_days_this_month (from backend) | "Avg/Day" (active-days context shown separately) |
| 4 | Dashboard AI -> User Insights panel | frontend/src/components/ai/UserInsightsPanel.tsx:183, frontend/src/components/ai/UserInsightsPanel.tsx:185 | metrics.total_hours_30d (from backend AI service) | work_days = distinct dates with entries in last 30 days | "Daily Avg" |

### Backend formulas feeding the above surfaces

1. My Reports (surface #1)
- Source: backend/src weekly endpoint returns full daily series including zero-hour days.
- File: backend/app/routers/reports.py:296, backend/app/routers/reports.py:337
- Mechanics:
  - daily_breakdown includes one row per calendar day in selected range.
  - Frontend divides by number of rows in that array.
- Exact frontend formula:
  - avgHoursPerDay = round((totalHours / dailyChartData.length) * 10) / 10
- Denominator type:
  - All calendar days in selected range (includes weekends and includes today when current period selected).

2. User Detail + Admin Reports (surfaces #2 and #3 share one backend computation)
- Source endpoint: /api/reports/admin/users/{user_id}
- File: backend/app/routers/reports.py:1411, backend/app/routers/reports.py:1424
- Exact formula:
  - active_days = count(distinct date(start_time)) for month window
  - avg_hours_per_day = round(month_seconds / 3600 / max(active_days, 1), 2)
- Denominator type:
  - Days with logged hours (distinct entry dates), not calendar days.
  - Includes today if there is any entry today (partial-day included).
  - Weekends only counted if user logged on weekend.

3. User Insights panel (surface #4)
- Source endpoint: /api/ai/reports/user-insights
- File: backend/app/ai/services/reporting_service.py:905, backend/app/ai/services/reporting_service.py:917
- Exact formula:
  - work_days = count(distinct date(start_time)) in last 30 days
  - avg_daily_hours = round((total_seconds / 3600) / work_days, 1)
- Denominator type:
  - Days with logged hours only.
  - Includes today if user has an entry today.
  - Weekends only counted if user logged on weekend.

### Additional average-daily calculations found (backend, not currently wired to an active UI label in frontend/src)

1. Admin workers report API
- File: backend/app/routers/admin.py:227, backend/app/routers/admin.py:281
- Formula: avg_daily_hours = total_hours / days_in_period
- Denominator type: all calendar days in requested period.
- Frontend usage status: API client exists (frontend/src/api/client.ts:1038), no active page in frontend/src currently renders this value.

2. Report templates productivity analysis
- File: backend/app/services/report_templates.py:302, backend/app/services/report_templates.py:309
- Formula: avg_hours_per_day = total_hours / max(days_worked, 1)
- Denominator type: days with logged hours.
- Surface status: template payload (not part of the identified Avg Hours/Day cards above).

### Centralized vs duplicated today

- Not centralized.
- At least 4 distinct average-daily implementations:
  - Frontend local division in ReportsPage (calendar-day denominator).
  - Backend reports router user metrics (days-worked denominator).
  - Backend AI reporting service user insights (days-worked denominator).
  - Backend admin workers report (calendar-day denominator).
- Result: behavior and transparency differ by surface.

## Working days configuration (Part B)

### Existing state

- Confirmed absent in models/migrations:
  - Company.working_days
  - User.working_days
  - UserSettings/CompanySettings schedule/workdays fields
- Checked model definitions:
  - Company in backend/app/models/__init__.py:109 has timezone/date/time settings but no working-days field.
  - User in backend/app/models/__init__.py:256 has expected_hours_per_week but no working-days field.
- Checked migrations:
  - backend/alembic/versions/003_add_staff_fields.py:26 adds expected_hours_per_week.
  - No migration adds working_days/schedule/workdays for Company/User.

### Related fields found (prior scheduling/workload intent)

- User.expected_hours_per_week
  - Model: backend/app/models/__init__.py:256
  - Migration: backend/alembic/versions/003_add_staff_fields.py:26
  - Used in AI/user staffing flows as expected weekly load.
- Company overtime config (policy-oriented, not schedule calendar)
  - backend/app/models/__init__.py:137

### Proposed schema additions

- Convention decision:
  - Use JSON array of integers (not SQL ARRAY) to match current codebase convention of portable JSON fields in models/migrations.
  - Weekday convention should be Monday=0 ... Sunday=6, consistent with Python date.weekday() usage and existing comments (backend/app/ai/services/ml_anomaly_service.py:91).

- Proposed fields:
  - Company.working_days: JSON list[int], non-null, default [0,1,2,3,4]
  - User.working_days: JSON list[int] or null (null = inherit company)

- Resolution helper:
  - get_user_working_days(user):
    - if user.working_days is not null: return user.working_days
    - elif user.company.working_days is not null: return company list
    - else: return [0,1,2,3,4]

- Locked product behavior alignment:
  - User overrides company when set.
  - Null user value means inherit company.
  - New companies default to Mon-Fri.

## In-progress signaling (Part C)

### Reusable patterns identified

- Live indicator (pulsing green dot) already implemented:
  - frontend/src/components/dashboard/YourStatsCard.tsx:38-42
  - Used to mark "Today" stat as live while timer is running; driven by dataUpdatedAt freshness and local ticking logic (frontend/src/components/dashboard/YourStatsCard.tsx:92-99).
- Additional live-style indicators exist in dashboard/admin timer contexts:
  - frontend/src/pages/DashboardPage.tsx:159
- Footer freshness patterns already exist in AI panels:
  - "Generated ..." in WeeklySummaryPanel (frontend/src/components/ai/WeeklySummaryPanel.tsx:292)
  - "Generated ..." fallback text in UserInsightsPanel (frontend/src/components/ai/UserInsightsPanel.tsx:278-280)
  - "Updated ..." patterns in forecasting cards (example: frontend/src/components/ai/CashFlowChart.tsx:219)

### Backend response fields that already hint at completeness/in-progress

- reports weekly endpoint (My Reports source):
  - No explicit period_complete / partial / is_current flag in WeeklySummary payload model (backend/app/routers/reports.py:68).
- dashboard stats endpoint:
  - running_timer boolean exists (backend/app/routers/reports.py:76), but this flags timer state, not period completeness.
- AI weekly summary path:
  - comparison_is_week_complete exists in metrics (backend/app/ai/services/reporting_service.py:656), with comparison_label adjusted for same-period comparison when week is in progress (backend/app/ai/services/reporting_service.py:191, backend/app/ai/services/reporting_service.py:211-219).
  - generated_at exists for freshness (backend/app/ai/services/reporting_service.py:160).

### Recommended response field additions for Avg Hours/Day transparency

For every endpoint returning Avg Hours/Day-style metrics:
- avg_hours_per_day_value (existing numeric)
- avg_hours_per_day_numerator_hours
- avg_hours_per_day_denominator_days
- avg_hours_per_day_denominator_type: calendar_days | working_days | days_with_entries
- avg_hours_per_day_includes_today: boolean
- avg_hours_per_day_today_is_partial: boolean
- avg_hours_per_day_working_days_source: user | company | default
- avg_hours_per_day_working_days_used: [0..6]

These fields make UI copy explicit and auditable.

## Centralization (Part D)

- Current state: mixed and duplicated.
- There is not one place to fix this today.
- Recommended extraction target:
  - backend/app/services/avg_hours_service.py (new shared utility)
  - Shared API contract object returned by each endpoint that displays average daily hours.

### Suggested shared backend utility responsibilities

- Resolve working days via user/company/default helper.
- Compute completed_working_days_in_period (with option to exclude current local day when in progress).
- Compute days_with_entries and calendar_days for transparency metadata.
- Return both value and explanation metadata in one structure.

### Surface integration plan from central utility

- Replace frontend local division in ReportsPage with backend-provided transparent average payload.
- Replace ad hoc average formulas in:
  - backend/app/routers/reports.py (user metrics)
  - backend/app/routers/admin.py (workers report)
  - backend/app/ai/services/reporting_service.py (user insights)
  - backend/app/services/report_templates.py (if kept user-facing)

## Proposed PR breakdown

Option A - Phased (recommended if >3 surfaces affected):
- Phase 4a: Add working_days fields + migration + resolution helper
  - ~1h, backend only
- Phase 4b: Centralized avg calculation utility + apply to all surfaces
  - ~1-2h, backend
- Phase 4c: Frontend transparency updates across surfaces
  - ~1h, frontend
- Phase 4d: Settings UI for working days config
  - ~1-2h, can defer

Option B - Single PR (recommended if <=3 surfaces):
- All of the above in one coherent PR

Recommendation:
- Option A (Phased).
- Reason: more than 3 affected surfaces/paths, with mixed backend + frontend logic and inconsistent denominator semantics today.
