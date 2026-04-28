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

- ~~backend/app/routers/time_entries.py:list_time_entries date filter is still
  naive-datetime based.~~ **RESOLVED in Prompt 4a** — replaced with
  `app.utils.timewindow.day_bounds` / `range_bounds` that interpret the
  client-supplied `start_date` / `end_date` as tenant-local civil dates and
  produce tz-aware half-open UTC bounds. See `backend/tests/test_timezone_correctness.py`
  for the cross-endpoint LA midnight-straddle proof.

## Prompt 4b — remaining timezone correctness sweep

The 4a pass focused on the user-visible date-range surface (reports.py,
work_sessions.py, time_entries.py) and the highest-value `datetime.utcnow()`
call sites (account_requests.py, approvals.py, websocket.py,
scheduled_reports.py, payroll_service.py:600, report_templates.py). The
following call sites remain on naive `datetime.now()` / `datetime.utcnow()`
and must be migrated to `app.utils.timewindow.now_utc` in Prompt 4b. Each
is currently silenced individually in `backend/ruff.toml`
`[lint.per-file-ignores]` (DTZ003 + DTZ005) — the `# TODO(4b): remove
after sweep` comment marks each entry. **Remove the entry from
ruff.toml as you migrate each file.**

- `app/routers/admin.py`
- `app/routers/export.py`
- `app/routers/email_logs.py`
- `app/routers/monitoring.py`
- `app/ai/router.py`
- `app/ai/models/feature_engineering.py`
- `app/ai/services/anomaly_service.py`
- `app/ai/services/forecasting_service.py`
- `app/ai/services/ml_anomaly_service.py`
- `app/ai/services/nlp_service.py`
- `app/ai/services/reporting_service.py`
- `app/ai/services/semantic_search_service.py`
- `app/ai/services/suggestion_service.py`
- `app/ai/services/task_estimation_service.py`
- `app/ai/services/team_analytics_service.py`
- `app/services/ip_security.py`
- `app/services/payroll_report_service.py`
- `app/services/payslip_pdf_service.py`
- `app/services/slack_service.py`

## Prompt 4 follow-ups

- **Per-user timezone override (future enhancement).** 4a treats the
  *company* timezone (`Company.timezone`) as the single source of truth for
  every report rendered to every user in that tenant. A user travelling
  across timezones, or a multi-region team that does not share a single
  civil day, will see boundaries pinned to the company's IANA zone.
  Adding `User.timezone` (nullable, IANA, falls back to company tz) and
  threading it through `get_company_timezone` would resolve this without
  any further changes to `app.utils.timewindow`. Out of scope for 4a.
- **Frontend datetime audit (Prompt 7).** All client-side `Date` /
  `Intl.DateTimeFormat` rendering still relies on the browser local zone.
  After 4a/4b, the API contract is canonically tenant-local; the
  frontend must (a) display UTC instants in the company's IANA tz, and
  (b) submit `start_date` / `end_date` as plain `YYYY-MM-DD` civil dates
  (the backend already interprets them in tenant-local time). Track in
  Prompt 7 frontend pass.
- **Operational deploy note.** Companies are created with
  `timezone='UTC'` (DB default). Tenant admins must `PATCH /companies/me`
  with `{"timezone": "<IANA>"}` to switch. The `CompanyUpdate` schema
  rejects non-IANA values via `zoneinfo.available_timezones()` so a typo
  is caught at the API boundary instead of silently corrupting bounds.
- **Production tzdata pin.** `tzdata==2026.2` was added to
  `backend/requirements.txt` because Alpine and minimal Linux base
  images do not ship the IANA tz database that `zoneinfo` reads at
  runtime. Removing this pin will break every report on every
  non-Debian production image — keep it.
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


## Deploy notes — Prompt 5 (B8 / B13 / B21 — WS hardening)

### Behavior change at startup
The FastAPI lifespan now calls `load_active_timers_from_db(company_id=None)`
once at boot to warm `manager.active_timers` for every tenant in a single
DB pass. The call is wrapped in try/except: if the warm-cache query fails
the app logs `app.warm_cache_failed` at ERROR and **continues startup with
an empty cache**. The first per-connection load for each tenant will then
populate that tenant's slice on demand. Operators should grep for
`app.warm_cache_failed` in startup logs after deploy.

