# Secret Rotation Guide

Step-by-step procedures for rotating every secret used by TimeTracker. Follow these procedures during scheduled rotations or immediately if a secret is compromised.

---

## Rotation Schedule

| Secret | Rotation Frequency | Risk if Compromised |
|--------|--------------------|---------------------|
| `SECRET_KEY` (JWT signing) | Every 90 days | Full account takeover — attacker can forge tokens |
| `DB_PASSWORD` | Every 180 days | Full data breach — direct database access |
| `API_KEY_ENCRYPTION_KEY` | Every 365 days (or on compromise) | Decryption of stored third-party API keys |
| `REDIS_PASSWORD` | Every 180 days | Session hijacking, cache poisoning |
| `SENTRY_DSN` | On compromise only | Error data leakage to attacker's project |
| `FIRST_SUPER_ADMIN_PASSWORD` | After first login, then every 90 days | Administrative access |

---

## Prerequisites

Before rotating any secret:

1. **Schedule a maintenance window** — some rotations cause brief downtime
2. **Create a database backup:**
   ```bash
   docker compose exec postgres pg_dump -U timetracker time_tracker > backup_$(date +%Y%m%d_%H%M%S).sql
   ```
3. **Verify you can access the server** via SSH and have `docker compose` access
4. **Have the current `.env.production` file** backed up locally

---

## 1. SECRET_KEY (JWT Signing Key)

### Impact
All existing JWT tokens (access + refresh) become invalid immediately. Every active user will be logged out and must re-authenticate.

### Steps

#### 1a. Generate a new key
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```
Save the output — this is your new `SECRET_KEY`.

#### 1b. Blacklist all existing tokens
If Redis is available, existing tokens will fail validation automatically once the key changes. However, for a clean state:
```bash
docker compose exec redis redis-cli FLUSHDB
```

#### 1c. Update the environment file
```bash
nano /path/to/timetracker/.env.production

# Replace the SECRET_KEY line:
SECRET_KEY=<PASTE_NEW_KEY_HERE>
```

#### 1d. Restart backend services
```bash
docker compose restart backend
```

#### 1e. Verify
```bash
# 1. Check backend health
curl -s https://your-domain.com/api/health | jq .

# 2. Verify old tokens are rejected (should return 401)
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer <OLD_TOKEN>" \
  https://your-domain.com/api/users/me

# 3. Verify new login works
curl -s -X POST https://your-domain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@your-domain.com","password":"<YOUR_ADMIN_PASSWORD>"}' | jq .access_token
```

#### 1f. Rollback
If login fails after rotation:
1. Restore the old `SECRET_KEY` in `.env.production`
2. `docker compose restart backend`
3. Investigate the issue in logs: `docker compose logs backend --tail=50`

---

## 2. DB_PASSWORD (PostgreSQL Database Password)

### Impact
Brief downtime while PostgreSQL processes the password change and the backend reconnects.

> **⚠️ CRITICAL:** If using a Docker volume, PostgreSQL credentials are set when the volume is first created. You cannot simply change the environment variable — you must also update PostgreSQL itself.

### Steps

#### 2a. Generate a new password
```bash
openssl rand -base64 32 | tr -d '\n' | tr -dc 'a-zA-Z0-9'
```

#### 2b. Update the password in PostgreSQL
```bash
docker compose exec postgres psql -U timetracker -d time_tracker -c \
  "ALTER USER timetracker WITH PASSWORD '<NEW_PASSWORD>';"
```

#### 2c. Update environment files
```bash
nano /path/to/timetracker/.env.production

# Update these lines:
DB_PASSWORD=<NEW_PASSWORD>
DATABASE_URL=postgresql+asyncpg://timetracker:<NEW_PASSWORD>@postgres:5432/time_tracker
```

Also update `docker-compose.prod.yml` if it has `POSTGRES_PASSWORD`.

#### 2d. Restart backend
```bash
docker compose restart backend
```
Do **not** restart the postgres container — the password was already changed via SQL.

#### 2e. Verify
```bash
# Check health endpoint (includes database connectivity check)
curl -s https://your-domain.com/api/health | jq .

# Verify data is accessible
curl -s -H "Authorization: Bearer <TOKEN>" \
  https://your-domain.com/api/projects | jq '.total'
