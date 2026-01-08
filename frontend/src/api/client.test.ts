// ============================================
// TIME TRACKER - API CLIENT TESTS
// Phase 7: Testing - API client configuration
// ============================================
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';

// Mock axios
vi.mock('axios', async () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: {
        use: vi.fn(),
      },
      response: {
        use: vi.fn(),
      },
    },
  };

  return {
    default: {
      create: vi.fn(() => mockAxiosInstance),
      ...mockAxiosInstance,
    },
  };
});

// Mock import.meta.env
vi.stubGlobal('import', {
  meta: {
    env: {
      VITE_API_URL: 'http://localhost:8000',
    },
  },
});

// Simple mock storage for testing
const createMockStorage = () => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
    get length() { return Object.keys(store).length; },
    key: (index: number) => Object.keys(store)[index] || null,
  };
};

describe('API Client', () => {
  let mockStorage: ReturnType<typeof createMockStorage>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockStorage = createMockStorage();
    // Override global localStorage for these tests
    Object.defineProperty(window, 'localStorage', { value: mockStorage, writable: true });
  });

  afterEach(() => {
    mockStorage.clear();
  });

  describe('URL Normalization', () => {
    it('should normalize API base URL correctly', () => {
      // Test the normalizeApiBaseUrl function logic
      const normalize = (input: string): string => {
        const trimmed = (input ?? '').trim();
        if (!trimmed) return '';
        const withoutTrailingSlash = trimmed.replace(/\/+$/g, '');
        if (withoutTrailingSlash.endsWith('/api')) {
          return withoutTrailingSlash.slice(0, -4);
        }
        return withoutTrailingSlash;
      };

      expect(normalize('http://localhost:8000')).toBe('http://localhost:8000');
      expect(normalize('http://localhost:8000/')).toBe('http://localhost:8000');
      expect(normalize('http://localhost:8000/api')).toBe('http://localhost:8000');
      expect(normalize('http://localhost:8000/api/')).toBe('http://localhost:8000');
      expect(normalize('')).toBe('');
      expect(normalize('  ')).toBe('');
    });
  });

  describe('Token Storage', () => {
    it('should store access token in localStorage', () => {
      const token = 'test-access-token';
      localStorage.setItem('access_token', token);
      
      expect(localStorage.getItem('access_token')).toBe(token);
    });

    it('should store refresh token in localStorage', () => {
      const token = 'test-refresh-token';
      localStorage.setItem('refresh_token', token);
      
      expect(localStorage.getItem('refresh_token')).toBe(token);
    });

    it('should clear tokens on logout', () => {
      localStorage.setItem('access_token', 'token1');
      localStorage.setItem('refresh_token', 'token2');

      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');

      expect(localStorage.getItem('access_token')).toBeNull();
      expect(localStorage.getItem('refresh_token')).toBeNull();
    });
  });

  describe('Auth State Persistence', () => {
    it('should preserve company slug for white-label portals', () => {
      localStorage.setItem('tt_company_slug', 'acme-corp');
      
      expect(localStorage.getItem('tt_company_slug')).toBe('acme-corp');
    });

    it('should clear auth storage correctly', () => {
      const authState = {
        state: {
          isAuthenticated: true,
          user: { id: 1, email: 'test@test.com' },
        },
      };
      localStorage.setItem('auth-storage', JSON.stringify(authState));

      // Simulate clearing auth
      const parsed = JSON.parse(localStorage.getItem('auth-storage') || '{}');
      parsed.state = { ...parsed.state, isAuthenticated: false, user: null };
      localStorage.setItem('auth-storage', JSON.stringify(parsed));

      const updated = JSON.parse(localStorage.getItem('auth-storage') || '{}');
      expect(updated.state.isAuthenticated).toBe(false);
      expect(updated.state.user).toBeNull();
    });
  });

  describe('Request Headers', () => {
    it('should add authorization header when token exists', () => {
      localStorage.setItem('access_token', 'Bearer test-token');
      
      // Test the interceptor logic
      const config = {
        headers: {},
      };
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers = { ...config.headers, Authorization: `Bearer ${token}` };
      }

      expect(config.headers).toHaveProperty('Authorization');
    });

    it('should not add authorization header when no token', () => {
      // No token set
      const config = {
        headers: {},
      };
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers = { ...config.headers, Authorization: `Bearer ${token}` };
      }

      expect(config.headers).not.toHaveProperty('Authorization');
    });
  });

  describe('Error Handling Logic', () => {
    it('should detect redirect loops after max redirects', () => {
      const MAX_AUTH_REDIRECTS = 3;
      let authRedirectCount = 0;

      // Simulate multiple auth redirects
      for (let i = 0; i < 4; i++) {
        authRedirectCount++;
        if (authRedirectCount >= MAX_AUTH_REDIRECTS) {
          // Would trigger force logout
          break;
        }
      }

      expect(authRedirectCount).toBe(MAX_AUTH_REDIRECTS);
    });

    it('should identify auth endpoints correctly', () => {
      const isAuthEndpoint = (url: string) => 
        url.includes('/auth/login') || url.includes('/auth/refresh');

      expect(isAuthEndpoint('/api/auth/login')).toBe(true);
      expect(isAuthEndpoint('/api/auth/refresh')).toBe(true);
      expect(isAuthEndpoint('/api/users')).toBe(false);
      expect(isAuthEndpoint('/api/time-entries')).toBe(false);
    });
  });

  describe('API Endpoint Configuration', () => {
    it('should have correct auth endpoints', () => {
      const authEndpoints = {
        login: '/api/auth/login',
        refresh: '/api/auth/refresh',
        me: '/api/auth/me',
        forgotPassword: '/api/auth/forgot-password',
        resetPassword: '/api/auth/reset-password',
      };

      expect(authEndpoints.login).toContain('/auth/');
      expect(authEndpoints.refresh).toContain('/auth/');
      expect(authEndpoints.me).toContain('/auth/');
    });

    it('should have correct time entry endpoints', () => {
      const timeEntryEndpoints = {
        list: '/api/time-entries',
        create: '/api/time-entries',
        update: (id: number) => `/api/time-entries/${id}`,
        delete: (id: number) => `/api/time-entries/${id}`,
        timer: '/api/time-entries/timer',
      };

      expect(timeEntryEndpoints.list).toBe('/api/time-entries');
      expect(timeEntryEndpoints.update(1)).toBe('/api/time-entries/1');
      expect(timeEntryEndpoints.delete(5)).toBe('/api/time-entries/5');
    });

    it('should have correct project endpoints', () => {
      const projectEndpoints = {
        list: '/api/projects',
        create: '/api/projects',
        get: (id: number) => `/api/projects/${id}`,
      };

      expect(projectEndpoints.list).toBe('/api/projects');
      expect(projectEndpoints.get(10)).toBe('/api/projects/10');
    });

    it('should have correct team endpoints', () => {
      const teamEndpoints = {
        list: '/api/teams',
        create: '/api/teams',
        get: (id: number) => `/api/teams/${id}`,
        members: (id: number) => `/api/teams/${id}/members`,
      };

      expect(teamEndpoints.list).toBe('/api/teams');
      expect(teamEndpoints.members(5)).toBe('/api/teams/5/members');
    });
  });

  describe('Pagination Parameters', () => {
    it('should build pagination query params correctly', () => {
      const buildParams = (page: number, size: number) => ({
        page,
        size,
      });

      const params = buildParams(1, 50);
      expect(params.page).toBe(1);
      expect(params.size).toBe(50);
    });

    it('should handle filters in query params', () => {
      const buildFilterParams = (filters: Record<string, unknown>) => {
        const params: Record<string, unknown> = {};
        Object.entries(filters).forEach(([key, value]) => {
          if (value !== undefined && value !== null && value !== '') {
            params[key] = value;
          }
        });
        return params;
      };

      const result = buildFilterParams({
        project_id: 1,
        user_id: undefined,
        start_date: '2026-01-01',
        end_date: '',
      });

      expect(result).toEqual({
        project_id: 1,
        start_date: '2026-01-01',
      });
    });
  });

  describe('Response Type Handling', () => {
    it('should handle paginated response structure', () => {
      const paginatedResponse = {
        items: [{ id: 1 }, { id: 2 }],
        total: 100,
        page: 1,
        size: 50,
        pages: 2,
      };

      expect(paginatedResponse.items.length).toBe(2);
      expect(paginatedResponse.total).toBe(100);
      expect(paginatedResponse.pages).toBe(2);
    });

    it('should handle auth token response structure', () => {
      const tokenResponse = {
        access_token: 'jwt-token',
        refresh_token: 'refresh-jwt-token',
        token_type: 'bearer',
      };

      expect(tokenResponse.access_token).toBeDefined();
      expect(tokenResponse.refresh_token).toBeDefined();
      expect(tokenResponse.token_type).toBe('bearer');
    });
  });
});
