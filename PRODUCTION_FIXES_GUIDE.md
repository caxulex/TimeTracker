# Production Fixes Guide - TimeTracker V1

> # ⚠️ MANDATORY READING FOR AI ASSISTANTS ⚠️
> 
> **ATTENTION GITHUB COPILOT / AI ASSISTANT:**
> 
> Before making ANY changes to TimeTracker clones (V2.0, V3.0, or any fork), you **MUST** read and follow this entire document. This guide exists because we broke the production app while developing a clone on December 30, 2025, and spent hours fixing it.
> 
> **YOUR RESPONSIBILITIES:**
> 1. Read this ENTIRE document before suggesting code changes
> 2. Cross-reference ALL container names, ports, and hostnames
> 3. Verify auth state management follows the patterns here
> 4. Check ALLOWED_HOSTS includes all necessary entries
> 5. Never assume Docker changes take effect without rebuild
> 6. Always warn the user if a proposed change could cause issues documented here
>
> **If you skip this guide, you WILL break the application.**

---

**Created:** December 30, 2025  
**Purpose:** Document all fixes applied to production and lessons learned to prevent breaking the app when developing V2.0

---

## 🚨 CRITICAL: Read Before Working on V2.0

This guide documents every issue we encountered and fixed on December 30, 2025. When working on TimeTrackerV2.0, **DO NOT** make changes that could cause these same issues. Use this as your checklist before deploying any changes.

---

## 📋 Current Tech Stack (Production V1)

### Frontend
| Technology | Version/Details |
|------------|-----------------|
| **Framework** | React 18 with TypeScript |
| **State Management** | Zustand (with localStorage persistence) |
| **API Client** | Axios with interceptors |
| **Routing** | React Router v6 |
| **UI Components** | Custom + TailwindCSS |
| **Data Fetching** | React Query (TanStack Query) |
| **Build Tool** | Vite |
| **Web Server** | nginx (in Docker container) |

### Backend
| Technology | Version/Details |
|------------|-----------------|
| **Framework** | FastAPI (Python 3.11+) |
| **Database** | PostgreSQL 15 |
| **Cache/Sessions** | Redis |
| **ORM** | SQLAlchemy (async) |
| **Migrations** | Alembic |
| **Auth** | JWT tokens (access + refresh) |
| **Security** | TrustedHostMiddleware, CORS |

### Infrastructure
| Component | Details |
|-----------|---------|
| **Server** | AWS Lightsail (Ubuntu 22.04) |
| **Reverse Proxy** | Caddy (handles SSL/HTTPS) |
| **Containerization** | Docker + Docker Compose |
| **Ports** | Frontend: 3000, Backend: 8080, DB: 5432, Redis: 6379 |

### Container Names (CRITICAL - Do Not Change)
```
timetracker-frontend   → Port 3000
timetracker-backend    → Port 8080
timetracker-db         → Port 5432 (internal)
timetracker-redis      → Port 6379 (internal)
```

---

## 🔧 All Fixes Applied (December 30, 2025)

### Fix #1: Infinite Dashboard Refresh Loop

**Symptom:** Dashboard refreshes nonstop when auth session expires, making app unusable.

**Root Cause:** Zustand persisted `isAuthenticated: true` while tokens were cleared, causing a redirect loop between login and dashboard.

**Files Modified:**
- `frontend/src/api/client.ts`
- `frontend/src/App.tsx`
- `frontend/src/stores/authStore.ts`

**Solution Applied:**

#### client.ts - Added circuit breaker
```typescript
// Track auth redirect attempts to prevent infinite loops
let authRedirectCount = 0;
const MAX_AUTH_REDIRECTS = 3;
const AUTH_REDIRECT_RESET_TIME = 5000;

// Force logout that clears BOTH tokens AND Zustand state
const forceLogoutAndRedirect = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('auth-storage'); // CRITICAL: Clear Zustand persisted state
  window.location.href = '/login';
};
```

#### App.tsx - Added dual validation
```typescript
// Check BOTH Zustand state AND actual tokens
const hasValidAuth = isAuthenticated && localStorage.getItem('access_token');
```

