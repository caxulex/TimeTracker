# Post-Launch TODO

Issues identified during the production-readiness campaign that are out of scope
for launch but should be addressed afterward.

## Test infrastructure

- **TRUNCATE overhead dominates non-auth test runtime.** Full suite takes ~15 min
  despite bcrypt optimization. Likely fix: refactor handler-side session.commit()
  to enable SAVEPOINT-based rollback isolation (Option A from Prompt 0.7), OR
  explore pytest-xdist parallelization. Either is a multi-hour refactor.

## Observability

- GitHub Actions Node.js deprecation: bumped to v6 preemptively (2026-06-02
  forced migration); monitor for future major bumps.

## Lint / type debt

- ruff: 4,313 pre-existing errors (4,099 auto-fixable). Deferred to Prompt 7.5.
- mypy: 761 pre-existing errors across 66 files. Deferred to Prompt 7.5.
- Both currently non-fatal in CI; flip to strict after Prompt 7.5 clears them.

## Dev experience

- 6 eslint warnings (react-hooks/exhaustive-deps, react-refresh/only-export-components).
  Under --max-warnings 50 threshold; cleanup cosmetic.


## Timer-domain risks deferred from B1/B3/B10/B14/B20 session

- backend/app/routers/time_entries.py:list_time_entries date filter is still
  naive-datetime based. `datetime.combine(..., datetime.min.time())` returns
  a tzinfo-less datetime whose interpretation depends on the Postgres session
  TimeZone. Two tests in tests/test_time_entries_findings.py::TestB20 are
  marked NEEDS_VERIFICATION for this reason — B20's half-open change removes
  the 23:59:59.999999 microsecond cliff but not the TZ ambiguity. Prompt 4
  (timezone-aware rewrite of time_entries + reports date filters) is the
  proper fix.
- backend/app/routers/time_entries.py:get_timer_status — audit referenced
  `get_timer`; current function is `get_timer_status` (same route path
  `/timer`). No code impact, flagging for documentation parity.
- backend/app/routers/time_entries.py:make_entry_response — signature uses
  implicit-Optional `str = None` defaults (pre-existing). Introduced one
  `# type: ignore[arg-type]` on the new orphan-return call site to avoid
  adding a new mypy error. Clean fix is to change the signature to
  `Optional[str] = None` (matches line 165 notes in mypy output).
- backend/app/routers/time_entries.py:create_manual_entry (~line 709) calls
  `start_time = entry_data.start_time or now` when `duration_seconds` is
  supplied. That means `POST /api/time` with only `duration_seconds`
  silently anchors the entry to server-now, which is usually not what a
  backdated manual entry wants. Not in scope for this session's findings.
- backend/app/routers/time_entries.py: `TimeEntry.end_time == None` and
  `start_time == None` comparisons (pre-existing) should use `.is_(None)`
  — ruff E711. Not in scope; covered by the lint-debt row above.
- WebSocket broadcasts fire inside the request handler before the response
  returns. A slow broadcast will slow GET /timer/start/stop. Out of scope.

## Test infrastructure (continued)

- 9 tests in test_multitenancy.py and test_websocket.py skip with "PostgreSQL
  database not available" on Windows local despite pg16 being reachable.
  Predates Prompt 1. Probe mechanism likely differs from the main conftest
  fixture chain. Low priority — tests run and pass in CI.

## Test infrastructure (continued)

- 9 tests in test_multitenancy.py and test_websocket.py skip with "PostgreSQL
  database not available" on Windows local despite pg16 being reachable.
  Predates Prompt 1. Probe mechanism likely differs from the main conftest
  fixture chain. Low priority — tests run and pass in CI.
