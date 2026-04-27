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
- Partial indexes (ux_time_entries_one_running_per_user, ix_time_entries_running) are declared in raw SQL only, not in SQLAlchemy models. alembic check reports them as drift. Consider declaring them in models.py during Prompt 7.5 lint/type cleanup so the model is the source of truth.

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

## Discovered while implementing B2 / B12 (2026-01-…)

- backend/app/routers/work_sessions.py:537 and :639 build TimeEntry(is_running=True, ...) and commit. After B2 (migration 021_unique_running_timer), if a user already has a running timer when a meeting/resume code path fires, the commit will now raise IntegrityError instead of silently creating a duplicate. The new partial unique index is the correct invariant; these two call sites should be wrapped in the same try/except IntegrityError -> 409 pattern used in start_timer. Risk is low (these paths assume no manual timer running) but should be hardened.
- backend/app/database.py: _build_engine does not currently honor a hypothetical staging ENVIRONMENT distinctly — anything other than literal production falls through to NullPool. Acceptable for now; revisit if a staging tier ever needs the pooled engine.

## Deploy notes — Prompt 3

### Required env vars now mandatory in production
The following env vars previously had silent auto-generation fallbacks. As of
this commit, they raise at startup if unset/empty when ENVIRONMENT=production:
- SECRET_KEY
- API_KEY_ENCRYPTION_KEY

Verify both are explicitly set in the Lightsail deploy environment before
deploying this commit. If they are not, the app will fail to start with a
clear ValueError instead of silently rotating keys per restart.

### Behavior change during Redis outage
Before this commit: revoked JWTs continued to work if Redis was unreachable
(except Exception: pass swallowed the error — fail-open).

After this commit: revoked JWTs are rejected (HTTP 401, WS close 1011 — fail-closed).

Operational implication: a Redis outage now manifests as elevated 401 rates
on authenticated endpoints. Operators should:
- Treat sustained 401 spikes as a Redis health signal.
- Monitor for the log identifier `auth.blacklist_unavailable` (HTTP path) and
  the WS close-code-1011 pattern.

### Frontend ↔ backend deploy ordering for B15 logout
Backend can deploy first. The new logout handler accepts an optional
LogoutRequest body containing refresh_token; if missing, it logs a WARNING
(`auth.logout_missing_refresh`) and proceeds with access-token-only
revocation. An older frontend (without refresh_token in the logout body)
continues to work but leaves refresh tokens valid until natural expiry.

After frontend deploys: refresh tokens are revoked on logout as intended.

### Skip-count environmental wobble (informational)
Local pytest skip count varies (4 vs 6) depending on whether redis-server
is running on the dev host. Two tests in test_password_reset.py are gated
by @skip_without_redis. CI uses a Redis service container so its skip count
is stable. Document in eventual deploy runbook so any team member running
local tests doesn't think "6 → 4" is a regression.

### Test infrastructure note (not a deploy concern)
conftest.py now resets token_blacklist._redis between tests to handle
pytest-asyncio function-scoped event-loop binding. Production runs a
single persistent loop, so no equivalent change is needed in production
code. If that ever changes (e.g., subprocess workers each running their
own loop), the same defensive reset pattern should be applied to
token_blacklist.get_redis().