### WS connect cost
Pre-Prompt 5: every new WebSocket connection ran an unfiltered
`SELECT * FROM time_entries WHERE end_time IS NULL` and overwrote
`manager.active_timers` (cross-tenant leak risk + N full scans on
reconnect storms during deploy churn).

Post-Prompt 5: each connection runs a company-scoped query
(`WHERE end_time IS NULL AND users.company_id = :cid`) and merges
results via `dict.update`. Per-connection DB cost is now bounded by
the number of running timers for the connecting user's tenant, not the
global running-timer count. Reconnect storms after a deploy now scale
with per-tenant load instead of global load.

### WS auth surface unchanged
Prompt 3's fail-closed Redis behavior in `get_current_user_ws` is
preserved — Prompt 5 did not touch the auth path.

## Risks observed but not fixed during Prompt 5

- backend/app/routers/websocket.py — `team_ids` cached on the connection
  manager at connect time is intentionally **stale across team-membership
  changes during the connection**. A user added to or removed from a team
  while their WS is open won't see / will continue to see team-scoped
  broadcasts until they reconnect. By design for the realtime path; document
  in the admin guide if this surprises ops.
- backend/app/routers/websocket.py:91 — `ConnectionManager.disconnect`
  iterates `self.team_members.items()` with an unused loop variable
  (`team_id`). Pre-existing B007 ruff finding; cosmetic.
- backend/app/routers/websocket.py — `manager.active_timers` is in-process
  state. Multi-worker deploys (uvicorn workers > 1) will keep separate
  caches per worker. Out of scope for Prompt 5 (would need Redis-backed
  shared state); not a correctness issue per se because per-connection
  loads ensure each worker's view is tenant-correct.
- Local-only env wobble: on Windows hosts, `redis.asyncio` against a
  Redis instance running in WSL Ubuntu can intermittently fail with
  `Error 22` even when `redis-cli ping` succeeds, due to the
  proactor-loop / WSL networking interaction. This affects any auth-
  protected test that exercises the JWT blacklist; CI (Linux) is
  unaffected. Documented for future contributors so a flaky local run
  isn't mistaken for a regression.


## Deploy notes — backend medium polish (B16 / B23 / B29)

### B16 — Trusted-proxy-aware client IP

`get_client_ip(request)` in `backend/app/routers/auth.py` no longer trusts
`X-Forwarded-For` / `X-Real-IP` blindly. The header is honored only when
the immediate TCP peer (`request.client.host`) is in the new
`TRUSTED_PROXIES` setting. Each entry may be either an exact IP
(`10.0.0.5`) or a CIDR block (`10.0.0.0/8`); parsed via
`ipaddress.ip_network(strict=False)`.

#### Required env var (production)

```dotenv
# Comma-separated list of CIDRs / IPs allowed to set X-Forwarded-For.
# Set to your reverse-proxy / load-balancer subnet.
# Empty value => trust no proxy (fall back to peer IP only).
TRUSTED_PROXIES=10.0.0.0/8,127.0.0.1
```

If left empty in production, the FastAPI lifespan logs a single startup
warning `auth.no_trusted_proxies` and the app falls back to using the
direct peer IP for every audit log / login lockout / rate-limit key.
Lightsail deployment behind nginx: set `TRUSTED_PROXIES` to the nginx
subnet (typically `127.0.0.1` for same-host nginx, or the container
network CIDR for compose deployments).

### B29 — list_time_entries authorization tightening

`GET /api/time-entries?user_id=<other>` previously returned an empty
`200` for non-admins requesting a user with whom they share no team.
The endpoint now returns `403 {"detail":"You do not have permission to
view this user's time entries."}` when:

- caller is not admin / superadmin, **and**
- `?user_id` is supplied, **and**
- `?user_id != caller.id`, **and**
- no row in `team_members` exists where the caller and target share a
  team.

#### Frontend impact

Frontend currently treats an empty list as "no entries". After this
change, the same query for a stranger now returns 403. Callers should:

- surface a "you don't have access" toast, **not** "no results", and
- avoid pre-populating the user-id filter with a value the current user
  cannot legally query (e.g., from a stale URL share).

No change for self-lookups, teammate-lookups, no-`user_id` queries, or
admin / superadmin queries.

