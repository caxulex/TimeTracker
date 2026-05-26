// ============================================
// TIME TRACKER - API CLIENT PAGINATION TESTS
// Asserts outgoing query params use `page_size` (backend's expected name),
// not the legacy `size`. Fixes silent 20-cap regression in usersApi,
// teamsApi, and tasksApi.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Capture the axios instance used by client.ts so we can spy on its `.get`.
// Use vi.hoisted so the spy exists when vi.mock's factory runs (hoisted above imports).
const { mockGet } = vi.hoisted(() => ({
  mockGet: vi.fn().mockResolvedValue({ data: { items: [], total: 0, page: 1, size: 0 } }),
}));

vi.mock('axios', () => {
  const instance = {
    get: mockGet,
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return {
    default: {
      create: vi.fn(() => instance),
      isAxiosError: vi.fn(() => false),
    },
  };
});

// Import AFTER the mock is registered so client.ts picks up the mocked axios.
import { usersApi, teamsApi, tasksApi, payRatesApi } from '../client';

describe('API client pagination params (page_size vs size)', () => {
  beforeEach(() => {
    mockGet.mockClear();
  });

  it('usersApi.getAll(1, 100) sends page_size=100 (not size)', async () => {
    await usersApi.getAll(1, 100);

    expect(mockGet).toHaveBeenCalledTimes(1);
    const [url, config] = mockGet.mock.calls[0];
    expect(url).toBe('/api/users');
    expect(config.params).toEqual({ page: 1, page_size: 100 });
    expect(config.params).not.toHaveProperty('size');
  });

  it('teamsApi.getAll(2, 50) sends page_size=50 (not size)', async () => {
    await teamsApi.getAll(2, 50);

    expect(mockGet).toHaveBeenCalledTimes(1);
    const [url, config] = mockGet.mock.calls[0];
    expect(url).toBe('/api/teams');
    expect(config.params).toEqual({ page: 2, page_size: 50 });
    expect(config.params).not.toHaveProperty('size');
  });

  it('tasksApi.getAll({ page_size, project_id }) forwards page_size in query string', async () => {
    await tasksApi.getAll({ page_size: 100, project_id: 5 });

    expect(mockGet).toHaveBeenCalledTimes(1);
    const [url, config] = mockGet.mock.calls[0];
    expect(url).toBe('/api/tasks');
    expect(config.params).toMatchObject({ page_size: 100, project_id: 5 });
  });

  it('payRatesApi.getAll(1, 100) sends page_size=100 (not limit) to /api/pay-rates', async () => {
    await payRatesApi.getAll(1, 100, true);

    expect(mockGet).toHaveBeenCalledTimes(1);
    const [url, config] = mockGet.mock.calls[0];
    expect(url).toBe('/api/pay-rates');
    expect(config.params).toMatchObject({ skip: 0, page_size: 100, active_only: true });
    expect(config.params).not.toHaveProperty('limit');
  });
});
