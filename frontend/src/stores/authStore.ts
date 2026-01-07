// ============================================
// TIME TRACKER - AUTH STORE (ZUSTAND)
// ============================================
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, UserLogin, UserRegister, AuthToken } from '../types';
import { authApi } from '../api/client';

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
          localStorage.setItem('access_token', tokens.access_token);
          localStorage.setItem('refresh_token', tokens.refresh_token);

          // Fetch user data after login
          const user = await authApi.getMe();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch (error: any) {
          const detail = error.response?.data?.detail;
          // Handle FastAPI validation errors (array of objects) vs string errors
          let message = 'Login failed';
          if (typeof detail === 'string') {
            message = detail;
          } else if (Array.isArray(detail)) {
            message = detail.map((e: any) => e.msg || e.message || String(e)).join(', ');
          } else if (detail?.msg) {
            message = detail.msg;
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
        } catch (error: any) {
          const detail = error.response?.data?.detail;
          // Handle FastAPI validation errors (array of objects) vs string errors
          let message = 'Registration failed';
          if (typeof detail === 'string') {
            message = detail;
          } else if (Array.isArray(detail)) {
            message = detail.map((e: any) => e.msg || e.message || String(e)).join(', ');
          } else if (detail?.msg) {
            message = detail.msg;
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
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          set({ user: null, isAuthenticated: false, isLoading: false, error: null });
        }
      },

      fetchUser: async () => {
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
