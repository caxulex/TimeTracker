// ============================================
// TIME TRACKER - AUTH STORE (ZUSTAND)
// ============================================
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, UserLogin, UserRegister, AuthToken } from '../types';
import { authApi } from '../api/client';
import axios from 'axios';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: UserLogin) => Promise<void>;
  register: (data: UserRegister) => Promise<void>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  clearError: () => void;
  setUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (credentials: UserLogin) => {
        set({ isLoading: true, error: null });
        try {
          const tokens: AuthToken = await authApi.login(credentials);
          // TODO(B17, XSS-risk): localStorage tokens are vulnerable to any
          // SPA XSS = total account takeover. Migration plan:
          // POST_LAUNCH_TODO.md ┬º "B17 token storage migration plan".
          // Target: refresh token in httpOnly+Secure+SameSite=Strict cookie,
          // access token in module-level memory only (see client.ts).
          localStorage.setItem('access_token', tokens.access_token);
          localStorage.setItem('refresh_token', tokens.refresh_token);

          // Fetch user data after login
          const user = await authApi.getMe();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch (error: unknown) {
          let message = 'Login failed';
          if (axios.isAxiosError(error)) {
            const detail = error.response?.data?.detail;
            if (typeof detail === 'string') {
              message = detail;
            } else if (Array.isArray(detail)) {
              message = detail.map((e: Record<string, unknown>) => (typeof e.msg === 'string' ? e.msg : typeof e.message === 'string' ? e.message : String(e))).join(', ');
            } else if (detail?.msg) {
              message = detail.msg;
            }
          } else if (error instanceof Error) {
            message = error.message;
          } else if (typeof error === 'object' && error !== null) {
            const resp = (error as Record<string, unknown>).response as Record<string, unknown> | undefined;
            const data = resp?.data as Record<string, unknown> | undefined;
            if (typeof data?.detail === 'string') {
              message = data.detail;
            }
          }
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      register: async (data: UserRegister) => {
        set({ isLoading: true, error: null });
        try {
          await authApi.register(data);
          // After registration, login automatically
          await get().login({ email: data.email, password: data.password });
        } catch (error: unknown) {
          let message = 'Registration failed';
          if (axios.isAxiosError(error)) {
            const detail = error.response?.data?.detail;
            if (typeof detail === 'string') {
              message = detail;
            } else if (Array.isArray(detail)) {
              message = detail.map((e: Record<string, unknown>) => (typeof e.msg === 'string' ? e.msg : typeof e.message === 'string' ? e.message : String(e))).join(', ');
            } else if (detail?.msg) {
              message = detail.msg;
            }
          } else if (error instanceof Error) {
            message = error.message;
          } else if (typeof error === 'object' && error !== null) {
            const resp = (error as Record<string, unknown>).response as Record<string, unknown> | undefined;
            const data = resp?.data as Record<string, unknown> | undefined;
            if (typeof data?.detail === 'string') {
              message = data.detail;
            }
          }
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        set({ isLoading: true });
        try {
          await authApi.logout();
        } catch (error) {
          // Ignore logout errors
        } finally {
          // TODO(B17, XSS-risk): replace with cookie clear + memory clear once
          // migration in POST_LAUNCH_TODO.md ┬º B17 ships.
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          set({ user: null, isAuthenticated: false, isLoading: false, error: null });
        }
      },

      fetchUser: async () => {
        // TODO(B17, XSS-risk): replace with getAccessToken() module accessor.
        const token = localStorage.getItem('access_token');
        if (!token) {
          set({ isAuthenticated: false, user: null });
          return;
        }

        set({ isLoading: true });
        try {
          const user = await authApi.getMe();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch (error) {
          // TODO(B17, XSS-risk): clear via cookie expiry + memory clear post-migration.
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          set({ user: null, isAuthenticated: false, isLoading: false });
        }
      },

      clearError: () => set({ error: null }),

      setUser: (user: User) => set({ user }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        // Only persist user and isAuthenticated
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
      // Validate auth state on rehydration to prevent stale isAuthenticated causing redirect loops
      onRehydrateStorage: () => (state, error) => {
        if (error) {
          console.error('[AuthStore] Error rehydrating:', error);
          return;
        }
        
        // If persisted as authenticated but no token exists, clear the stale state
        // TODO(B17, XSS-risk): swap to !!getAccessToken() (in-memory) post-migration.
        const hasToken = !!localStorage.getItem('access_token');
        if (state?.isAuthenticated && !hasToken) {
          console.warn('[AuthStore] Token missing but isAuthenticated=true - clearing stale auth state');
          // Use setTimeout to avoid state update during rehydration
          setTimeout(() => {
            useAuthStore.setState({ isAuthenticated: false, user: null });
          }, 0);
        }
      },
    }
  )
);