```

#### 2f. Rollback
If the backend cannot connect:
1. Revert `DATABASE_URL` and `DB_PASSWORD` in `.env.production`
2. `docker compose restart backend`
3. If you already changed PostgreSQL's password, change it back:
   ```bash
   docker compose exec postgres psql -U timetracker -d time_tracker -c \
     "ALTER USER timetracker WITH PASSWORD '<OLD_PASSWORD>';"
   ```

---

## 3. API_KEY_ENCRYPTION_KEY (AES Encryption for Stored API Keys)

### Impact
Existing encrypted API keys in the `api_keys` table will become unreadable. Users must re-enter their third-party API keys (Gemini, OpenAI, etc.) after rotation.

### Steps

#### 3a. Generate a new key
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### 3b. Decide on migration strategy

**Option A — Invalidate and require re-entry (simpler, recommended):**
```bash
docker compose exec postgres psql -U timetracker -d time_tracker -c \
  "UPDATE api_keys SET is_active = false;"
```

**Option B — Re-encrypt existing keys (complex):**
This requires a custom migration script that decrypts all keys with the old key and re-encrypts with the new one. Only attempt if you have many API keys and cannot ask users to re-enter.

#### 3c. Update environment
```bash
nano /path/to/timetracker/.env.production
# Update:
API_KEY_ENCRYPTION_KEY=<NEW_KEY>
```

#### 3d. Restart and verify
```bash
docker compose restart backend

# Verify health
curl -s https://your-domain.com/api/health | jq .

# Notify users to re-enter their API keys via Settings → API Keys
```

#### 3e. Rollback
Restore the old `API_KEY_ENCRYPTION_KEY` and reactivate keys:
```bash
docker compose exec postgres psql -U timetracker -d time_tracker -c \
  "UPDATE api_keys SET is_active = true;"
docker compose restart backend
```

---

## 4. REDIS_PASSWORD

### Impact
Brief disconnection of session/cache layer. Running timers are unaffected (stored in PostgreSQL), but rate-limiting counters and token blacklist entries reset.

### Steps

#### 4a. Generate a new password
```bash
openssl rand -base64 32 | tr -dc 'a-zA-Z0-9'
```

#### 4b. Update Redis configuration
```bash
docker compose exec redis redis-cli CONFIG SET requirepass "<NEW_PASSWORD>"
```

#### 4c. Update environment
```bash
nano /path/to/timetracker/.env.production
# Update:
REDIS_URL=redis://:<NEW_PASSWORD>@redis:6379/0
```

Also update `docker-compose.prod.yml` if Redis password is configured there.

#### 4d. Restart backend
```bash
docker compose restart backend
```

#### 4e. Verify
```bash
# Health check includes Redis connectivity
curl -s https://your-domain.com/api/health | jq .

# Test Redis directly
docker compose exec redis redis-cli -a "<NEW_PASSWORD>" PING
# Should respond: PONG
```

#### 4f. Rollback
Restore old `REDIS_URL` and reset Redis password:
```bash
docker compose exec redis redis-cli -a "<NEW_PASSWORD>" CONFIG SET requirepass "<OLD_PASSWORD>"
docker compose restart backend
```

---

## 5. SENTRY_DSN

### Impact
Zero downtime. Error reporting pauses briefly during restart.

### Steps

#### 5a. Revoke old DSN
1. Log into [sentry.io](https://sentry.io) (or your self-hosted Sentry)
2. Go to **Project Settings → Client Keys (DSN)**
3. Click **Revoke** on the compromised key
4. **Create a new key** and copy the new DSN

#### 5b. Update environment
```bash
nano /path/to/timetracker/.env.production
# Update:
SENTRY_DSN=<NEW_DSN>
```

#### 5c. Restart and verify
```bash
docker compose restart backend

# Check Sentry dashboard for incoming events from your application
```

#### 5d. Rollback
If the new DSN is invalid, remove or revert it:
```bash
# Remove Sentry entirely (errors will be logged locally)
# SENTRY_DSN=
docker compose restart backend
```

---

## Emergency Rotation Checklist

If you suspect a secret has been compromised, follow this priority order:

1. **SECRET_KEY** — Rotate immediately (prevents forged tokens)
2. **DB_PASSWORD** — Rotate immediately (prevents data exfiltration)
3. **API_KEY_ENCRYPTION_KEY** — Rotate and invalidate stored keys
4. **REDIS_PASSWORD** — Rotate to prevent session tampering
5. **Review audit logs** — Check Admin → Audit Logs for suspicious activity
6. **Notify affected users** — Instruct them to change passwords
7. **Document the incident** — Record timeline, impact, and remediation steps

---

## Generating Secure Secrets — Quick Reference

```bash
# JWT Secret Key (64 bytes, URL-safe)
python -c "import secrets; print(secrets.token_urlsafe(64))"

# AES-256 Encryption Key (32 bytes, URL-safe)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Database / Redis Password (32 alphanumeric characters)
openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32
```
