# Dashboard Infinite Refresh Bug Assessment

**Date**: December 30, 2025  
**Issue**: Dashboard starts refreshing nonstop when auth session expires  
**Severity**: Critical - Prevents user from using the application

---

## Issue Summary

When the authentication session expires, instead of redirecting to the login page, the dashboard gets stuck in an infinite refresh/re-render loop, making the application unusable. The user had to manually stop execution via Chrome DevTools and sign out/in to recover.

---

## Root Cause Analysis

### Primary Cause: Race Condition Between Auth State and Persisted State

The bug is caused by a **mismatch between Zustand persisted state and actual auth validity**:

1. **AuthStore persists `isAuthenticated: true`** to localStorage even after the token expires
2. **ProtectedRoute** uses `isAuthenticated` from Zustand store (persisted value)
3. **API calls fail with 401/403** and trigger `window.location.href = '/login'`
4. **BUT** the persisted `isAuthenticated` is still `true`, so...
5. **React Router immediately redirects back to `/dashboard`** (due to PublicRoute logic)
6. **Dashboard makes API calls → 401/403 → redirect to /login → redirect to /dashboard → LOOP**

### The Infinite Loop Sequence:

```
1. User lands on /dashboard (token expired but isAuthenticated=true persisted)
2. DashboardPage renders → useQuery fires API calls
3. API interceptor catches 401/403 → window.location.href = '/login'
4. LoginPage's PublicRoute checks isAuthenticated (still true from persistence)
5. PublicRoute redirects to /dashboard
6. GOTO step 2 (infinite loop)
```

---

## Contributing Factors

### 1. Token Expiry Not Synced with Zustand State

