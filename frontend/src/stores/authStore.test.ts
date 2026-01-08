// ============================================
// TIME TRACKER - AUTH STORE TESTS
// Phase 7: Testing - Zustand auth store
// ============================================
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act } from '@testing-library/react';

// Mock the auth API
vi.mock('../api/client', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
    getMe: vi.fn(),
  },
}));

// Import after mocking
import { useAuthStore } from './authStore';
import { authApi } from '../api/client';

describe('Auth Store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear localStorage
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('Initial State', () => {
    it('should start with no user after logout', async () => {
      await act(async () => {
        await useAuthStore.getState().logout();
      });
      const { user } = useAuthStore.getState();
      expect(user).toBeNull();
    });

    it('should start as not authenticated after logout', async () => {
      await act(async () => {
        await useAuthStore.getState().logout();
      });
      const { isAuthenticated } = useAuthStore.getState();
      expect(isAuthenticated).toBe(false);
    });

    it('should have no error after logout', async () => {
      await act(async () => {
        await useAuthStore.getState().logout();
      });
      const { error } = useAuthStore.getState();
      expect(error).toBeNull();
    });
  });

  describe('Login', () => {
    it('should login successfully', async () => {
      const mockTokens = {
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'bearer',
      };
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        name: 'Test User',
        role: 'regular_user' as const,
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
      };

      vi.mocked(authApi.login).mockResolvedValue(mockTokens);
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser);

      await act(async () => {
        await useAuthStore.getState().login({
          email: 'test@example.com',
          password: 'password123',
        });
      });

      const { user, isAuthenticated, isLoading, error } = useAuthStore.getState();
      expect(user).toEqual(mockUser);
      expect(isAuthenticated).toBe(true);
      expect(isLoading).toBe(false);
      expect(error).toBeNull();
      expect(localStorage.getItem('access_token')).toBe('test-access-token');
      expect(localStorage.getItem('refresh_token')).toBe('test-refresh-token');
    });

    it('should handle login failure', async () => {
      vi.mocked(authApi.login).mockRejectedValue({
        response: {
          data: {
            detail: 'Invalid credentials',
          },
        },
      });

      await act(async () => {
        try {
          await useAuthStore.getState().login({
            email: 'test@example.com',
            password: 'wrong',
          });
        } catch (e) {
          // Expected to throw
        }
      });

      const { error, isAuthenticated } = useAuthStore.getState();
      expect(error).toBe('Invalid credentials');
      expect(isAuthenticated).toBe(false);
    });
  });

  describe('Logout', () => {
    it('should clear user data on logout', async () => {
      // Set up initial authenticated state
      localStorage.setItem('access_token', 'token');
      localStorage.setItem('refresh_token', 'refresh');

      vi.mocked(authApi.logout).mockResolvedValue(undefined);

      await act(async () => {
        await useAuthStore.getState().logout();
      });

      const { user, isAuthenticated } = useAuthStore.getState();
      expect(user).toBeNull();
      expect(isAuthenticated).toBe(false);
      expect(localStorage.getItem('access_token')).toBeNull();
      expect(localStorage.getItem('refresh_token')).toBeNull();
    });
  });

  describe('Set User', () => {
    it('should set user directly', () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        name: 'Test User',
        role: 'admin' as const,
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
      };

      act(() => {
        useAuthStore.getState().setUser(mockUser);
      });

      const { user } = useAuthStore.getState();
      expect(user).toEqual(mockUser);
    });
  });

  describe('Clear Error', () => {
    it('should clear error state', async () => {
      // First set an error
      vi.mocked(authApi.login).mockRejectedValue({
        response: {
          data: {
            detail: 'Some error',
          },
        },
      });

      await act(async () => {
        try {
          await useAuthStore.getState().login({
            email: 'test@example.com',
            password: 'wrong',
          });
        } catch (e) {
          // Expected
        }
      });

      expect(useAuthStore.getState().error).toBe('Some error');

      act(() => {
        useAuthStore.getState().clearError();
      });

      expect(useAuthStore.getState().error).toBeNull();
    });
  });

  describe('Fetch User', () => {
    it('should fetch current user when token exists', async () => {
      localStorage.setItem('access_token', 'valid-token');

      const mockUser = {
        id: 1,
        email: 'test@example.com',
        name: 'Test User',
        role: 'regular_user' as const,
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
      };

      vi.mocked(authApi.getMe).mockResolvedValue(mockUser);

      await act(async () => {
        await useAuthStore.getState().fetchUser();
      });

      const { user, isAuthenticated } = useAuthStore.getState();
      expect(user).toEqual(mockUser);
      expect(isAuthenticated).toBe(true);
    });

    it('should not fetch when no token exists', async () => {
      // No token set
      await act(async () => {
        await useAuthStore.getState().fetchUser();
      });

      expect(authApi.getMe).not.toHaveBeenCalled();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
  });
});