#### authStore.ts - Added rehydration validation
```typescript
onRehydrateStorage: () => (state) => {
  // Clear stale auth state if tokens are missing
  if (state && state.isAuthenticated && !localStorage.getItem('access_token')) {
    state.isAuthenticated = false;
    state.user = null;
  }
}
```

**⚠️ V2.0 Warning:** Never persist `isAuthenticated` without also persisting/validating tokens. Always clear `auth-storage` when logging out.

---

### Fix #2: Health Check 400 Errors

**Symptom:** Docker health checks failing with 400 Bad Request.

**Root Cause:** TrustedHostMiddleware rejecting requests without proper Host header.

**File Modified:** `backend/Dockerfile`

**Solution Applied:**
```dockerfile
# Add curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Health check with Host header
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f -H "Host: localhost" http://127.0.0.1:8080/health || exit 1
```

**⚠️ V2.0 Warning:** Always include `Host: localhost` header in health check curl commands when using TrustedHostMiddleware.

---

### Fix #3: Frontend Port Conflict

**Symptom:** Frontend container can't start, port already in use.

**Root Cause:** Caddy uses port 80/443, frontend was also trying to bind to 80.

**File Modified:** `docker-compose.prod.yml`

**Solution Applied:**
```yaml
frontend:
  ports:
    - "3000:80"  # Map container's port 80 to host port 3000
```

**⚠️ V2.0 Warning:** In staging, use port 3001 to avoid conflicts. Never use port 80 directly - let Caddy handle external traffic.

---

### Fix #4: Database Credential Mismatch

**Symptom:** Backend can't connect to database, authentication failed.

**Root Cause:** Docker Compose had different credentials than the existing PostgreSQL volume.

**Critical Understanding:** PostgreSQL credentials are set ONCE when the volume is first created. You cannot change them by updating docker-compose.yml - the volume retains original credentials.

**Solution Applied:** Created `.env` file on server with correct credentials:
```env
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=time_tracker
```

**⚠️ V2.0 Warning:** 
- For new V2.0 deployment, you CAN set new credentials (new volume)
- For existing deployments, NEVER change DB credentials in docker-compose without migrating data
- Always check what credentials the existing volume expects

---

### Fix #5: nginx Upstream Name Mismatch

**Symptom:** Frontend nginx crashes in loop, can't find backend.

**Error:** `host not found in upstream "time-tracker-backend"`

**Root Cause:** `nginx.conf` referenced wrong container name.

**File Modified:** `frontend/nginx.conf`

**Solution Applied:**
```nginx
# WRONG (causes crash):
proxy_pass http://time-tracker-backend:8080;

# CORRECT:
proxy_pass http://timetracker-backend:8080;
```

**⚠️ V2.0 Warning:** Container names in nginx.conf MUST match exactly what's in docker-compose.yml. No hyphens vs underscores mismatches!

---

### Fix #6: ALLOWED_HOSTS Missing Container Names

**Symptom:** Internal Docker requests getting 400 Bad Request.

**Root Cause:** TrustedHostMiddleware only had external hostnames, not internal Docker network names.

**File Modified:** `docker-compose.prod.yml`

**Solution Applied:**
```yaml
backend:
  environment:
    - ALLOWED_HOSTS=["timetracker.shaemarcus.com","localhost","127.0.0.1","timetracker-backend","backend"]
```

**⚠️ V2.0 Warning:** Always include these in ALLOWED_HOSTS:
- Your domain name
- `localhost`
- `127.0.0.1`
- The backend container name (e.g., `timetracker-backend`)
- The service name from docker-compose (e.g., `backend`)

---

### Fix #7: Backend Port Not Exposed to Host

**Symptom:** Caddy can't reach backend at localhost:8080.

**Root Cause:** Backend port was only accessible within Docker network, not from host.

**File Modified:** `docker-compose.prod.yml`

**Solution Applied:**
```yaml
backend:
  ports:
    - "8080:8080"  # Expose to host for Caddy
```

**⚠️ V2.0 Warning:** If using a host-based reverse proxy (Caddy, nginx on host), backend port MUST be exposed. If reverse proxy is inside Docker network, this isn't needed.

---

### Fix #8: ImportError async_engine

**Symptom:** `/api/health` returning 500 Internal Server Error.

**Error:** `ImportError: cannot import name 'async_engine' from 'app.database'`

