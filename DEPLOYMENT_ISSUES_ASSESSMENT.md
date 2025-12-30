# TimeTracker Deployment Issues Assessment
## December 30, 2025

This document provides a comprehensive analysis of deployment issues encountered and their root causes.

---

## Executive Summary

Multiple interconnected configuration issues caused deployment failures. The primary root cause was **inconsistent naming conventions** between different configuration files and deployment methods.

---

## Issue Categories

### 1. TrustedHostMiddleware Blocking Requests (400 Bad Request)

**Symptom:**
```
INFO: 127.0.0.1:60332 - "GET /health HTTP/1.1" 400 Bad Request
```

**Root Cause:**
FastAPI's `TrustedHostMiddleware` rejects requests where the `Host` header doesn't match the `ALLOWED_HOSTS` configuration.

**Affected Components:**
- Docker health checks (internal)
- Nginx proxy requests (internal Docker network)
- External API requests

**Why It Happened:**
1. Health checks used `urllib.request.urlopen()` which doesn't set an explicit Host header
2. Nginx proxied requests with `Host: timetracker-backend` but that wasn't in ALLOWED_HOSTS
3. ALLOWED_HOSTS had `time-tracker-backend` (with extra hyphen) instead of actual container name

**Files Involved:**
- `backend/Dockerfile` - Health check command
- `docker-compose.prod.yml` - ALLOWED_HOSTS environment variable
- `backend/app/main.py` - TrustedHostMiddleware configuration
- `~/timetracker/.env` - Server environment overrides

**Solution Applied:**
```dockerfile
# Before (Dockerfile)
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# After
HEALTHCHECK CMD curl -f -H "Host: localhost" http://127.0.0.1:8080/health
```

```yaml
# docker-compose.prod.yml ALLOWED_HOSTS
ALLOWED_HOSTS: ["timetracker.shaemarcus.com","localhost","127.0.0.1","timetracker-backend","backend"]
```

---

### 2. Container Naming Inconsistencies

**Symptom:**
```
nginx: [emerg] host not found in upstream "time-tracker-backend" in /etc/nginx/conf.d/default.conf:55
```

**Root Cause:**
Multiple configuration files referenced different container names:

| File | Name Used | Actual Container |
|------|-----------|------------------|
| `nginx.conf` | `time-tracker-backend` | ❌ Wrong |
| `docker-compose.prod.yml` | `timetracker-backend` | ✅ Correct |
| `backend/.env` | `time-tracker-postgres` | ❌ Wrong (for this compose) |
| `deploy.sh` (original) | `time-tracker-backend` | Different deployment |

**Why It Happened:**
Two different deployment methods existed with different naming conventions:
1. **Original**: `deploy.sh` using GHCR images with `time-tracker-*` naming
2. **New**: `docker-compose.prod.yml` with `timetracker-*` naming

**Solution Applied:**
```nginx
# nginx.conf - Fixed upstream names
location /api {
    proxy_pass http://timetracker-backend:8080;  # Was: time-tracker-backend
}
```

---

### 3. Database Credential Mismatches

**Symptom:**
```
psql: error: FATAL: role "timetracker" does not exist
```

**Root Cause:**
The PostgreSQL volume `timetracker_postgres_data` was created with user `postgres`, but `docker-compose.prod.yml` defaults to user `timetracker`.

**Configuration Conflict:**

| Source | DB_USER | DB_PASSWORD |
|--------|---------|-------------|
| docker-compose.prod.yml default | `timetracker` | `timetracker_secure_password` |
| Existing volume data | `postgres` | `postgres` |
| backend/.env | `postgres` | `postgres` |

**Solution Applied:**
Created `~/timetracker/.env` on server:
```bash
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=time_tracker
```

---

### 4. Deployment Architecture Confusion

**Root Cause:**
Two completely different deployment architectures existed:

#### Original Deployment (`deploy.sh`)
```bash
docker pull ghcr.io/caxulex/timetracker-backend:latest
docker run -d --name time-tracker-backend \
  --network timetracker_time-tracker-network \
  -p 8080:8080 \
  --env-file ~/timetracker/backend/.env \
  ghcr.io/caxulex/timetracker-backend:latest
```
- Used **pre-built images** from GitHub Container Registry
- Container names: `time-tracker-backend`, `time-tracker-frontend`
- Network: `timetracker_time-tracker-network`
- Database host in .env: `time-tracker-postgres`

#### New Deployment (`docker-compose.prod.yml`)
```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: timetracker-backend
```
- **Builds images locally** from source
- Container names: `timetracker-backend`, `timetracker-frontend`
- Network: `timetracker_timetracker-network`
- Database host: `postgres` (compose service name)

**Impact:**
- Different container names broke nginx proxy
- Different network names caused isolation
- Database connection strings were incompatible
- User confusion about which deployment method to use

---

### 5. Frontend Infinite Refresh Loop (Original Bug)

**Symptom:**
Dashboard refreshes continuously when auth session expires, preventing user interaction.

**Root Cause:**
State synchronization issue between:
1. Zustand store (`isAuthenticated: true` persisted in localStorage)
2. Actual token state (tokens cleared from localStorage)

