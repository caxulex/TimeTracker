# Basecamp Integration (v1)

Per-tenant, OAuth-based, **one-way** mirror of Basecamp 4 projects into
TimeTracker. v1 is intentionally minimal: a super-admin clicks a button to
authorize, and another button to sync — no webhooks, no polling, no
to-dos, and no two-way push.

> Reference: [Basecamp 4 API (`bc3-api`)](https://github.com/basecamp/bc3-api)

---

## What v1 does

| Capability | v1 | Notes |
|---|---|---|
| Per-tenant OAuth (Launchpad)              | ✅ | `type=web_server`, refresh-token rotation supported |
| Encrypted token storage                   | ✅ | AES-256-GCM via `EncryptionService` (`API_KEY_ENCRYPTION_KEY`) |
| Manual project sync (Basecamp → TimeTracker) | ✅ | Idempotent, dry-run capable |
| One Basecamp account per company          | ✅ | UNIQUE on `basecamp_credentials.company_id` |
| Project name / description / status mirror | ✅ | Update on change, no-op when identical |
| Sync to-dos / time entries                | ❌ | v2 |
| Two-way push (TimeTracker → Basecamp)     | ❌ | Out of scope for this feature |
| Webhooks / background scheduler           | ❌ | v2 |
| Frontend admin UI                         | ❌ | v2 — endpoints are exposed and ready |

---

## Setup (super-admin / operator)

### 1. Register a Launchpad integration

1. Go to <https://launchpad.37signals.com/integrations> and create a new
   integration. Pick "Basecamp 4" as the product.
2. Set the **Redirect URI** to **exactly**:

   ```
   https://timetracker.shaemarcus.com/api/integrations/basecamp/callback
   ```

   The redirect URI is whitelisted on Launchpad — it must match the value
   passed to `/authorization/new` byte-for-byte.

3. Copy the **Client ID** and **Client Secret** Launchpad shows you.

### 2. Set environment variables

Add to your `.env` (or compose secrets):

```
BASECAMP_CLIENT_ID=...
BASECAMP_CLIENT_SECRET=...
BASECAMP_REDIRECT_URI=https://timetracker.shaemarcus.com/api/integrations/basecamp/callback
API_KEY_ENCRYPTION_KEY=...   # required to encrypt stored OAuth tokens
```

`docker-compose.prod.yml` and `docker-compose.prod.ghcr.yml` already
forward these into the backend container as bare strings (default empty).

### 3. Apply the migration

```
alembic upgrade head      # creates basecamp_credentials, basecamp_project_mappings
```

### 4. Connect from the API

```http
GET /api/integrations/basecamp/connect
Authorization: Bearer <super-admin JWT>
```

Returns `{"authorization_url": "https://launchpad.37signals.com/authorization/new?...&state=..."}`.
Redirect the user there. After consent, Launchpad sends them to your
configured `BASECAMP_REDIRECT_URI`, which lands on:

```http
GET /api/integrations/basecamp/callback?code=...&state=...
```

The handler verifies the CSRF `state` token (stored in Redis under
`basecamp_oauth_state:<state>` for 10 min), exchanges the code for
access + refresh tokens, encrypts both, and persists them. The user is
then 302-redirected to `/settings/integrations?status=connected`.

---

## OAuth flow

```
┌───────────┐                                     ┌────────────────┐
│  Browser  │                                     │ Launchpad      │
│ (admin)   │                                     │ (37signals)    │
└─────┬─────┘                                     └───────┬────────┘
      │ 1. GET /api/integrations/basecamp/connect          │
      ▼                                                    │
┌──────────────┐  store state token (Redis, 10m)           │
│  TimeTracker │ ─────────────────────────────────────►    │
│  backend     │  302 → launchpad authorization_url        │
└──────┬───────┘                                           │
       │              2. user authorizes ───────────────►  │
       │                                                   │
       │   3. 302 → /api/integrations/basecamp/callback    │
       │       ?code=...&state=...                         │
       ▼                                                   │
┌──────────────┐  4. POST /authorization/token (code)      │
│  TimeTracker │ ─────────────────────────────────────►    │
│  backend     │  ◄───── access_token + refresh_token      │
│              │  5. GET /authorization.json (account info)│
│              │  ◄───── accounts: [{id, name, product}]   │
│              │  6. encrypt + persist BasecampCredentials │
│              │  7. 302 → /settings/integrations          │
└──────────────┘
```

---

## Sync semantics

- **Manual only.** The app does not poll Basecamp or run scheduled syncs.
  A super-admin must `POST /api/integrations/basecamp/sync`.
- **One-way.** Basecamp is the source of truth for v1. TimeTracker never
  writes back.
- **Idempotent.** Each Basecamp project is mapped 1-to-1 via
  `basecamp_project_mappings (company_id, basecamp_account_id, basecamp_project_id)`.
  Re-running sync produces:
  - `created`: a new mapping + matching internal `Project` was made
  - `updated`: an existing mapping had its mirrored project's name/desc/status refreshed
  - `unchanged`: nothing differed
- **Dry-run.** `POST /sync {"dry_run": true}` returns the same report
  shape but writes nothing and does not bump `last_sync_at`.
- **Token freshness.** Before any Basecamp call the service compares
  `expires_at` against `now + 60s` and refreshes via the refresh-token
  flow (`grant_type=refresh_token`) if the access token is within that
  window. The new access token + expiry are persisted.
- **Where projects land.** The Basecamp `Project` model in this app
  requires a non-null `team_id`. The sync picks the lowest-id `Team`
  belonging to the company as the destination team. Companies with no
  team will get an entry in the report's `errors` list. (Future v2 will
  let admins pick a target team.)