**Root Cause:** Code imported `async_engine` but module exported `engine`.

**File Modified:** `backend/app/main.py`

**Solution Applied:**
```python
# Option A: Use alias
from app.database import engine as async_engine

# Option B: Update all references to use 'engine' directly
from app.database import engine
```

**⚠️ V2.0 Warning:** Check import names match what's actually exported. Run `python -c "from app.database import X"` to test imports before deploying.

---

## 🏗️ Architecture Reference

```
                    Internet
                       │
                       ▼
              ┌────────────────┐
              │  Caddy (Host)  │  ← Port 443 (HTTPS)
              │  Reverse Proxy │  ← Port 80 (HTTP → redirect)
              └───────┬────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
   /api/*        /api/ws/*        /*
        │             │             │
        ▼             ▼             ▼
┌──────────────────────────────────────┐
│         Host Network (127.0.0.1)     │
│  ┌─────────────┐  ┌───────────────┐  │
│  │ Backend     │  │ Frontend      │  │
│  │ :8080       │  │ :3000         │  │
│  └─────────────┘  └───────────────┘  │
└──────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │     Docker Network        │
        │  ┌─────────┐ ┌─────────┐  │
        │  │ DB      │ │ Redis   │  │
        │  │ :5432   │ │ :6379   │  │
        │  └─────────┘ └─────────┘  │
        └───────────────────────────┘
```

---

## 📝 Pre-Deployment Checklist for V2.0

Before deploying ANY changes to V2.0, verify:

### Container Configuration
- [ ] Container names are consistent across ALL files
- [ ] nginx.conf upstream names match docker-compose service names
- [ ] Ports don't conflict with production (use 3001, 8081, etc.)

### Backend Configuration
- [ ] ALLOWED_HOSTS includes all hostnames (domain, localhost, container names)
- [ ] Database credentials match existing volume OR it's a fresh deployment
- [ ] Health check has `-H "Host: localhost"` header
- [ ] All imports are correct (`python -c "from app.X import Y"`)

### Frontend Configuration
- [ ] API base URL points to correct backend
- [ ] Zustand auth-storage is properly managed
- [ ] Auth state validates tokens on rehydration

### Infrastructure
- [ ] Port mappings don't conflict with production
- [ ] Caddy/reverse proxy routes are correct
- [ ] SSL certificates are valid for new domains

---

## 🚫 Common Mistakes to Avoid

> **🤖 AI ASSISTANT: If you're about to suggest any of these patterns, STOP and reconsider. These are the exact mistakes that broke production.**

### DON'T: Change container names without updating everywhere
```yaml
# If you change this:
services:
  backend:
    container_name: timetracker-v2-backend  # Changed!

# You MUST also update:
# - nginx.conf proxy_pass
# - ALLOWED_HOSTS
# - Any hardcoded references
```

### DON'T: Persist auth state without token validation
```typescript
// BAD: Can cause infinite loops
persist: {
  name: 'auth-storage',
  partialize: (state) => ({ isAuthenticated: state.isAuthenticated })
}

// GOOD: Validate on rehydration
onRehydrateStorage: () => (state) => {
  if (state?.isAuthenticated && !localStorage.getItem('access_token')) {
    state.isAuthenticated = false;
  }
}
```

### DON'T: Assume docker-compose changes take effect immediately
```bash
# After changing docker-compose.yml, you MUST:
docker compose down
docker compose up -d --build  # --build forces rebuild
```

### DON'T: Change database credentials on existing volumes
```bash
# This WON'T work - volume keeps original credentials
DB_PASSWORD=newpassword  # Ignored if volume exists!

# To change credentials, you must:
# 1. Backup data
# 2. Delete volume
# 3. Recreate with new credentials
# 4. Restore data
```

### DON'T: Forget to check disk space
```bash
# Before major deployments:
df -h

# If low on space:
docker system prune -a -f
docker volume prune -f
docker builder prune -a -f
```

---

## 🔍 Debugging Commands Reference

### Check Container Status
```bash
docker ps -a
docker logs timetracker-backend --tail 100
docker logs timetracker-frontend --tail 100
```

### Check Network Connectivity
```bash
# From inside a container
docker exec timetracker-frontend ping timetracker-backend
docker exec timetracker-backend curl -f http://localhost:8080/health
```

