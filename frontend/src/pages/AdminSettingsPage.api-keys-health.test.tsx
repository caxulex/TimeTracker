import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

import { AdminSettingsPage } from './AdminSettingsPage';
import { apiKeysApi } from '../api/apiKeys';
import { usersApi } from '../api/client';
import type { APIKey } from '../types/apiKey';

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn((selector?: (state: { user: unknown }) => unknown) => {
    const state = {
      user: {
        id: 1,
        name: 'Admin User',
        email: 'admin@example.com',
        role: 'super_admin',
        is_active: true,
      },
    };
    return selector ? selector(state) : state;
  }),
}));

vi.mock('../hooks/useNotifications', () => ({
  useNotifications: () => ({
    addNotification: vi.fn(),
  }),
}));

vi.mock('../api/apiKeys', () => ({
  apiKeysApi: {
    getAll: vi.fn(),
    getEncryptionStatus: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    test: vi.fn(),
  },
}));

vi.mock('../api/client', () => ({
  usersApi: {
    getAll: vi.fn(),
  },
}));

const mockedApiKeysApi = vi.mocked(apiKeysApi);
const mockedUsersApi = vi.mocked(usersApi);

const createClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

const renderPage = () => {
  const queryClient = createClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AdminSettingsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
};

function buildKey(overrides: Partial<APIKey> = {}): APIKey {
  const now = new Date();
  const twoHoursAgo = new Date(now.getTime() - (2 * 60 * 60 * 1000)).toISOString();
  return {
    id: 10,
    provider: 'gemini',
    key_preview: '...1234',
    label: 'Gemini Prod',
    is_active: true,
    created_by: 1,
    created_at: now.toISOString(),
    updated_at: now.toISOString(),
    last_used_at: twoHoursAgo,
    usage_count: 5,
    last_successful_call_at: twoHoursAgo,
    last_failed_call_at: null,
    success_count: 5,
    failure_count: 0,
    last_error_message: null,
    last_error_status_code: null,
    health_status: 'healthy',
    notes: null,
    ...overrides,
  };
}

describe('AdminSettingsPage API key health surface', () => {
  beforeEach(() => {
    mockedUsersApi.getAll.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      size: 500,
      pages: 0,
    });

    mockedApiKeysApi.getEncryptionStatus.mockResolvedValue({
      configured: true,
      message: 'ok',
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders Healthy badge for healthy keys', async () => {
    mockedApiKeysApi.getAll.mockResolvedValue({
      items: [buildKey({ health_status: 'healthy' })],
      total: 1,
      page: 1,
      page_size: 20,
      has_more: false,
    });

    renderPage();

    expect(await screen.findByText('Healthy')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('renders Failing badge and last error for failing keys', async () => {
    mockedApiKeysApi.getAll.mockResolvedValue({
      items: [
        buildKey({
          health_status: 'failing',
          usage_count: 68,
          success_count: 0,
          failure_count: 68,
          last_error_message: '429 Your prepayment credits are depleted',
          last_error_status_code: 429,
          last_successful_call_at: null,
          last_failed_call_at: new Date().toISOString(),
        }),
      ],
      total: 1,
      page: 1,
      page_size: 20,
      has_more: false,
    });

    renderPage();

    expect(await screen.findByText('Failing')).toBeInTheDocument();
    expect(
      screen.getByText(/Failed 68 of 68 recent calls\. Last error: 429 Your prepayment credits are depleted/i)
    ).toBeInTheDocument();
  });

  it('renders relative timestamp text for healthy keys', async () => {
    mockedApiKeysApi.getAll.mockResolvedValue({
      items: [
        buildKey({
          health_status: 'healthy',
          last_successful_call_at: new Date(Date.now() - (2 * 60 * 60 * 1000)).toISOString(),
        }),
      ],
      total: 1,
      page: 1,
      page_size: 20,
      has_more: false,
    });

    renderPage();

    const message = await screen.findByText(/Last successful call:/i);
    expect(message.textContent).toMatch(/Last successful call: (just now|\d+ minute[s]? ago|\d+ hour[s]? ago|yesterday|\d+ days ago)/i);
  });
});
