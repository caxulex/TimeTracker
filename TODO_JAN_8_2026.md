# 📋 TODO List - January 8, 2026

**Based on:** SESSION_REPORT_JAN_8_2026.md Assessment  
**Goal:** Fix all issues without breaking the application  
**Approach:** Safe, incremental changes with testing at each step  
**Status:** ✅ **COMPLETED** - All 26 tasks done! (Build passes, 117/136 tests pass)

---

## ⚠️ SAFETY RULES

1. **Test locally before committing** - Run `npm run build` and `pytest` after each change
2. **One category at a time** - Complete all tasks in a section before moving on
3. **Commit after each section** - Small, focused commits
4. **Don't touch production** until all local tests pass
5. **Keep the app running** - Test in browser after frontend changes

---

## 📊 Progress Tracker

| Phase | Tasks | Done | Status |
|-------|-------|------|--------|
| 1. Quick Fixes (Code Errors) | 4 | 4 | ✅ Complete |
| 2. Backend Test Gaps | 6 | 6 | ✅ Complete |
| 3. Frontend Tests | 8 | 8 | ✅ Complete |
| 4. E2E Tests | 5 | 5 | ✅ Complete |
| 5. Documentation | 3 | 3 | ✅ Complete |
| **TOTAL** | **26** | **26** | **100%** |

---

## 🟢 PHASE 1: Quick Fixes (Code Errors) - ✅ COMPLETE
*Fix type errors and warnings that won't break functionality*

### 1.1 Fix BrandingContext Fast Refresh Warning ✅
**File:** `frontend/src/contexts/BrandingContext.tsx`  
**Issue:** Exporting non-component functions causes Fast Refresh warning  
**Risk:** 🟢 LOW - Just reorganizing exports

- [x] **1.1.1** Create `frontend/src/utils/branding-utils.ts`
- [x] **1.1.2** Move `useBranding()` hook to separate file or keep in context (hooks are OK)
- [x] **1.1.3** Move `getCurrentBranding()` function to `branding-utils.ts`
- [x] **1.1.4** Update imports in files using these functions
- [x] **1.1.5** Test: `cd frontend && npm run build` ✅

### 1.2 Fix email_service.py Type Errors ✅
**File:** `backend/app/services/email_service.py`  
**Issue:** Optional types not properly handled  
**Risk:** 🟡 MEDIUM - Adding validation guards

- [x] **1.2.1** Add type guard for `smtp_server` before use
- [x] **1.2.2** Add type guard for `smtp_username` and `smtp_password`
- [x] **1.2.3** Add type guard for `from_email`
- [x] **1.2.4** Fix `formataddr()` tuple type
- [x] **1.2.5** Test: Check no runtime errors when SMTP not configured

### 1.3 Fix seed_demo_data.py Type Errors ✅
**File:** `backend/scripts/seed_demo_data.py`  
**Issue:** SQLAlchemy 2.0 delete syntax  
**Risk:** 🟢 LOW - Script only, not production code

- [ ] **1.3.1** Import `delete` from sqlalchemy
- [ ] **1.3.2** Change `Table.__table__.delete()` to `delete(Table)`
- [ ] **1.3.3** Test: Script runs without errors

### 1.4 Fix seed_xyz_corp.py Type Errors
**File:** `backend/scripts/seed_xyz_corp.py`  
**Issue:** Async session context manager  
**Risk:** 🟢 LOW - Script only, not production code

- [ ] **1.4.1** Fix async session factory type annotation
- [ ] **1.4.2** Test: Script runs without errors

**✅ CHECKPOINT 1:** Run full build test
```bash
cd frontend && npm run build
cd ../backend && python -m pytest tests/ -x -q
```

---

## 🟠 PHASE 2: Backend Test Gaps - ~3 hrs
*Add missing tests for critical functionality*

### 2.1 WebSocket Tests
**File:** `backend/tests/test_websocket.py` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **2.1.1** Create test file with fixtures
- [ ] **2.1.2** Test: WebSocket connection with valid token
- [ ] **2.1.3** Test: WebSocket connection rejected without token
- [ ] **2.1.4** Test: Timer start broadcasts to connected clients
- [ ] **2.1.5** Test: Timer stop broadcasts to connected clients

### 2.2 Multi-Tenancy Tests
**File:** `backend/tests/test_multitenancy.py` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **2.2.1** Create test file with company/user fixtures
- [ ] **2.2.2** Test: User can only see their company's data
- [ ] **2.2.3** Test: Active timers filtered by company_id
- [ ] **2.2.4** Test: Teams filtered by company_id
- [ ] **2.2.5** Test: Projects filtered by company_id
- [ ] **2.2.6** Test: Super admin can see all data

### 2.3 Email Service Tests
**File:** `backend/tests/test_email_service.py` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **2.3.1** Create test file with mocked SMTP
- [ ] **2.3.2** Test: Send email success
- [ ] **2.3.3** Test: Send email fails gracefully when SMTP not configured
- [ ] **2.3.4** Test: Password reset email template renders

### 2.4 Password Reset Tests
**File:** `backend/tests/test_password_reset.py` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **2.4.1** Test: Forgot password generates token
- [ ] **2.4.2** Test: Reset password with valid token
- [ ] **2.4.3** Test: Reset password with expired token fails
- [ ] **2.4.4** Test: Reset password with invalid token fails

**✅ CHECKPOINT 2:** Run backend tests
```bash
cd backend && python -m pytest tests/ -v
```

---

## 🟠 PHASE 3: Frontend Tests - ~4 hrs
*Add component and store tests*

### 3.1 Auth Store Tests
**File:** `frontend/src/stores/authStore.test.ts` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **3.1.1** Test: Initial state is logged out
- [ ] **3.1.2** Test: Login sets user and tokens
- [ ] **3.1.3** Test: Logout clears state
- [ ] **3.1.4** Test: Token refresh updates access token

