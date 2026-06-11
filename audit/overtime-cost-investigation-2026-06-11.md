# Overtime Risk Cost & Display Investigation

## Smoke test context
Visible data (period 2026-06-08 to 2026-06-14, current week):

- Joe Bello: 28.6h current / 40h, projected 54.8h, Est Cost $26,617, "Projected 14.8h overtime"
- Bryan: 24.8h / 40h, projected 48.9h, Est Cost $332, "Projected 8.9h overtime"
- Jelry: 24.4h / 40h, projected 48.6h, Est Cost $321, "Projected 8.6h overtime"
- Daniel: 27.6h / 40h, projected 57.2h, Est Cost $645, "Projected 1.7.2h overtime" (malformed)

## Part A — Cost Calculation

### A1: Formula trace
Code path (backend):

- Entry: `ForecastingService.assess_overtime_risk(...)`
- File: `backend/app/ai/services/forecasting_service.py`
- In-loop computations:
  - `days_left = (week_end - tenant_today).days`
  - `projected_total = current_hours + (avg_daily * days_left)`
  - `overtime_hours = max(projected_total - overtime_threshold, 0)`
  - `pay_rate = await self._get_user_pay_rate(user.id, tenant_today)`
  - `overtime_cost = Decimal(str(overtime_hours)) * pay_rate * Decimal("1.5")`
  - Response payload sets:
    - `projected_overtime = max(projected_total - overtime_threshold, 0)`
    - `estimated_cost = overtime_cost.quantize(Decimal("0.01"))`

Exact meaning of current formula:

- `estimated_cost = projected_overtime_hours × selected_base_rate × 1.5`

Inputs feeding estimated_cost:

- Projected overtime hours (not total projected hours)
- Base pay rate selected by `_get_user_pay_rate`
- Hard-coded multiplier `1.5`

### A2: PayRate query logic
Pay rate selection method:

- Method: `_get_user_pay_rate(self, user_id: int, today: date) -> Decimal`
- File: `backend/app/ai/services/forecasting_service.py`
- Query criteria:
  - `PayRate.user_id == user_id`
  - `PayRate.is_active == True`
  - `(PayRate.effective_to IS NULL OR PayRate.effective_to >= today)`
- Ordering / selection:
  - `ORDER BY PayRate.effective_from DESC LIMIT 1`

Fallback behavior:

- If no row matches, returns hard-coded default `Decimal("25.00")`

Important observed behavior:

- `_get_user_pay_rate` ignores `PayRate.rate_type` and `PayRate.overtime_multiplier`
- Therefore, if a user has non-hourly rates (e.g., monthly), `base_rate` is still treated as hourly in overtime estimation
- Contrast: `backend/app/services/payroll_service.py` contains explicit `rate_type` handling and conversion logic

Can users have multiple PayRate rows?

- Yes. Model supports historical rows (`effective_from`, `effective_to`) and query selects newest active row that is not expired as of `today`.

### A3: SMC pay rate data
Attempted production/staging connectivity probe from this environment:

- Environment has `DATABASE_URL` defined
- Parsed target: host `localhost`, db `time_tracker` (from backend `.env`)
- Connection attempt failed: `ConnectionRefusedError [WinError 1225]` (no reachable DB listener)

Result:

- Could not execute tenant data audit queries for `company_id=2` from this runtime
- No data was modified (read-only attempt only)

Read-only SQL to run when DB access is available:

```sql
-- 1) Company timezone and tenant "today" anchor
SELECT id, name, timezone
FROM companies
WHERE id = 2;

-- 2) Users in company 2
SELECT u.id, u.name, u.email, u.is_active, u.company_id
FROM users u
WHERE u.company_id = 2
ORDER BY u.name;

-- 3) All pay rate rows for company 2 users
SELECT
  u.id AS user_id,
  u.name AS user_name,
  pr.id AS pay_rate_id,
  pr.rate_type,
  pr.base_rate,
  pr.currency,
  pr.overtime_multiplier,
  pr.effective_from,
  pr.effective_to,
  pr.is_active
FROM users u
LEFT JOIN pay_rates pr ON pr.user_id = u.id
WHERE u.company_id = 2
ORDER BY u.name, pr.effective_from DESC;

-- 4) Users with NO pay_rate rows at all
SELECT u.id, u.name, u.email
FROM users u
LEFT JOIN pay_rates pr ON pr.user_id = u.id
WHERE u.company_id = 2
GROUP BY u.id, u.name, u.email
HAVING COUNT(pr.id) = 0
ORDER BY u.name;

-- 5) Rows expired as-of tenant local "today" (for visibility)
-- Replace :tenant_today with resolved date for company timezone.
SELECT
  u.id AS user_id,
  u.name,
  pr.id AS pay_rate_id,
  pr.rate_type,
  pr.base_rate,
  pr.effective_from,
  pr.effective_to,
  pr.is_active
FROM pay_rates pr
JOIN users u ON u.id = pr.user_id
WHERE u.company_id = 2
  AND pr.effective_to IS NOT NULL
  AND pr.effective_to < :tenant_today
ORDER BY u.name, pr.effective_to DESC;

-- 6) Row forecasting_service WOULD currently pick (per user)
-- Replace :tenant_today with resolved tenant-local date.
WITH ranked AS (
  SELECT
    u.id AS user_id,
    u.name AS user_name,
    pr.id AS pay_rate_id,
    pr.rate_type,
    pr.base_rate,
    pr.currency,
    pr.overtime_multiplier,
    pr.effective_from,
    pr.effective_to,
    pr.is_active,
    ROW_NUMBER() OVER (
      PARTITION BY u.id
      ORDER BY pr.effective_from DESC
    ) AS rn
  FROM users u
  LEFT JOIN pay_rates pr
    ON pr.user_id = u.id
   AND pr.is_active = TRUE
   AND (pr.effective_to IS NULL OR pr.effective_to >= :tenant_today)
  WHERE u.company_id = 2
)
SELECT *
FROM ranked
WHERE rn = 1
ORDER BY user_name;
```