**Attack Vector:**
1. User's token expires or is cleared
2. API returns 401 Unauthorized
3. Interceptor clears tokens from localStorage
4. Zustand store still has `isAuthenticated: true` (persisted separately)
5. `ProtectedRoute` sees `isAuthenticated: true`, allows access
6. Dashboard tries to fetch data, gets 401
7. Interceptor redirects to login
8. Loop: Login page sees `isAuthenticated: true`, redirects to dashboard

**Solution Applied:**
- Added dual validation: check both `isAuthenticated` AND `localStorage.getItem('access_token')`
- Added redirect loop detection with circuit breaker
- Added `onRehydrateStorage` validation in Zustand

---

## Prevention Checklist

### Naming Conventions
- [ ] Use consistent naming across ALL files (pick ONE: hyphens OR no hyphens)
- [ ] Document the canonical container names in README
- [ ] Use compose service names (`backend`, `postgres`) instead of container names where possible

### TrustedHostMiddleware
- [ ] Always include `localhost`, `127.0.0.1` in ALLOWED_HOSTS
- [ ] Include Docker service names used in nginx proxy
- [ ] Use explicit Host headers in health checks

### Database Configuration
- [ ] Document the database credentials in deployment guide
- [ ] Use environment variables consistently
- [ ] Check existing volume credentials before deploying

### Deployment Method
- [ ] Choose ONE deployment method and document it
- [ ] Remove or clearly deprecate alternative methods
- [ ] Update CI/CD to match chosen method

---

## Recommended Configuration Standards

### docker-compose.prod.yml Service Names
```yaml
services:
  postgres:      # Database
  redis:         # Cache
  backend:       # API server
  frontend:      # Web UI
```

### nginx.conf Upstream References
```nginx
# Use compose service names (most portable)
proxy_pass http://backend:8080;

# OR use explicit container names (if needed)
proxy_pass http://timetracker-backend:8080;
```

### ALLOWED_HOSTS (Complete List)
```python
ALLOWED_HOSTS = [
    "timetracker.shaemarcus.com",  # Production domain
    "localhost",                     # Local development
    "127.0.0.1",                    # Local development
    "backend",                       # Docker compose service name
    "timetracker-backend",          # Docker container name
]
```

### Environment Variable Priority
1. `~/timetracker/.env` (server-specific overrides)
2. `docker-compose.prod.yml` defaults
3. `backend/.env` (development defaults - NOT used in compose)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Internet                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTPS (443)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Caddy (Reverse Proxy)                     │
│                    Port 80, 443                              │
│                    Host: timetracker.shaemarcus.com          │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP (3000)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Docker Network: timetracker_timetracker-network │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         timetracker-frontend (nginx)                  │   │
│  │         Port 80 (internal) → 3000 (host)             │   │
│  │                                                       │   │
│  │   /api/* ──► proxy_pass http://backend:8080          │   │
│  │   /*     ──► serve static React files                │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│  ┌──────────────────────▼───────────────────────────────┐   │
│  │         timetracker-backend (FastAPI/Uvicorn)         │   │
│  │         Port 8080 (internal only)                     │   │
│  │                                                       │   │
│  │   ALLOWED_HOSTS must include:                        │   │
│  │   - timetracker.shaemarcus.com (external)            │   │
│  │   - localhost, 127.0.0.1 (health checks)             │   │
│  │   - backend, timetracker-backend (nginx proxy)       │   │
│  └───────────┬─────────────────────┬────────────────────┘   │
│              │                     │                         │
│  ┌───────────▼─────────┐ ┌────────▼────────────────────┐   │
│  │  timetracker-db     │ │  timetracker-redis          │   │
│  │  PostgreSQL 15      │ │  Redis 7                    │   │
│  │  Port 5432          │ │  Port 6379                  │   │
│  │  User: postgres     │ │                             │   │
│  └─────────────────────┘ └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Files Changed During This Session

| File | Change |
|------|--------|
| `frontend/src/api/client.ts` | Added redirect loop detection, forceLogoutAndRedirect() |
| `frontend/src/App.tsx` | Added dual validation in route guards |
| `frontend/src/stores/authStore.ts` | Added onRehydrateStorage validation |
| `backend/Dockerfile` | Added curl, fixed health check command |
| `docker-compose.prod.yml` | Fixed ALLOWED_HOSTS, port configuration |
| `frontend/nginx.conf` | Fixed upstream container name |
| `~/timetracker/.env` (server) | Created with correct DB credentials |

---

## Commits

1. `9d89f24` - Fix infinite dashboard refresh loop on auth expiration
2. `da45504` - Add localhost to ALLOWED_HOSTS for health checks  
3. `391583d` - Fix frontend port conflict with Caddy
4. `ce2591d` - Fix health check to use curl with Host header
5. `c75d5df` - Fix nginx upstream to use correct container name
6. `9a89eb4` - Add timetracker-backend to ALLOWED_HOSTS for internal networking

---

## Lessons Learned

1. **Naming matters**: A single hyphen difference (`time-tracker` vs `timetracker`) caused cascading failures
2. **Test internal networking**: Always verify containers can communicate within Docker network
3. **Document deployment method**: Having two methods caused confusion
4. **TrustedHostMiddleware is strict**: Every possible Host header must be whitelisted
5. **Check existing data**: Database volumes retain credentials from initial creation
6. **Health checks need proper headers**: Internal health checks must pass middleware validation
