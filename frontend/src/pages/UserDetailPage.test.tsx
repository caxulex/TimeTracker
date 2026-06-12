import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

import UserDetailPage from './UserDetailPage';

const getAdminUserDetailMock = vi.fn();

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn((selector: (state: { user: unknown }) => unknown) =>
    selector({
      user: {
        id: 1,
        role: 'admin',
      },
    }),
  ),
}));

vi.mock('../api/client', () => ({
  reportsApi: {
    getAdminUserDetail: (...args: unknown[]) => getAdminUserDetailMock(...args),
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ userId: '101' }),
    useNavigate: () => vi.fn(),
  };
});

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => <div />,
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Pie: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
  Cell: () => <div />,
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <UserDetailPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('UserDetailPage avg hours transparency', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows subtitle and tooltip based on backend metadata', async () => {
    getAdminUserDetailMock.mockResolvedValueOnce({
      user_id: 101,
      user_name: 'Alice Johnson',
      user_email: 'alice@example.com',
      role: 'regular_user',
      teams: [],
      today_seconds: 0,
      today_hours: 0,
      week_seconds: 7200,
      week_hours: 2,
      month_seconds: 18000,
      month_hours: 5,
      total_entries: 3,
      active_days_this_month: 2,
      avg_hours_per_day: 1,
      avg_denominator_days: 5,
      avg_denominator_type: 'working_days_completed',
      avg_includes_today: false,
      avg_working_days_source: 'user',
      avg_working_days_used: [0, 1, 2, 3, 4],
      current_timer_running: false,
      projects: [],
      last_activity: null,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/across 5 completed working days/i)).toBeInTheDocument();
    });

    expect(screen.getByTitle(/Excludes today \(in progress\) and non-working days\./i)).toBeInTheDocument();
    expect(screen.getByTitle(/Working days for this user: Mon-Fri/i)).toBeInTheDocument();
    expect(screen.getByTitle(/\(custom schedule\)/i)).toBeInTheDocument();
  });

  it('falls back gracefully when metadata is absent', async () => {
    getAdminUserDetailMock.mockResolvedValueOnce({
      user_id: 101,
      user_name: 'Alice Johnson',
      user_email: 'alice@example.com',
      role: 'regular_user',
      teams: [],
      today_seconds: 0,
      today_hours: 0,
      week_seconds: 7200,
      week_hours: 2,
      month_seconds: 18000,
      month_hours: 5,
      total_entries: 3,
      active_days_this_month: 2,
      avg_hours_per_day: 1,
      current_timer_running: false,
      projects: [],
      last_activity: null,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/across 2 days/i)).toBeInTheDocument();
    });
  });
});