### B23 — list_time_entries enrichment N+1 fix

The list endpoint previously issued, per page:

1. count query
2. sum-of-duration query
3. main page query
4. `SELECT … FROM projects WHERE id IN (…)` enrichment
5. `SELECT … FROM tasks WHERE id IN (…)` enrichment
6. `SELECT … FROM users WHERE id IN (…)` enrichment

Now: count and sum are merged into a single aggregate query, and the
project / task / user names are eager-loaded via SQLAlchemy
`joinedload` (single LEFT JOIN — safe because all three relationships
are has-one). The endpoint hits `time_entries` exactly twice per
request (stats + page). No client-visible behavior change — just lower
DB cost on long-tail tenants. Verified by
`backend/tests/test_time_entries_query_count_b23.py` which asserts
`count("time_entries" statements) <= 2` over a 50-entry / 10-project /
10-task / 3-user dataset.

### Bare-except sweep deferred sites

Out-of-scope for this prompt (intentional fallbacks or already
narrowed); revisit during the Prompt 7.5 lint cleanup:

- `app/ai/utils/cache_manager.py` — 12 sites of intentional Redis
  graceful-degradation fallback (lines 71, 92, 116, 139, 156, 175, 196,
  216, 250, 266, 290).
- `app/ai/services/ai_client.py:145, 227` — `is_available` probes;
  intentional broad catch.
- `app/ai/services/ml_anomaly_service.py:724` — already logs and
  returns a degraded response.
- `app/routers/companies.py:754` — re-raises `HTTPException`.
- `app/routers/ai_features.py:470` — counter increment, intentional
  no-op on metric backend failure.
- `app/main.py:165` — narrow `urlparse` fallback.
- `app/routers/monitoring.py:106` — already returns explicit error
  dict.
- `app/services/auth_service.py:31` — bcrypt verify intentionally
  returns `False` on any exception (timing-attack hygiene).

In-scope sweep done in this prompt:

- `app/services/payroll_report_service.py:383` — narrowed bare
  `except` to `except (TypeError, ValueError, AttributeError)`.
- `app/routers/notifications.py` — bulk-WS delivery `except Exception:
  pass` replaced with a `CancelledError` / system-exit re-raise plus a
  `logger.warning("notifications.bulk_ws_delivery_failed")` for the
  swallowed delivery failure.


---

## B17 token storage migration plan (deferred from prep/production-readiness session)

**Status:** Deferred to post-launch. Audit finding B17 (medium severity).
TODO comments added in source at every localStorage token access in
`frontend/src/api/client.ts` and `frontend/src/stores/authStore.ts`.

### Risk being deferred

Both access and refresh tokens are stored in `localStorage`. Any XSS
anywhere in the SPA grants total account takeover (steal + replay both
tokens with no MFA challenge). Estimated effort: **medium** (~1–2 days
including tests and a staged migration window). Not safe to attempt in a
single hardening session because it interacts with: the Zustand `persist`
middleware, the redirect-loop guard in `client.ts`, the existing B15
logout-revoke flow, and cross-subdomain cookie scope for tenants on
`*.timetracker.shaemarcus.com`.

### Affected files

Backend:
- `backend/app/routers/auth.py` — login, refresh, logout endpoints.
- `backend/.env.example` — document new cookie-scope env var if added.

Frontend:
- `frontend/src/api/client.ts` — request interceptor, refresh flow,
  `forceLogoutAndRedirect`.
- `frontend/src/stores/authStore.ts` — login, logout, fetchUser,
  onRehydrateStorage, partialize shape.
- `frontend/src/stores/authStore.test.ts` — adjust mocks to expect
  cookie-based refresh and in-memory access token.

### Backend changes

1. **Login (`POST /api/auth/login`)**: alongside the existing JSON body
   response, set the refresh token via:
   ```python
   response.set_cookie(
       key="refresh_token",
       value=refresh_token,
       httponly=True,
       secure=True,
       samesite="strict",
       max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
       # Scope: confirm tenant subdomain handling. If tenants live at
       # *.timetracker.shaemarcus.com and the API is at api.timetracker...,
       # set domain=".timetracker.shaemarcus.com" so the cookie is sent on
       # cross-subdomain requests. Otherwise omit `domain` for host-only.
   )
   ```
   Continue returning `refresh_token` in the JSON body during the
   migration window (backward compatibility with old frontend deploys).
   Add a TODO with a removal date once the frontend rollout is complete.

