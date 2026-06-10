# date.today() / datetime.now() Sweep Inventory

Scope scanned (read-only):
- backend/app/ai/services/**
- backend/app/ai/router.py
- backend/app/ai/utils/**

Patterns scanned:
- date.today()
- datetime.now()
- datetime.utcnow()

Summary:
- Total matches: 30
- Category A (BUG): 25
- Category B (ACCEPTABLE): 2
- Category C (UNCERTAIN): 3
- Matches in backend/app/ai/router.py: 0
- Matches in backend/app/ai/utils/: 0

## Category A — BUGS (tenant-relative use of server date)

| File:Line | Context (line +/-2) | Why it's a bug | Suggested fix |
|---|---|---|---|
| backend/app/ai/services/anomaly_service.py:136 | # Check cache\ncache_date = date.today().isoformat()\nif self.cache: | Cache key rolls over on server date, but anomaly windows are user/tenant-facing day ranges; causes stale or premature cache rollover near tenant midnight boundaries. | Use tenant-local date for cache partition key (`get_tenant_today(...).isoformat()`). |
| backend/app/ai/services/anomaly_service.py:331 | period_start = date.today() - timedelta(days=period_days)\nperiod_end = date.today()\nfeatures = AnomalyFeatures( | Period boundary for anomaly scan should be tenant-local civil day, not server day. | Replace with tenant-local `today` from helper and derive `period_start/period_end` from it. |
| backend/app/ai/services/anomaly_service.py:332 | period_start = date.today() - timedelta(days=period_days)\nperiod_end = date.today()\nfeatures = AnomalyFeatures( | Same boundary issue as line 331; inclusive period_end drifts for tenants ahead/behind server timezone. | Use tenant-local `today`. |
| backend/app/ai/services/forecasting_service.py:509 | current_hours = await self._get_user_hours(\n    user.id,\n    week_start,\n    date.today()\n) | End date for "current week" risk assessment is tenant-relative; server date can clip/extend week hours incorrectly around day transitions. | Pass tenant-local `today` into this call. |
| backend/app/ai/services/forecasting_service.py:524 | # Project hours for rest of week\ndays_left = (week_end - date.today()).days\nprojected_additional = avg_daily * days_left | Remaining days in week should be based on tenant local day. | Compute from tenant-local `today`. |
| backend/app/ai/services/forecasting_service.py:584 | def _get_week_start(self) -> date:\n    """Get Monday of current week."""\n    today = date.today()\n    return today - timedelta(days=today.weekday()) | Week anchor used for forecasting windows; should align to tenant week, not server week. | Make `_get_week_start` accept `today: date` parameter and pass tenant-local date from caller. |
| backend/app/ai/services/forecasting_service.py:652 | from app.models import TimeEntry\n\nstart_date = date.today() - timedelta(days=days)\n\nresult = await self.db.execute( | Historical averaging window start uses server day; this shifts daily grouping window for tenants near UTC boundaries. | Derive `start_date` from tenant-local `today`. |
| backend/app/ai/services/forecasting_service.py:838 | burn_rate_daily=Decimal("0.00"),\ndays_remaining=365 if not project.deadline else max((project.deadline - date.today()).days, 0),\nprojected_completion=project.deadline if project.deadline else date.today() + timedelta(days=365), | Budget projection and days remaining are tenant-facing calendar outputs; server date creates off-by-one day behavior. | Use tenant-local `today` for all calendar math. |
| backend/app/ai/services/forecasting_service.py:839 | days_remaining=365 if not project.deadline else max((project.deadline - date.today()).days, 0),\nprojected_completion=project.deadline if project.deadline else date.today() + timedelta(days=365),\nrisk_level=RiskLevel.LOW, | Same as line 838 (same constructor block). | Use tenant-local `today`. |
| backend/app/ai/services/forecasting_service.py:853 | # Calculate burn rate\nfirst_entry = min(entries, key=lambda e: e.start_time)\ndays_active = max((date.today() - first_entry.start_time.date()).days, 1)\nburn_rate_daily = spent_to_date / days_active | Days active is a tenant-facing age metric; off-by-one when server day differs from tenant day. | Use tenant-local `today`. |
| backend/app/ai/services/forecasting_service.py:858 | # Calculate days remaining based on deadline or budget\nif project.deadline:\n    days_remaining = max((project.deadline - date.today()).days, 0)\n    projected_completion = project.deadline | Deadline distance is tenant calendar math. | Use tenant-local `today`. |
| backend/app/ai/services/forecasting_service.py:865 | remaining_budget = budget_total - spent_to_date\ndays_remaining = int(remaining_budget / burn_rate_daily) if remaining_budget > 0 else 0\nprojected_completion = date.today() + timedelta(days=days_remaining) | Projected completion date should be computed from tenant-local day. | Use tenant-local `today`. |
| backend/app/ai/services/forecasting_service.py:869 | else:\n    days_remaining = 365\n    projected_completion = date.today() + timedelta(days=365)\n    projected_total = spent_to_date | Fallback projection based on server date can drift for tenant reports. | Use tenant-local `today`. |
| backend/app/ai/services/forecasting_service.py:878 | deadline_risk = False\nif project.deadline:\n    days_to_deadline = (project.deadline - date.today()).days\n    if days_to_deadline <= 7 and utilization > 75: | Deadline risk trigger depends on tenant calendar boundaries. | Use tenant-local `today`. |
| backend/app/ai/services/nlp_service.py:138 | # Date patterns\nDATE_KEYWORDS = {\n    "today": lambda: date.today(),\n    "yesterday": lambda: date.today() - timedelta(days=1), | NLP interpretation of "today" is explicitly user-relative and should be tenant-local. | Replace static lambdas with timezone-aware resolution from tenant helper (or resolver callback). |
| backend/app/ai/services/nlp_service.py:139 | DATE_KEYWORDS = {\n    "today": lambda: date.today(),\n    "yesterday": lambda: date.today() - timedelta(days=1),\n    "tomorrow": lambda: date.today() + timedelta(days=1), | "yesterday" should use tenant day boundary. | Use tenant-local `today - 1 day`. |
| backend/app/ai/services/nlp_service.py:140 | "today": lambda: date.today(),\n"yesterday": lambda: date.today() - timedelta(days=1),\n"tomorrow": lambda: date.today() + timedelta(days=1),\n"last week": lambda: date.today() - timedelta(weeks=1), | "tomorrow" relative date is tenant-local concept. | Use tenant-local base date. |
| backend/app/ai/services/nlp_service.py:141 | "yesterday": lambda: date.today() - timedelta(days=1),\n"tomorrow": lambda: date.today() + timedelta(days=1),\n"last week": lambda: date.today() - timedelta(weeks=1),\n"this morning": lambda: date.today(), | "last week" anchor should be tenant-local day. | Use tenant-local base date. |
| backend/app/ai/services/nlp_service.py:142 | "tomorrow": lambda: date.today() + timedelta(days=1),\n"last week": lambda: date.today() - timedelta(weeks=1),\n"this morning": lambda: date.today(),\n"this afternoon": lambda: date.today(), | "this morning" maps to current tenant day. | Use tenant-local base date. |
| backend/app/ai/services/nlp_service.py:143 | "last week": lambda: date.today() - timedelta(weeks=1),\n"this morning": lambda: date.today(),\n"this afternoon": lambda: date.today(),\n"this evening": lambda: date.today(), | "this afternoon" maps to current tenant day. | Use tenant-local base date. |
| backend/app/ai/services/nlp_service.py:144 | "this morning": lambda: date.today(),\n"this afternoon": lambda: date.today(),\n"this evening": lambda: date.today(),\n} | "this evening" maps to current tenant day. | Use tenant-local base date. |
| backend/app/ai/services/nlp_service.py:245 | else:\n    # Default to today\n    result.start_time = datetime.combine(date.today(), datetime.min.time())\n    if result.duration_seconds: | Default parse date should be tenant-local "today" for user intent. | Use tenant-local `today` before `datetime.combine`. |
| backend/app/ai/services/nlp_service.py:363 | if day_name in text_lower:\n    # Find the most recent occurrence of this day\n    today = date.today()\n    days_since = (today.weekday() - day_num) % 7 | Relative weekday resolution is tenant-local natural language semantics. | Base weekday math on tenant-local `today`. |
| backend/app/ai/services/nlp_service.py:384 | clean_text = re.sub(...)\nparsed = date_parser.parse(clean_text, fuzzy=True, dayfirst=False)\nif parsed.date() != date.today():  # Only use if not defaulting to today\n    return ParsedDate(...) | "defaulted to today" check should compare against tenant-local today. | Compare to tenant-local `today`. |
| backend/app/ai/services/nlp_service.py:715 | 2. Project name (must match one from the list above)\n3. Task description\n4. Date (relative to today: {date.today().isoformat()})\n\nReturn a JSON object with: | Prompt conditioning gives AI a server-local "today" anchor; can bias extraction to wrong civil day for tenant. | Inject tenant-local date string in prompt context. |

## Category B — ACCEPTABLE

| File:Line | Context (line +/-2) | Why it's OK |
|---|---|---|
| backend/app/ai/services/forecasting_service.py:632 | # Calculate running time (use timezone-aware datetime)\nrunning_seconds = 0\nnow = datetime.now(timezone.utc)\nfor entry in running_entries: | Used for elapsed duration of currently running timers (`now - entry_start`). This is absolute-time arithmetic in UTC and is not tenant-civil-day boundary logic. |
| backend/app/ai/services/ml_anomaly_service.py:729 | # Get baseline and recent data\nperiod_start = datetime.now(timezone.utc) - timedelta(days=period_days)\n\nentries_result = await self.db.execute( | Uses timezone-aware UTC instant for rolling lookback window in model assessment. Not server-local naive date math; no tenant civil-day boundary implied at this line. |

## Category C — UNCERTAIN

| File:Line | Context (line +/-2) | What we need to know to categorize |
|---|---|---|
| backend/app/ai/services/forecasting_service.py:693 | or_(\n    PayRate.effective_to == None,\n    PayRate.effective_to >= date.today()\n) | Need domain rule for `PayRate.effective_to`: is it tenant civil date (recommended) or system-wide UTC date policy? If tenant-civil, this is Category A. |
| backend/app/ai/services/reporting_service.py:806 | # This week vs last week\nnow_utc = datetime.now(timezone.utc)\ntoday_utc = now_utc.date()\nweek_start = today_utc - timedelta(days=today_utc.weekday()) | Need product definition for "this week" in project health: tenant-local week or UTC week. If tenant-local, this should move to tenant timezone helper. |
| backend/app/ai/services/reporting_service.py:896 | # Last 30 days hours - use UTC datetime for consistent timezone handling\nnow_utc = datetime.now(timezone.utc)\ntoday_utc = now_utc.date()\nthirty_days_ago = today_utc - timedelta(days=30) | Need product definition for "last 30 days" in user insights: UTC sliding window vs tenant-local civil-date window. If tenant-local reporting parity is required, this becomes Category A. |

## Existing Helper Check (reporting_service.py:338)

Found existing resolver:
- `backend/app/ai/services/reporting_service.py:338` defines `_resolve_tenant_timezone(self, user_id) -> str`.

Assessment:
- Good building block for timezone string resolution.
- Not reusable across services as-is because:
  - It is a private method inside `ReportingService`.
  - It returns only timezone string, not resolved tenant-local date/datetime.
  - It is not exposed in `backend/app/ai/utils/` where other AI services can import it.

## Proposed helper

Recommended new module:
- `backend/app/ai/utils/tenant_time.py`

API sketch:

```python
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession

async def get_tenant_today(db: AsyncSession, company_id: int | None) -> date:
    """Return tenant-local civil date, falling back to UTC when timezone missing/invalid."""

async def get_tenant_now(db: AsyncSession, company_id: int | None) -> datetime:
    """Return tenant-local current datetime (tz-aware), UTC fallback."""
```

Suggested internals:
- Reuse existing company timezone source (`Company.timezone`) and UTC fallback semantics.
- Use `app.utils.timewindow.local_today(tz)` and `app.utils.timewindow.now_utc()` + zone conversion.
- Optionally add helper to resolve timezone once and pass through call stack for bulk operations.

## Implementation order

1. High impact, low ambiguity (fix first):
- `backend/app/ai/services/nlp_service.py` (all Category A calls, especially keyword/date parsing and default date assignment)
- `backend/app/ai/services/forecasting_service.py` window and projection boundaries (`509, 524, 584, 652, 838, 839, 853, 858, 865, 869, 878`)
- `backend/app/ai/services/anomaly_service.py` period boundaries and cache date (`136, 331, 332`)

2. Medium impact, needs domain confirmation (fix after product decision):
- `backend/app/ai/services/forecasting_service.py:693`
- `backend/app/ai/services/reporting_service.py:806, 896`

3. Leave as-is (documented acceptable):
- `backend/app/ai/services/forecasting_service.py:632`
- `backend/app/ai/services/ml_anomaly_service.py:729`

## Notes

- No `datetime.utcnow()` occurrences were found in the scoped paths.
- No `date.today()` / `datetime.now()` / `datetime.utcnow()` occurrences were found in:
  - `backend/app/ai/router.py`
  - `backend/app/ai/utils/`