---

## API reference

| Method | Path | Role | Purpose |
|---|---|---|---|
| `GET`    | `/api/integrations/basecamp/connect`     | super_admin            | Returns Launchpad authorization URL with CSRF state |
| `GET`    | `/api/integrations/basecamp/callback`    | public (uses state token) | OAuth redirect target; persists encrypted tokens |
| `GET`    | `/api/integrations/basecamp/status`      | admin / super_admin    | `{connected, account_id, account_name, last_sync_at}` |
| `POST`   | `/api/integrations/basecamp/sync`        | super_admin            | Body: `{"dry_run": bool}` → `{created, updated, unchanged, errors, dry_run}` |
| `DELETE` | `/api/integrations/basecamp/disconnect`  | super_admin            | Revokes the Launchpad token and deletes credentials |

---

## v1 limitations

1. Only **projects** are mirrored — to-do lists, to-dos, time entries,
   messages, schedules, and people are not synced.
2. The flow is **manual**: an operator must press Sync. There is no
   webhook subscription and no background scheduler.
3. **One Basecamp account per company.** Re-connecting overwrites the
   existing credential row.
4. Sync operates on the lowest-id `Team` for the company; multi-team
   companies will need v2 to pick a target.
5. `basecampy3` is **not** a dependency. v1 talks directly to Launchpad
   and the BC3 API via `httpx`. The reasons are listed in the project's
   commit log; future versions can revisit.
6. There is **no frontend UI yet** — endpoints are wired and tested but
   the React `/settings/integrations` page is not part of v1.

---

## Troubleshooting

- `503 Basecamp integration not configured`: `BASECAMP_CLIENT_ID` or
  `BASECAMP_CLIENT_SECRET` is empty in the backend container's env.
- `400 Invalid or expired state token`: the OAuth callback came back
  more than 10 min after `/connect`, or hit a different backend
  instance with a different Redis. Re-run `/connect`.
- `Redis unavailable`: state token storage and JWT blacklist both fail.
  The integration cannot complete OAuth without Redis.

---

See [`backend/app/services/basecamp_service.py`](../app/services/basecamp_service.py)
and [`backend/app/routers/integrations/basecamp.py`](../app/routers/integrations/basecamp.py)
for implementation. Tests live in
[`backend/tests/test_basecamp_integration.py`](../tests/test_basecamp_integration.py).
