// ============================================
// TIME TRACKER - USE AUTH HOOK TESTS
// Phase 7: Testing - useAuth hook
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAuth } from './useAuth';
import { useAuthStore } from '../stores/authStore';

// Mock the auth store
vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('useAuth Hook', () => {
  const mockLogin = vi.fn();
  const mockLogout = vi.fn();
  const mockRegister = vi.fn();
  const mockFetchUser = vi.fn();
  const mockClearError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      login: mockLogin,
      logout: mockLogout,
      register: mockRegister,
      fetchUser: mockFetchUser,
      clearError: mockClearError,
    });
  });

  describe('Initial State', () => {
    it('should return initial unauthenticated state', () => {
      const { result } = renderHook(() => useAuth());

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('should expose login function', () => {
      const { result } = renderHook(() => useAuth());

      expect(result.current.login).toBe(mockLogin);
    });

    it('should expose logout function', () => {
      const { result } = renderHook(() => useAuth());

      expect(result.current.logout).toBe(mockLogout);
    });

    it('should expose register function', () => {
      const { result } = renderHook(() => useAuth());

      expect(result.current.register).toBe(mockRegister);
    });

    it('should expose fetchUser function', () => {
      const { result } = renderHook(() => useAuth());

      expect(result.current.fetchUser).toBe(mockFetchUser);
    });

    it('should expose clearError function', () => {
      const { result } = renderHook(() => useAuth());

      expect(result.current.clearError).toBe(mockClearError);
    });
  });

  describe('Authenticated State', () => {
    it('should return authenticated user', () => {
      const mockUser = {
        id: 1,
        email: 'test@example.com',
        name: 'Test User',
        role: 'user',
        company_id: 1,
      };

      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: mockLogin,
        logout: mockLogout,
        register: mockRegister,
        fetchUser: mockFetchUser,
        clearError: mockClearError,
      });

      const { result } = renderHook(() => useAuth());

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isAuthenticated).toBe(true);
    });

    it('should return user with admin role', () => {
      const mockAdmin = {
        id: 1,
        email: 'admin@example.com',
        name: 'Admin User',
        role: 'admin',
        company_id: 1,
      };

      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: mockAdmin,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: mockLogin,
        logout: mockLogout,
        register: mockRegister,
        fetchUser: mockFetchUser,
        clearError: mockClearError,
      });

      const { result } = renderHook(() => useAuth());

      expect(result.current.user?.role).toBe('admin');
    });
  });

  describe('Loading State', () => {
    it('should return loading state', () => {
      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: null,
        isAuthenticated: false,
        isLoading: true,
        error: null,
        login: mockLogin,
        logout: mockLogout,
        register: mockRegister,
        fetchUser: mockFetchUser,
        clearError: mockClearError,
      });

      const { result } = renderHook(() => useAuth());

      expect(result.current.isLoading).toBe(true);
    });
  });

  describe('Error State', () => {
    it('should return error state', () => {
      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: 'Invalid credentials',
        login: mockLogin,
        logout: mockLogout,
        register: mockRegister,
        fetchUser: mockFetchUser,
        clearError: mockClearError,
      });

      const { result } = renderHook(() => useAuth());

      expect(result.current.error).toBe('Invalid credentials');
    });
  });

  describe('Function Calls', () => {
    it('should call login with credentials', async () => {
      const { result } = renderHook(() => useAuth());

      const credentials = { email: 'test@example.com', password: 'password' };
      await act(async () => {
        result.current.login(credentials);
      });

      expect(mockLogin).toHaveBeenCalledWith(credentials);
    });

    it('should call logout', async () => {
      const { result } = renderHook(() => useAuth());

      await act(async () => {
        result.current.logout();
      });

      expect(mockLogout).toHaveBeenCalled();
    });

    it('should call register with user data', async () => {
      const { result } = renderHook(() => useAuth());

      const userData = {
        email: 'new@example.com',
        password: 'password',
        name: 'New User',
        company_name: 'New Company',
      };

      await act(async () => {
        result.current.register(userData);
      });

      expect(mockRegister).toHaveBeenCalledWith(userData);
    });

    it('should call fetchUser', async () => {
      const { result } = renderHook(() => useAuth());

      await act(async () => {
        result.current.fetchUser();
      });

      expect(mockFetchUser).toHaveBeenCalled();
    });

    it('should call clearError', async () => {
      const { result } = renderHook(() => useAuth());

      await act(async () => {
        result.current.clearError();
      });

      expect(mockClearError).toHaveBeenCalled();
    });
  });
});
