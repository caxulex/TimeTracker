# API Versioning Plan

## Current State
All API endpoints use the `/api/` prefix (e.g., `/api/auth/login`, `/api/projects`).

## Proposed Change
Add versioned prefix: `/api/v1/` to all routes.

## Status: DEFERRED
This change affects 40+ files across backend, frontend, tests, and documentation.
It should only be implemented when a breaking API change necessitates v2.

## Scope Impact

| Area | Files Affected | Effort |
|------|---------------|--------|
| Backend routers | 1 (main.py) | Low |
| Backend tests | ~20 files | High |
| Frontend API client | ~5 files, 80+ paths | High |
| Frontend tests | ~6 files | Medium |
| Documentation | ~5 files | Low |
| Configuration (nginx, docker) | ~3 files | Low |
| **Total** | **~40 files** | **16-24 hours** |

## Recommended Approach

1. Add an `API_PREFIX` constant to `backend/app/config.py`
2. Use that constant in `main.py` for all `include_router` calls
3. Add backward-compat middleware: requests to `/api/*` redirect to `/api/v1/*`
4. Frontend: create a single `API_PREFIX` constant in `client.ts` and refactor all paths to use it
5. Update all tests
6. Deprecation period: support both `/api/` and `/api/v1/` for 2 releases

## Prerequisites
- All API paths should use a shared constant (currently hardcoded strings)
- Frontend needs a centralized path builder function
- All tests must be updated atomically in the same PR
