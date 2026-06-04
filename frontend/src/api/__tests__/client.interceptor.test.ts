// ============================================
// TIME TRACKER - API CLIENT INTERCEPTOR TESTS
// Focused coverage for response interceptor auth handling.
// ============================================
import { beforeAll, beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

const { requestUse, responseUse, mockCreate, mockPost } = vi.hoisted(() => {
  const requestUse = vi.fn();
  const responseUse = vi.fn();
  const mockCreate = vi.fn();
  const mockPost = vi.fn();
  return { requestUse, responseUse, mockCreate, mockPost };
});

vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: {
        use: requestUse,
      },
      response: {
        use: responseUse,
      },
    },
  };

  return {
    default: {
      create: mockCreate.mockReturnValue(mockAxiosInstance),
      post: mockPost,
      isAxiosError: vi.fn(() => false),
    },
  };
});

vi.stubGlobal('import', {
  meta: {
    env: {
      VITE_API_URL: 'http://localhost:8000',
    },
  },
});

type MockStorage = {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
  removeItem: (key: string) => void;
  clear: () => void;
};

function createMockStorage(): MockStorage {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
}

function createAxiosError(status?: number, url = '/api/projects/1/teams') {
  return {
    config: {
      url,
      headers: {},
    },
    response: status ? { status } : undefined,
  };
}

describe('API client response interceptor', () => {
  let mockStorage: MockStorage;
  let originalLocation: Location;
  let hrefSetter: ReturnType<typeof vi.fn>;
  let handleErrorResponse: (error: unknown) => Promise<unknown>;

  beforeAll(async () => {
    await import('../client');
    const responseHandler = responseUse.mock.calls[0]?.[1];
    handleErrorResponse = responseHandler as (error: unknown) => Promise<unknown>;
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockStorage = createMockStorage();
    Object.defineProperty(window, 'localStorage', { value: mockStorage, writable: true });

    hrefSetter = vi.fn();
    originalLocation = window.location;
    delete (window as unknown as { location?: Location }).location;
    (window as unknown as { location: Location }).location = {
      pathname: '/dashboard',
      get href() {
        return 'http://localhost/dashboard';
      },
      set href(value: string) {
        hrefSetter(value);
      },
    } as unknown as Location;
  });

  afterEach(() => {
    (window as unknown as { location: Location }).location = originalLocation;
    mockStorage.clear();
  });

  it('401 response triggers logout flow', async () => {
    localStorage.setItem('access_token', 'expired-access');
    localStorage.setItem('auth-storage', JSON.stringify({ state: { isAuthenticated: true, user: { id: 1 } } }));

    await expect(handleErrorResponse(createAxiosError(401))).rejects.toBeDefined();

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(JSON.parse(localStorage.getItem('auth-storage') || '{}')).toMatchObject({
      state: {
        isAuthenticated: false,
        user: null,
      },
    });
    expect(hrefSetter).toHaveBeenCalledWith('/login');
  });

  it('401 response on /auth/login does not attempt refresh before rejecting', async () => {
    await expect(handleErrorResponse(createAxiosError(401, '/api/auth/login'))).rejects.toBeDefined();

    expect(mockPost).not.toHaveBeenCalled();
    expect(hrefSetter).toHaveBeenCalledWith('/login');
  });

  it('403 response is passed through without logout or redirect', async () => {
    localStorage.setItem('access_token', 'valid-access');
    localStorage.setItem('refresh_token', 'valid-refresh');
    localStorage.setItem('auth-storage', JSON.stringify({ state: { isAuthenticated: true } }));

    const error = createAxiosError(403);

    await expect(handleErrorResponse(error)).rejects.toBe(error);

    expect(localStorage.getItem('access_token')).toBe('valid-access');
    expect(localStorage.getItem('refresh_token')).toBe('valid-refresh');
    expect(localStorage.getItem('auth-storage')).toBeTruthy();
    expect(hrefSetter).not.toHaveBeenCalled();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it('500 response does not trigger logout', async () => {
    localStorage.setItem('access_token', 'valid-access');

    const error = createAxiosError(500);

    await expect(handleErrorResponse(error)).rejects.toBe(error);

    expect(localStorage.getItem('access_token')).toBe('valid-access');
    expect(hrefSetter).not.toHaveBeenCalled();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it('network error without response does not trigger logout', async () => {
    localStorage.setItem('access_token', 'valid-access');

    const error = {
      config: {
        url: '/api/projects/1/teams',
        headers: {},
      },
    };

    await expect(handleErrorResponse(error)).rejects.toBe(error);

    expect(localStorage.getItem('access_token')).toBe('valid-access');
    expect(hrefSetter).not.toHaveBeenCalled();
    expect(mockPost).not.toHaveBeenCalled();
  });
});