**File**: [frontend/src/api/client.ts](frontend/src/api/client.ts#L76-L128)

```typescript
// Line 126-127: Tokens cleared, but Zustand state NOT updated
localStorage.removeItem('access_token');
localStorage.removeItem('refresh_token');
window.location.href = '/login';  // ❌ Redirects BEFORE clearing isAuthenticated
```

The axios interceptor clears tokens but **does NOT clear the Zustand `isAuthenticated` state** before redirecting. Since AuthStore persists `isAuthenticated` to localStorage, the stale `true` value causes the redirect loop.

### 2. PublicRoute Trusts Persisted State

**File**: [frontend/src/App.tsx](frontend/src/App.tsx#L81-L89)

```typescript
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();  // ❌ Uses persisted value

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;  // ❌ Redirects back
  }

  return <>{children}</>;
}
```

### 3. Multiple Refetch Sources Compound the Issue

Several components have `refetchInterval` that keep firing while the loop happens:

| Component | Refetch Interval | Source |
|-----------|------------------|--------|
| `ActiveTimers.tsx` | 5 seconds (when WS disconnected) | [Line 28](frontend/src/components/ActiveTimers.tsx#L28) |
| `AdminAlertsPanel.tsx` | 60 seconds | [Line 46](frontend/src/components/AdminAlertsPanel.tsx#L46) |
| `AdminReportsPage.tsx` | 30 seconds | [Line 84](frontend/src/pages/AdminReportsPage.tsx#L84) |
| `useApi.ts` (useTimerStatus) | 30 seconds | [Line 184](frontend/src/hooks/useApi.ts#L184) |
| `TimerWidget.tsx` | On window focus | [Line 54](frontend/src/components/time/TimerWidget.tsx#L54) |

### 4. WebSocket Reconnect Loop

**File**: [frontend/src/hooks/useWebSocket.ts](frontend/src/hooks/useWebSocket.ts#L155-L169)

```typescript
ws.onclose = (event) => {
  // ...
  if (autoReconnect && reconnectAttempts.current < maxReconnectAttempts) {
    reconnectAttempts.current++;
    reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);  // 3 second retry
  }
};
```

When auth fails, WebSocket also tries to reconnect 5 times, adding more failed requests.

---

## Why Signing Out and Back In Fixed It

When the user manually signed out:
1. `logout()` in authStore properly sets `isAuthenticated: false` and persists it
2. This breaks the redirect loop since PublicRoute no longer redirects away from /login
3. Fresh login creates new valid tokens

---

## Recommended Fixes

### Fix 1: Clear Zustand Auth State Before Redirect (CRITICAL)

**File**: `frontend/src/api/client.ts`

```typescript
// Import the auth store at the top
import { useAuthStore } from '../stores/authStore';

// In the response interceptor (around line 126):
// Clear tokens and Zustand state BEFORE redirect
localStorage.removeItem('access_token');
localStorage.removeItem('refresh_token');

// CRITICAL: Clear the persisted auth state
useAuthStore.getState().logout();  // Or: useAuthStore.setState({ isAuthenticated: false, user: null })

// Small delay to ensure state is persisted before redirect
setTimeout(() => {
  window.location.href = '/login';
}, 50);
```

### Fix 2: Validate Token Existence in ProtectedRoute/PublicRoute

**File**: `frontend/src/App.tsx`

```typescript
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const hasToken = !!localStorage.getItem('access_token');

  // Only redirect if BOTH persisted state AND token exist
  if (isAuthenticated && hasToken) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const hasToken = !!localStorage.getItem('access_token');

  // Require BOTH conditions to access protected routes
  if (!isAuthenticated || !hasToken) {
    return <Navigate to="/login" replace />;
  }

  return <Layout>{children}</Layout>;
}
```

### Fix 3: Add Auth Validation to AuthStore Rehydration

**File**: `frontend/src/stores/authStore.ts`

```typescript
{
  name: 'auth-storage',
  partialize: (state) => ({
    user: state.user,
    isAuthenticated: state.isAuthenticated,
  }),
  // NEW: Validate on rehydration
  onRehydrateStorage: () => (state) => {
    // If persisted as authenticated but no token, reset auth state
    const hasToken = !!localStorage.getItem('access_token');
    if (state?.isAuthenticated && !hasToken) {
      console.log('[AuthStore] Token missing, clearing stale auth state');
      useAuthStore.setState({ isAuthenticated: false, user: null });
    }
  },
}
```

### Fix 4: Prevent Query Retries on Auth Errors

**File**: `frontend/src/App.tsx`

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error: any) => {
        // Don't retry on auth errors
        if (error?.response?.status === 401 || error?.response?.status === 403) {
          return false;
        }
        return failureCount < 1;
      },
      // ... other options
    },
  },
});
```

### Fix 5: Add Circuit Breaker for Redirect Loop Detection

**File**: `frontend/src/api/client.ts`

```typescript
// Add at the top of the file
let redirectAttempts = 0;
const MAX_REDIRECT_ATTEMPTS = 3;
const REDIRECT_RESET_INTERVAL = 5000; // 5 seconds

// In the interceptor:
if ((status === 401 || status === 403) && !originalRequest._retry) {
  redirectAttempts++;
  
  // Circuit breaker: If we've tried redirecting too many times, just force logout
  if (redirectAttempts >= MAX_REDIRECT_ATTEMPTS) {
    console.error('Redirect loop detected, forcing logout');
    localStorage.clear();  // Clear ALL storage
    sessionStorage.clear();
    window.location.href = '/login';
    return Promise.reject(error);
  }
  
  // Reset counter after interval
  setTimeout(() => { redirectAttempts = 0; }, REDIRECT_RESET_INTERVAL);
  
  // ... rest of the logic
}
```

---

## Implementation Priority

| Fix | Priority | Complexity | Impact |
|-----|----------|------------|--------|
| Fix 1 (Clear Zustand before redirect) | **CRITICAL** | Low | Directly prevents the loop |
| Fix 2 (Dual validation in routes) | High | Low | Defense in depth |
| Fix 3 (Rehydration validation) | High | Low | Prevents stale state issues |
| Fix 4 (Query retry prevention) | Medium | Low | Reduces failed requests |
| Fix 5 (Circuit breaker) | Medium | Medium | Last resort safety net |

---

## Testing Scenarios

After implementing fixes, test these scenarios:

1. **Token Expiry During Active Session**
   - Leave app open for token expiry duration
   - Perform any action requiring API call
   - Expected: Clean redirect to login, no loop

2. **Stale Persisted State**
   - Manually delete `access_token` from localStorage (DevTools)
   - Refresh the page
   - Expected: Redirect to login without loop

3. **Multiple Tabs**
   - Open app in two tabs
   - Logout in one tab
   - Try to use the other tab
   - Expected: Both tabs redirect to login cleanly

4. **Network Disconnect During Session**
   - Start timer, disconnect network
   - Reconnect after token would expire
   - Expected: Graceful error handling, redirect to login

---

## Additional Observations

### Token Expiry Configuration
Need to verify backend token expiry settings. If tokens expire too quickly, this issue becomes more frequent.

### Missing Global Error Boundary
The app lacks a global error boundary that could catch repeated render errors and show a recovery UI.

### WebSocket Authentication
WebSocket uses same token - when expired, WS fails and triggers reconnect attempts that also fail, compounding the issue.

---

## Summary

**The root cause is a state synchronization issue**: The axios interceptor clears tokens but doesn't update Zustand's persisted `isAuthenticated` state, causing PublicRoute to redirect authenticated users back to dashboard, which makes API calls that fail, triggering another redirect - an infinite loop.

**The fix is straightforward**: Update the auth Zustand state **before** redirecting to login, and add validation checks to route guards to verify both persisted state AND actual token presence.