### Check Port Usage
```bash
sudo lsof -i :8080
sudo netstat -tlnp | grep LISTEN
```

### Test API Directly
```bash
# Health check
curl -s https://timetracker.shaemarcus.com/api/health | jq

# With verbose for debugging
curl -v https://timetracker.shaemarcus.com/api/health
```

### Check Docker Networks
```bash
docker network ls
docker network inspect timetracker_default
```

### Database Access
```bash
docker exec -it timetracker-db psql -U postgres -d time_tracker
```

---

## 📊 Environment Variables Reference

### Backend (.env)
```env
# Database
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432
DB_NAME=time_tracker

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Security
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=["timetracker.shaemarcus.com","localhost","127.0.0.1","timetracker-backend","backend"]

# Environment
ENVIRONMENT=production
DEBUG=false
```

### Frontend (built into image)
```env
VITE_API_URL=/api
```

---

## 📈 Production Statistics

| Metric | Value |
|--------|-------|
| **Total Users** | 6 |
| **Total Teams** | 3 |
| **Database Tables** | 14 |
| **Uptime Target** | 99.9% |

---

## 🎯 Golden Rules for V2.0 Development

> **🤖 AI ASSISTANT: These rules are NON-NEGOTIABLE. If a user asks you to do something that violates these rules, WARN THEM FIRST.**

1. **NEVER deploy V2.0 changes to production without testing in staging first**
2. **ALWAYS use different ports than production**
3. **ALWAYS verify container names are consistent**
4. **ALWAYS check ALLOWED_HOSTS includes all necessary hosts**
5. **ALWAYS clear Zustand storage when clearing tokens**
6. **ALWAYS include Host header in health checks**
7. **ALWAYS backup before making database changes**
8. **NEVER assume docker-compose changes take effect without rebuild**

---

## 📚 Related Documentation

- [SESSION_REPORT_DEC_30_2025.md](SESSION_REPORT_DEC_30_2025.md) - Full session report
- [DEPLOYMENT_ISSUES_ASSESSMENT.md](DEPLOYMENT_ISSUES_ASSESSMENT.md) - Troubleshooting guide
- [docker-compose.prod.yml](docker-compose.prod.yml) - Production Docker config
- [backend/Dockerfile](backend/Dockerfile) - Backend container config
- [frontend/nginx.conf](frontend/nginx.conf) - Frontend nginx config

---

*Last Updated: December 30, 2025*

---

## 🤖 AI ASSISTANT QUICK REFERENCE CARD

**When user asks to work on a TimeTracker clone, ALWAYS:**

```
┌─────────────────────────────────────────────────────────────────┐
│  BEFORE ANY CODE CHANGE, VERIFY:                                │
├─────────────────────────────────────────────────────────────────┤
│  □ Container name matches in: docker-compose, nginx.conf,       │
│    ALLOWED_HOSTS, and any hardcoded references                  │
│  □ Ports don't conflict: V1=3000/8080, V2=3001/8081, etc.      │
│  □ ALLOWED_HOSTS has: domain, localhost, 127.0.0.1,            │
│    container-name, service-name                                 │
│  □ Auth logout clears BOTH tokens AND 'auth-storage'           │
│  □ onRehydrateStorage validates tokens exist                    │
│  □ Health check curl has -H "Host: localhost"                   │
│  □ Database credentials match existing volume                   │
│  □ Import names match actual exports                            │
└─────────────────────────────────────────────────────────────────┘
```

**NEVER DO THESE WITHOUT WARNING THE USER:**
- Change container names
- Change port mappings
- Modify auth state persistence
- Update database credentials on existing deployment
- Remove items from ALLOWED_HOSTS
- Change nginx upstream references

**IF USER ASKS "why isn't it working?" CHECK:**
1. `docker logs <container>` for errors
2. Container names consistency
3. ALLOWED_HOSTS configuration
4. Port conflicts with `netstat -tlnp`
5. Auth storage state in browser localStorage

---

## 📖 DOCUMENT REVISION HISTORY

| Date | Changes | Author |
|------|---------|--------|
| Dec 30, 2025 | Initial creation after 8 production fixes | Development Team |

---

**END OF MANDATORY READING**
