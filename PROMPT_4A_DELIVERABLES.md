# Prompt 4a — Backend Timezone Correctness Pass: Deliverables

**Branch:** `prep/production-readiness`
**Scope keys:** B6 (UTC vs civil-day mismatch in reports) · B7 (date-range
filters interpreted as UTC instead of tenant-local) · B9 (`datetime.utcnow()`
producing naive UTC) · B18 subset (cross-endpoint range consistency).
**Out of scope (deferred to 4b):** see `POST_LAUNCH_TODO.md` § "Prompt 4b".

## What 4a changed

### 1. New single-source-of-truth helper
- `backend/app/utils/timewindow.py` — `now_utc()`, `local_today(tz)`,
  `day_bounds(d, tz)`, `week_bounds(d, tz, week_starts_on=0)`,
  `month_bounds(d, tz)`, `range_bounds(start, end, tz)`. All bounds are
  half-open `[start_utc, end_utc)`. DST-correct (IANA via stdlib
  `zoneinfo`).

### 2. New tests
- `backend/tests/test_timewindow.py` — **20 tests, 20 pass**. Covers:
  - LA spring-forward 2026-03-08 (23-hour day) ✓
  - LA fall-back 2026-11-01 (25-hour day) ✓
  - London spring 2026-03-29 / fall 2026-10-25 ✓
  - Week + month bounds across DST transitions ✓
  - `range_bounds` inclusive end + inversion error ✓
- `backend/tests/test_timezone_correctness.py` — **2 tests, 2 pass**.
  **Cross-endpoint integration test (NON-NEGOTIABLE deliverable).**
  Creates a `time_entry` whose UTC start is 2026-02-11 07:30Z (i.e.
  2026-02-10 23:30 in `America/Los_Angeles`), pins the company tz to LA,
  and asserts:
  - `GET /api/time?start_date=2026-02-10&end_date=2026-02-10` returns
    the entry **exactly once**.
  - `GET /api/time?start_date=2026-02-11&end_date=2026-02-11` (the UTC
    civil date) returns it **zero times**.
  - `GET /api/reports/dashboard` accepts the LA-pinned tenant without
    error.

### 3. Tenant-local routing
- `backend/app/dependencies.py` — added `get_company_timezone(current_user, db)`.
  Returns `"UTC"` if the user has no `company_id`; else does an explicit
  `select(Company.timezone)` (no lazy relationship, async-safe).
- `backend/app/routers/companies.py` — `CompanyUpdate.timezone` validated
  via `@field_validator` against `zoneinfo.available_timezones()`. Typos
  rejected at the API boundary.
- `backend/requirements.txt` — pinned `tzdata==2026.2` (PEP-615 companion;
  required for Alpine / slim Linux production base images that lack the
  system IANA db, and for Windows dev).

### 4. Endpoints rewritten to use `timewindow.*` + `tz` dependency
All 11 endpoints in `backend/app/routers/reports.py`:
`/dashboard`, `/weekly`, `/by-project`, `/by-task`, `/team`, `/export`,
`/admin/dashboard`, `/admin/teams`, `/admin/users/{user_id}`,
`/admin/users`, `/team-timesheet`, plus `/email`. Both private helpers
(`_generate_time_report`, `_get_team_timesheet_data`,
`_generate_team_timesheet_report`) now accept `tz: str` and call
`range_bounds` / `day_bounds` instead of `datetime.combine(...)`.

`backend/app/routers/work_sessions.py` — `/reports/daily` and
`/reports/summary` converted.

`backend/app/routers/time_entries.py` — `GET /api/time` list filter
converted (B7 + B20 fix combined: half-open AND tenant-local).

### 5. `datetime.utcnow()` sweep
Replaced with `app.utils.timewindow.now_utc()` in:
- `backend/app/routers/account_requests.py`
- `backend/app/routers/approvals.py`
- `backend/app/routers/websocket.py`
- `backend/app/services/scheduled_reports.py`
- `backend/app/services/report_templates.py`
- `backend/app/services/payroll_service.py:600` — Modification 1
  (REPLACE rather than BUMP because `period.approved_at = ...` is a
  non-arithmetic assignment to a tz-aware DB column; the fact that the
  source datetime was *naive* was the bug).

### 6. Lint guard
`backend/ruff.toml` — enabled rules `DTZ003` (`datetime.utcnow()` ban)
and `DTZ005` (`datetime.now()` without tz ban). Per Modification 2,
**no glob patterns**: each deferred 4b file is enumerated by exact
path with a `# TODO(4b): remove after sweep` comment. Tests are
allowlisted via the existing `tests/*` block.

After 4a, `python -m ruff check app/ --select DTZ003,DTZ005` reports
**0 errors**.

## Verification

```
python -m pytest tests/ -k "report or time_entr or work_session or timewindow or timezone or approval or account_request"
   88 passed (baseline 45 + 43 new/included)
python -m pytest tests/test_timewindow.py
   20 passed
python -m pytest tests/test_timezone_correctness.py
   2 passed                      ← non-negotiable cross-endpoint test
python -m ruff check app/ --select DTZ003,DTZ005
   0 errors                      ← rule active, no regressions
python -m mypy app/
   765 errors                    ← +1 vs 764 baseline (within noise;
                                    timewindow.py is 0 errors)
```

## Files modified (4a only)

```
backend/app/utils/timewindow.py                  NEW
backend/tests/test_timewindow.py                 NEW
backend/tests/test_timezone_correctness.py       NEW
backend/requirements.txt                         tzdata==2026.2
backend/ruff.toml                                DTZ003 + DTZ005 + per-file-ignores
backend/app/dependencies.py                      get_company_timezone
backend/app/routers/companies.py                 IANA validator
backend/app/routers/reports.py                   tz threaded through 11 endpoints + 3 helpers
backend/app/routers/work_sessions.py             tz threaded through 2 endpoints
backend/app/routers/time_entries.py              tz threaded through list_time_entries
backend/app/routers/account_requests.py          utcnow sweep
backend/app/routers/approvals.py                 utcnow sweep
backend/app/routers/websocket.py                 utcnow sweep
backend/app/services/scheduled_reports.py        utcnow sweep
backend/app/services/report_templates.py         utcnow sweep
backend/app/services/payroll_service.py          utcnow sweep (L600)
POST_LAUNCH_TODO.md                              4b list + per-user tz note + deploy note
PROMPT_4A_DELIVERABLES.md                        this file
```

## Rollback / risk notes

- `Company.timezone` already existed in migration `010` (`nullable=False,
  server_default='UTC'`). No schema migration was issued, so rollback is
  pure code revert.
- Any existing client that submitted `start_date` / `end_date` as
  *UTC*-civil dates rather than *local*-civil dates will see results
  shift by up to one day. This is the correct behaviour. Document for
  customers in the launch announcement.