### A4: Label accuracy
Current label in UI:

- Overtime panel shows `Est. Cost`

What payload field actually is:

- `estimated_cost` from backend is overtime-only estimate (projected overtime hours × selected base rate × 1.5)

Implication:

- Label `Est. Cost` is ambiguous and reads like total labor cost
- More accurate label would be `Est. Overtime Cost` (or `Est. OT Premium Cost` depending product intent)

## Part B — Display Bug

### B1: Formatter location
Backend recommendation string construction:

- `backend/app/ai/services/forecasting_service.py`
- High risk branch:
  - `f"Urgent: Reduce workload. Projected {projected_total - overtime_threshold:.1f}h overtime"`
- High branch:
  - `f"Review workload distribution. Likely to exceed threshold by {projected_total - overtime_threshold:.1f}h"`

Frontend rendering path:

- `frontend/src/components/ai/OvertimeRiskPanel.tsx`
- Recommendation is rendered directly: `{risk.recommendation}`
- No numeric parsing/reformatting is applied to recommendation text in this component

### B2: Root cause
Observed malformed text:

- `Projected 1.7.2h overtime`

Code-level findings:

- Source formatter in backend uses Python numeric format `:.1f` (for numeric values this yields `17.2`, not `1.7.2`)
- Frontend does not mutate this string

Conclusion:

- Could not reproduce `1.7.2` from current source path
- Most likely causes are:
  - malformed value originated in payload text before UI render (from another code path/version), or
  - smoke-test capture/transcription artifact

Reproduction status (source-based):

- Not reproducible from current formatter logic in repository

### B3: Other affected formatters
Current scope check in frontend:

- Overtime recommendation text is displayed raw only in `OvertimeRiskPanel`
- No shared formatter was found that rewrites recommendation numeric fragments into dotted patterns

Potentially affected area if malformed source text exists:

- Any consumer that displays backend recommendation strings directly (currently the overtime panel)

## Findings summary

### Confirmed bugs
- Ambiguous UI copy: `Est. Cost` does not describe that value is overtime-only estimate.
- Potential logic mismatch: forecasting overtime estimate ignores `rate_type` and `overtime_multiplier` while payroll service handles `rate_type` explicitly.

### Data quality issues
- Could not audit `company_id=2` pay-rate records due unavailable DB connectivity from this environment (`localhost/time_tracker` connection refused).
- Required tenant data audit remains pending with live DB access.

### Misleading copy
- `Est. Cost` likely implies total estimated weekly cost but current backend returns overtime-only estimate.

### Recommended fixes (prioritized)
1. Rename panel label to `Est. Overtime Cost` immediately (copy-only, low risk).
2. Add backend response field docstring/comments clarifying `estimated_cost` semantics.
3. Align forecasting pay-rate computation with payroll semantics:
   - handle `rate_type` (`hourly`, `monthly`, `daily`, etc.)
   - use `overtime_multiplier` from selected pay rate or company policy
4. Add defensive backend validation/logging for recommendation numeric text generation.
5. Add frontend test asserting recommendation string integrity for values like `17.2`.
6. Execute pending company_id=2 data audit queries and attach results to this report.

## Was this caused by yesterday's PayRate timezone change?
Preliminary answer: **Partially (filtering only), but not the primary driver of the observed magnitude.**

Reasoning:

- Yesterday’s change affects which pay-rate row is considered active around date boundaries (`effective_to >= tenant_today`).
- That can change selected row near boundary days, but by itself does not explain extremely large asymmetry such as `$26,617` vs `$332` unless the selected row has an unusually large `base_rate` (or non-hourly rate interpreted as hourly).
- The larger structural contributor appears to be current forecasting logic treating `base_rate` as hourly and multiplying by fixed `1.5`, without `rate_type` normalization.
