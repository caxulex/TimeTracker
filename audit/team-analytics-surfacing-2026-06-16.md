# Team Analytics Surfacing Audit (2026-06-16)

## 1. Inventory of current consumers (if any)

### Confirmed direct consumers
- AI endpoint exists and is wired in backend router:
  - `POST /api/ai/analytics/team` in `backend/app/ai/router.py`.
  - `POST /api/ai/analytics/compare-teams` in `backend/app/ai/router.py`.
- Service is consumed by AI router only:
  - `backend/app/ai/services/team_analytics_service.py` via `get_team_analytics_service()` imports in AI router.

### Confirmed non-consumers
- No usage of `team_analytics_service` outside AI router in `backend/app/**`.
- No usage in `backend/tests/**`.
- No usage in `backend/scripts/**` (including scheduler jobs).
- No usage in scheduled reports/email/report-template pipeline:
  - `backend/app/routers/report_templates.py` does not reference team analytics service or AI team endpoint.
- No usage found in Basecamp webhooks or webhook handlers.
- No evidence of Slack/email notification builder importing Team Analytics service.

### Important distinction
- Frontend currently uses `/api/reports/admin/teams` (from `backend/app/routers/reports.py`) for "team analytics" in Admin Reports.
- This is a separate, non-AI aggregate endpoint and does not expose AI Team Analytics insights/recommendations from `/api/ai/analytics/team`.

## 2. Verification that no UI currently renders this data

- No frontend reference to `/api/ai/analytics/team` in `frontend/src/**`.
- No frontend reference to `/api/ai/analytics/compare-teams` in `frontend/src/**`.
- No frontend usage of AI Team Analytics response fields (`ai_insights`, `recommendations`, velocity/collaboration structures) from the AI endpoint.
- Current team section UI in `frontend/src/pages/AdminReportsPage.tsx` renders data from `/api/reports/admin/teams` only.

Conclusion: the AI Team Analytics backend feature is currently unrendered in UI.

## 3. Git history relevant context (when added, why no UI)

- Service introduced in commit `b26020d` (2025-12-31):
  - Added `backend/app/ai/services/team_analytics_service.py`.
  - Added AI router and schemas (`backend/app/ai/router.py`, `backend/app/ai/schemas.py`).
- String-level history (`-S "/analytics/team"`) points to same introducing commit; no later endpoint rewiring/removal found.
- No deleted Team Analytics UI artifact found via delete-history scan (`diff-filter=D`) for team analytics terms.
- `frontend/src/pages/AdminReportsPage.tsx` was added in a different commit (`573a631`) and uses `/api/reports/admin/teams`, not AI Team Analytics endpoint.

Interpretation: AI Team Analytics was shipped backend-first and never integrated into frontend rendering.

## 4. Production usage signal (API hits in last 30 days, if measurable)

### What is measurable from this workspace
- No runtime `logs/` artifacts are present in workspace to inspect request paths.
- No dedicated persistent request-hit table/model was found for endpoint-level traffic accounting.
- Existing `audit_logs` model is generic action/resource logging, not guaranteed HTTP access log coverage by route.

### What is not directly measurable here
- Production endpoint hit counts for `/api/ai/analytics/team` in last 30 days cannot be proven from local repository alone.

### Read-only SQL recommendation (if production telemetry exists)
- If your infra stores request logs in DB (or centralized log sink), run equivalent query on that system:

```sql
SELECT
  DATE_TRUNC('day', timestamp) AS day,
  COUNT(*) AS hits
FROM request_logs
WHERE path = '/api/ai/analytics/team'
  AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1;
```

- If only app audit logs are available and route/path is included in `details`, adapt with:

```sql
SELECT COUNT(*)
FROM audit_logs
WHERE timestamp >= NOW() - INTERVAL '30 days'
  AND details ILIKE '%/api/ai/analytics/team%';
```

## 5. Recommended approach

Recommendation: **Build UI (admin surface) in a follow-up implementation PR**.

Rationale:
- No hidden consumer was found for AI Team Analytics service output.
- Endpoint/service are maintained and recently touched, so removing backend code now would be premature.
- Existing Admin Reports already has a Teams tab and role gating, making it the lowest-friction integration point.

## 6. If "build UI": proposed location, access model, components

### Proposed location
- Primary: `Admin Reports -> Teams` tab (`/admin/reports`) as an "AI Team Analytics" panel per team.
- Keep existing `/api/reports/admin/teams` summary cards/charts as top-level overview.
- Add opt-in drill-down (expand card or drawer) that fetches `/api/ai/analytics/team` for selected team.

### Access model decision
- **Phase 1 (now): Admin-only** (`admin`, `super_admin`, `company_admin`) to match current admin analytics and current backend endpoint role checks.
- Team-member self-service access: **defer** pending product decision on visibility/privacy (cross-member metrics, overtime/weekend visibility).
- Optional future Phase 2: team leads/managers access for own teams only, with explicit backend authorization changes.

### What to render (existing contract only)
- Use current `TeamAnalyticsResponse` shape as-is:
  - Core metrics: totals, active members, projects/tasks.
  - Velocity: history chart + trend label.
  - Collaboration: density + top edges.
  - Workload: gini + top contributors + underutilized members.
  - AI copy blocks: `ai_insights` + `recommendations`.
- Component pattern:
  - Reuse visual structure from `UserInsightsPanel` / `ProjectHealthCard` style blocks.
  - Keep Team Analytics panel self-contained (new component under `frontend/src/components/ai/`).

## 7. Implementation plan (separate PR after this audit)

1. Add frontend API client method for `POST /api/ai/analytics/team` in existing AI API module.
2. Add `TeamAnalyticsPanel` component (loading/error/empty states, charts, insight/recommendation lists).
3. Integrate into `frontend/src/pages/AdminReportsPage.tsx` Teams tab as per-team drill-down.
4. Gate by existing admin route/access checks only (no backend auth changes in first pass).
5. Add component tests for:
   - happy path render,
   - empty/no-members data,
   - error fallback.
6. Keep backend unchanged (contract reuse only); no scoring/model logic changes.

---

## Final assessment for this audit pass

- AI Team Analytics backend capability is present.
- It currently has no verified frontend rendering and no verified hidden delivery consumer.
- Building an admin-facing UI surface is justified and lower risk than removal at this stage.