2. **Refresh (`POST /api/auth/refresh`)**: accept refresh token from
   EITHER `request.cookies.get("refresh_token")` OR
   `body.refresh_token`, **preferring the cookie**. Document the
   dual-source acceptance as a deliberate migration concession.

3. **Logout (`POST /api/auth/logout`)**: confirm B15's flow already
   accepts refresh token from either cookie or body. Set
   `response.delete_cookie("refresh_token", ...)` on success so the
   browser drops the cookie immediately.

### Frontend changes

1. In `client.ts`, replace the module-scope `localStorage`-based token
   access with private state plus accessors:
   ```ts
   let accessToken: string | null = null;
   export function getAccessToken() { return accessToken; }
   export function setAccessToken(t: string | null) { accessToken = t; }
   ```
   Wire the request interceptor to `getAccessToken()`.

2. Replace every `localStorage.setItem('access_token', ...)` call with
   `setAccessToken(...)`. Remove every
   `localStorage.setItem('refresh_token', ...)` (the cookie is set by
   the server).

3. In the response interceptor's refresh branch, call
   `axios.post(url, {}, { withCredentials: true })` — the cookie is
   sent automatically; no body needed once the backend cookie path is
   live. Keep the body fallback during the dual-source window.

4. On app load (in `main.tsx` or store `onRehydrateStorage`), if the
   persisted state says `isAuthenticated` but `getAccessToken()` is
   null, call `/auth/refresh` with `{ withCredentials: true }` to mint
   a new access token from the cookie. This replaces today's
   "no token = clear stale auth" branch.

5. Update Zustand `partialize` if needed — `access_token` /
   `refresh_token` were never in the persisted slice, so this is mostly
   a no-op, but verify the rehydration logic.

6. Update `forceLogoutAndRedirect` to clear via
   `setAccessToken(null)` instead of `localStorage.removeItem(...)`.
   The cookie clears server-side via the logout endpoint.

### Testing strategy

Unit (vitest):
- `getAccessToken()` / `setAccessToken()` round-trip.
- Request interceptor: when accessor returns null, no `Authorization`
  header is attached; when it returns a string, header is `Bearer ...`.
- `forceLogoutAndRedirect` clears in-memory token and triggers
  navigation.

Integration (pytest, backend):
- Login sets the `refresh_token` cookie with `HttpOnly; Secure;
  SameSite=Strict` attributes.
- Refresh accepts cookie alone (no body) and returns a new access
  token.
- Refresh accepts body alone (legacy path) during the migration window.
- Refresh prefers cookie when both are present.
- Logout clears the cookie.

E2E (manual or Playwright if added later):
- Login → reload page → still authenticated (refresh via cookie).
- Logout → reload page → unauthenticated.
- XSS smoke check: in DevTools, `localStorage.getItem('access_token')`
  returns null after migration.

### Migration window (deploy plan)

1. **Phase 1 — backend deploys first.** Backend accepts refresh token
   from cookie OR body, sets cookie on login alongside JSON body
   response. Old frontend continues to work unchanged (uses body).
2. **Phase 2 — frontend deploys.** New frontend uses
   `withCredentials: true`, in-memory access token, no localStorage
   tokens. Old backend deploys (none after Phase 1) unaffected.
3. **Phase 3 — backend cleanup deploy.** Remove refresh token from
   login JSON body; remove body-source acceptance from refresh
   endpoint. Bump a minor API version note.

The TODO comments in source reference this section; remove them as
each phase ships.

### Why not done in the campaign session

- 12+ localStorage touchpoints across `client.ts` and `authStore.ts`
  plus Zustand `persist` interaction.
- Existing redirect-loop guard, refresh mutex, and rehydration paths
  all need rewriting and dedicated tests.
- Cross-subdomain cookie scope for tenants needs an explicit threat
  model decision (apex domain vs host-only).
- B15 logout-revoke flow assumes body source — needs revisit.
- Backward-compat dual-source window adds further code paths/tests.

---

## Deploy notes — frontend & ops polish

These notes accompany the prep/production-readiness session that
addressed B17 (deferred), B19, B22, B25, B26.