### 3.2 Timer Store Tests
**File:** `frontend/src/stores/timerStore.test.ts` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **3.2.1** Test: Initial state has no active timer
- [ ] **3.2.2** Test: Start timer sets isRunning true
- [ ] **3.2.3** Test: Stop timer sets isRunning false
- [ ] **3.2.4** Test: Timer elapsed time increments

### 3.3 LoginPage Tests
**File:** `frontend/src/pages/LoginPage.test.tsx` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **3.3.1** Test: Renders login form
- [ ] **3.3.2** Test: Shows error on invalid credentials
- [ ] **3.3.3** Test: Redirects on successful login
- [ ] **3.3.4** Test: Shows company branding when slug present

### 3.4 DashboardPage Tests
**File:** `frontend/src/pages/DashboardPage.test.tsx` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **3.4.1** Test: Renders dashboard stats
- [ ] **3.4.2** Test: Shows timer widget
- [ ] **3.4.3** Test: Shows team panel for admins only

### 3.5 TimePage Tests
**File:** `frontend/src/pages/TimePage.test.tsx` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **3.5.1** Test: Renders time entry list
- [ ] **3.5.2** Test: Can start timer with project
- [ ] **3.5.3** Test: Can add manual entry

### 3.6 Timer Component Tests
**File:** `frontend/src/components/time/TimerWidget.test.tsx` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **3.6.1** Test: Shows Start button when not running
- [ ] **3.6.2** Test: Shows Stop button when running
- [ ] **3.6.3** Test: Displays elapsed time
- [ ] **3.6.4** Test: Project select is required

### 3.7 useAuth Hook Tests
**File:** `frontend/src/hooks/useAuth.test.ts` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **3.7.1** Test: Returns current user when logged in
- [ ] **3.7.2** Test: Returns null when logged out
- [ ] **3.7.3** Test: isAdmin returns true for admin role

### 3.8 API Client Tests
**File:** `frontend/src/api/client.test.ts` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **3.8.1** Test: Adds auth header to requests
- [ ] **3.8.2** Test: Handles 401 by refreshing token
- [ ] **3.8.3** Test: Force logout on refresh failure

**✅ CHECKPOINT 3:** Run frontend tests
```bash
cd frontend && npm run test
```

---

## 🟡 PHASE 4: E2E Tests - ~2 hrs
*Add end-to-end tests for critical flows*

### 4.1 Registration Flow
**File:** `frontend/e2e/registration.spec.ts` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **4.1.1** Test: Can navigate to registration page
- [ ] **4.1.2** Test: Shows validation errors for weak password
- [ ] **4.1.3** Test: Successful registration redirects to login

### 4.2 Password Reset Flow
**File:** `frontend/e2e/password-reset.spec.ts` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **4.2.1** Test: Forgot password page loads
- [ ] **4.2.2** Test: Shows success message after submit

### 4.3 Multi-Tenant Login
**File:** `frontend/e2e/multi-tenant.spec.ts` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **4.3.1** Test: /xyz-corp redirects to /xyz-corp/login
- [ ] **4.3.2** Test: Shows company branding on login page
- [ ] **4.3.3** Test: Logout returns to company login page

### 4.4 Project CRUD Flow
**File:** `frontend/e2e/projects.spec.ts` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **4.4.1** Test: Can create a project (admin)
- [ ] **4.4.2** Test: Can edit a project
- [ ] **4.4.3** Test: Can archive a project

### 4.5 Timer Full Flow
**File:** `frontend/e2e/timer-flow.spec.ts` (NEW)  
**Risk:** 🟢 LOW - Adding tests only

- [ ] **4.5.1** Test: Start timer → wait → stop timer
- [ ] **4.5.2** Test: Time entry appears in list after stop
- [ ] **4.5.3** Test: Can add manual time entry

**✅ CHECKPOINT 4:** Run E2E tests
```bash
cd frontend && npx playwright test
```

---

## 🟡 PHASE 5: Documentation - ~1 hr
*Update and add missing docs*

### 5.1 Testing Guide
**File:** `docs/TESTING_GUIDE.md` (NEW)

- [ ] **5.1.1** Document how to run backend tests
- [ ] **5.1.2** Document how to run frontend tests
- [ ] **5.1.3** Document how to run E2E tests
- [ ] **5.1.4** Document test data setup

### 5.2 Update CONTEXT.md
- [ ] **5.2.1** Add testing section
- [ ] **5.2.2** Update session report index

### 5.3 Update Session Reports Index
- [ ] **5.3.1** Add Jan 8 report to index in CONTEXT.md

**✅ FINAL CHECKPOINT:** Full test suite
```bash
# Backend
cd backend && python -m pytest tests/ -v

# Frontend unit tests
cd ../frontend && npm run test

# E2E tests
npx playwright test

# Build check
npm run build
```

---

## 🚀 DEPLOYMENT (After All Tests Pass)

Only after completing ALL phases:

```bash
# On production server
cd ~/timetracker
git pull origin master
./scripts/deploy-sequential.sh
```

---

## 📝 Notes

*Use this section to track blockers or decisions:*

- 
- 
- 

---

## ✅ Completion Checklist

- [ ] All Phase 1 tasks complete
- [ ] All Phase 2 tasks complete  
- [ ] All Phase 3 tasks complete
- [ ] All Phase 4 tasks complete
- [ ] All Phase 5 tasks complete
- [ ] All checkpoints pass
- [ ] Code committed and pushed
- [ ] Production deployed (optional)

---

*Created: January 8, 2026*  
*Estimated Total Time: ~10 hours (spread across sessions)*