- **B19 (prod build console stripping).** `console.log`,
  `console.debug`, `console.info`, `console.trace` and `debugger`
  statements are stripped from the production frontend bundle via
  `esbuild.pure` / `esbuild.drop` in `frontend/vite.config.ts`.
  `console.warn` and `console.error` are preserved so production-side
  issues remain visible. Devs still see all console output in
  `npm run dev` — the strip is production-mode only.

- **B25 (CORS startup safety).** `backend/app/main.py` now refuses to
  start in production if BOTH `ALLOWED_ORIGINS` is empty AND
  `CORS_WILDCARD_DOMAINS` is empty (would silently block every browser
  request). Production deploys must set at least one. The resolved
  CORS configuration is logged at startup under the structured
  identifier `cors.config_resolved` (exact origins, regex pattern,
  wildcard-enabled flag, environment, resolved_at). Operators can
  grep for `cors.config_resolved` in startup logs to verify.

- **B22 (branding input validation).** Invalid favicon URLs (non-https
  / non-image-extension / `data:` / `javascript:` etc.) and invalid
  color strings (anything other than `#RRGGBB` or `#RRGGBBAA`) are
  silently rejected to defaults with a `console.warn` from
  `[branding]`. If a tenant reports their custom branding isn't
  appearing, check the browser console for a `[branding]` warning.
  The favicon `<link>` node is now reused across calls — repeated
  `applyBrandingToDocument` no longer leaks DOM nodes.

- **B26 (TODO label).** The placeholder
  `"Close (TODO: Open Staff Wizard)"` button label in the account
  requests prefill modal is now `"Close"`. The TODO note was relocated
  to a JSX comment immediately above the button in
  `frontend/src/pages/AccountRequestsPage.tsx`.

- **B17 (token storage — deferred).** See the "B17 token storage
  migration plan" section above. Source-level TODO comments tagged
  `TODO(B17, XSS-risk):` were added at every `localStorage` token
  access in `frontend/src/api/client.ts` and
  `frontend/src/stores/authStore.ts` so the next engineer can find
  every site to migrate. Commit message marks B17 as
  "deferred to post-launch".


---

## Prompt 8 — Pre-launch verification sweep (2026-01-…)

Findings from the seven-task verification pass on commit `752cba5` (branch
`prep/production-readiness`). All findings are **report-only**; no fix code
was written this session except the trivial alembic idempotency commit.
CI green at the time of the sweep.

### A. Launch blockers

(items that, in the auditor's judgment, should be addressed before opening
the door to paying customers — not items that block launch tonight)

- **A1 — `backend/create_superadmin.py` hardcodes credentials.**
  Lines 12-13 ship `email="shae@shaemarcus.com"`, `password="admin123"`.
  `admin123` is on the `INSECURE_PASSWORDS` denylist in
  `backend/app/config.py:42` — but the validator is bypassed because the
  script never reads `FIRST_SUPER_ADMIN_PASSWORD`. The password validator
  in `config.py:195-202` only fires for the env var path. Sets
  `is_active=True` unconditionally. Fix: rewrite the script to read the
  two env vars and fail with a clear message if either is unset; remove the
  hardcoded fallback.
- **A2 — Backend port published on the host in `docker-compose.prod.yml`.**
  Backend service uses `ports: - "8080:8080"`, exposing the API directly
  on the Lightsail public interface and bypassing nginx (and therefore
  bypassing the security headers, the rate limit at the edge, and the
  `X-Forwarded-For` chain that the new `TRUSTED_PROXIES` (B16) check
  depends on). Fix: change to `expose: ["8080"]` so only the
  `timetracker-network` peers (nginx) can reach it.
- **A3 — Uvicorn started without `--proxy-headers` /
  `--forwarded-allow-ips`.** `backend/Dockerfile:47` and
  `backend/Dockerfile.prod` both run uvicorn with no proxy-aware flags.
  Result: even if A2 is fixed and `TRUSTED_PROXIES` is set, FastAPI's
  `request.client.host` is the docker-network peer IP and the
  `X-Forwarded-For` header is silently ignored by Starlette's
  `ProxyHeadersMiddleware` (because that middleware is never installed).
  `get_client_ip` will work, but anything reading `request.client`
  directly (audit logs, lockout key) will see the proxy IP. Fix: add
  `--proxy-headers --forwarded-allow-ips=*` to the CMD (the trust check
  already lives in app code).
- **A4 — HSTS commented out in nginx, port 80 only.**
  `frontend/nginx.conf:35` has the HSTS header disabled. The container
  listens on port 80 only — TLS termination is assumed to be upstream
  (Lightsail load balancer / Cloudflare). If the upstream is misconfigured
  (or absent on a future deploy), the app will serve traffic over plain
  HTTP without complaint. Fix on launch day: confirm Lightsail TLS is on
  and uncomment the HSTS header (1-year, `includeSubDomains`,
  `preload`).

### B. Pre-launch fixes (not strictly blocking, but small and high-value)

- **B-fix-1 — `aioredis==2.0.1` in `backend/requirements.txt:21`.**
  Zero `import aioredis` / `from aioredis` lines anywhere in the
  codebase (the Redis client in use is `redis.asyncio`). Dead dep —
  delete the line. Reduces image size and dependency surface.
- **B-fix-2 — `python-multipart` 0.0.22 → 0.0.26.** Single CVE
  (CVE-2026-40347), in the request path (FastAPI form / file uploads).
  Patch-version bump.
- **B-fix-3 — `npm audit fix` on the frontend.** Resolves
  axios <=1.14.0 (moderate, SSRF — GHSA-3p68-rc4w-qgx5,
  GHSA-fvcv-3m26-pcqx), follow-redirects (moderate, GHSA-r4q5-vmmm-2653),
  and lodash <=4.17.23 (HIGH, prototype pollution —
  GHSA-r5fr-rjxr-66jc, GHSA-f23m-r3pf-42rh). All three are flagged as
  `--fix` clean. Run, regenerate `package-lock.json`, ship.

### C. Post-launch (correctness / hygiene, won't bite a smoke test)

- **C1 — Migration round-trip stops at `001 → base`.**
  After commit 752cba5 (3 `if_exists=True` adds), `alembic downgrade`
  unwinds 20 of 21 migrations cleanly. The final step `001 → base`
  fails on `DROP TABLE users` because later migrations created FKs that
  reference `users.id` and their own downgrade does not drop the FK
  before unwinding the column. Production deploys are forward-only, so
  this only bites a hypothetical full DR rebuild from migration 001
  upward. Resolution requires a dedicated session: walk every migration
  with a foreign key into a 001-era table and add the matching
  `op.drop_constraint` to its `downgrade()`. Out of scope for launch.
- **C2 — Payroll overtime threshold is per-PERIOD, not per-WEEK.**
  `backend/app/services/payroll_service.py:412-413, 567-568`.
  `overtime_threshold = Decimal("40") * weeks_in_period` then
  `regular_hours = min(total_hours, overtime_threshold)`. For a
  bi-weekly period this means the 41st hour of week 1 is paid at regular
  rate as long as total hours over both weeks stay under 80. FLSA and
  most US state wage laws define overtime per workweek. Same defect for
  semi-monthly and monthly. **Wage-compliance risk if customers in the
  US run this service for non-exempt hourly employees.** Fix: bucket
  `time_entries` by ISO week (in the company timezone — `company_tz`
  is now available via the 4a sweep) and apply the 40-hour threshold per
  bucket, then sum.
- **C3 — Payroll period boundary uses naive UTC midnight.**
  `backend/app/services/payroll_service.py:472-473`:
  `TimeEntry.start_time >= datetime.combine(period.start_date, datetime.min.time())`
  /  `... datetime.max.time()`. The `.combine` calls produce naive
  datetimes that SQLAlchemy compares as UTC. For a company in any zone
  west of UTC, time entries from late evening of the last period day
  (local) are silently dropped from that period and (depending on how
  the next period bounds line up) may be dropped from both periods.
  Mirrors the bug class that 4a fixed in `time_entries.py` and
  `reports.py` — apply `app.utils.timewindow.range_bounds` here.
- **C4 — Payroll uses `2.17` and `4.33` weeks-per-period.**
  `payroll_service.py:409-410`. These are coarse averages that compound
  with C2: even if you fix C2, a "monthly" period spans 4–5 ISO weeks
  depending on alignment, not 4.33. Once C2 is fixed (per-week buckets),
  these constants become unused and should be deleted.
- **C5 — Payroll has no withholding / tax / net-amount logic.**
  `payroll_service.py` computes `gross_amount` only. Acceptable if
  the resale customer hands the gross numbers off to an external payroll
  provider; not acceptable if marketed as a turnkey US payroll system.
  Document this in the resale collateral so a customer doesn't assume
  net pay is computed.
- **C6 — No `force_password_change` on first super-admin login.**
  Despite earlier audit recommending one, the column / flag does not
  exist anywhere in the codebase. After A1 is addressed, add a
  `password_changed_at` column and a login-time check that 302s to
  `/account/change-password` if the value is null or older than the
  configured rotation window. Pairs with C7.
- **C7 — Password validator is denylist-only.**
  `config.py:195-202` only rejects 8 hardcoded common passwords. No
  length, complexity, entropy, or user-attribute-similarity check. Add
  `MIN_PASSWORD_LENGTH = 12` and a basic complexity rule (mixed case
  + digit) at the same boundary, plus apply the same check to the
  registration / change-password endpoints (not just the bootstrap env
  var).
- **C8 — `ENVIRONMENT=production` does not require a non-empty
  `FIRST_SUPER_ADMIN_PASSWORD`.** The validator early-returns on
  empty / falsy `v`, so `FIRST_SUPER_ADMIN_PASSWORD=""` passes in
  production. Acceptable IF the bootstrap script (A1) becomes the sole
  super-admin path and itself requires the env. Worth adding a belt-
  and-suspenders check here regardless.

### D. Dependency bumps to schedule (test-required)

- `starlette` 0.46.2 → 0.49.1 — two CVEs (CVE-2025-54121,
  CVE-2025-62727), both in the request path. FastAPI may pin a narrower
  range; bump in a dedicated session with full CI run.
- `pytest` 7.4.3 → 9.0.3 — CVE-2025-71176, dev / CI only. Major bump,
  expect plugin compatibility surprises.
- `black` 24.8.0 → 26.3.1 — CVE-2026-32274, dev only. Major bump,
  reformatting churn expected.
- `python-jose` 3.5.0 — no CVE flagged in this version, but the
  package is poorly maintained relative to `PyJWT`. Migrate in a
  later hardening session.

### E. Infra config corrections (Lightsail deploy day)

- Set `TRUSTED_PROXIES` to the docker network CIDR for the compose
  bridge (run `docker network inspect timetracker-network` to read
  the actual CIDR — typically `172.x.0.0/16`). Empty / unset will log
  `auth.no_trusted_proxies` and fall back to peer IP, which after
  fixing A2/A3 will be the nginx container — close enough for
  per-IP-rate-limiting purposes but defeats the X-Forwarded-For chain.
- Confirm Lightsail TLS termination is on. After confirming, address A4
  (uncomment HSTS).
- Set non-empty `SECRET_KEY`, `API_KEY_ENCRYPTION_KEY`,
  `FIRST_SUPER_ADMIN_EMAIL`, `FIRST_SUPER_ADMIN_PASSWORD` (the last
  two only if A1 is done and the bootstrap script reads them).

### F. Verification tasks not completed this session

- **Playwright e2e (Task 5).** Aborted on environmental grounds (one of
  the explicitly-listed abort reasons in the prompt). Browser binaries
  not installed (`Executable doesn't exist at .../chrome-headless-shell.exe`);
  `e2e/.env` not created (only `.env.example` ships); seed data not
  populated; Redis unreachable from the Windows host. Multiple stacked
  blockers — running `npx playwright install` plus `npm run
  seed:demo` plus a Linux-side Redis would have exceeded the 15-min
  environmental-fix budget. **CI does not run Playwright** (only vitest
  + tsc + eslint), so there is no green reference baseline. Schedule a
  dedicated e2e bring-up session post-launch on a Linux host.

### Verdict

**LAUNCH READY WITH CONDITIONS.** The four A-items are short-lived
(~1 day combined) and should be fixed before the first paying tenant
touches the system; none of them require a refactor. The C-items are
real defects but won't bite a smoke test, and C2/C3 only matter for US
hourly-payroll customers — segment customers accordingly until those
land. Dependency CVEs (B-fix-2, B-fix-3) are clean `--fix` operations
and should ship with the A-items.

