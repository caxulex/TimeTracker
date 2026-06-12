import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import AdminReportsPage from './AdminReportsPage';

vi.mock('../hooks/useAIFeatures', () => ({
  useFeatureEnabled: () => ({ data: false }),
}));

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn((selector: (state: { user: unknown }) => unknown) =>
    selector({
      user: {
        id: 1,
        name: 'Admin User',
        email: 'admin@example.com',
        role: 'super_admin',
        is_active: true,
      },
    })
  ),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Bar: () => <div />,
  PieChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Pie: () => <div />,
  LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Line: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
  Cell: () => <div />,
}));

const createClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
    },
  });

const renderPage = () => {
  const client = createClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AdminReportsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('AdminReportsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input);

        if (url.includes('/api/reports/admin/dashboard')) {
          return {
            ok: true,
            json: async () => ({
              total_today_seconds: 0,
              total_today_hours: 0,
              total_week_seconds: 0,
              total_week_hours: 0,
              total_month_seconds: 0,
              total_month_hours: 0,
              active_users_today: 0,
              active_projects: 0,
              running_timers: 0,
              by_user: [],
            }),
          } as Response;
        }

        if (url.includes('/api/reports/admin/teams')) {
          return {
            ok: true,
            json: async () => [],
          } as Response;
        }

        if (url.includes('/api/reports/admin/users?period=week&page=1&page_size=50')) {
          return {
            ok: true,
            json: async () => ({
              data: [
                {
                  user_id: 101,
                  user_name: 'Alice Johnson',
                  user_email: 'alice@example.com',
                  total_seconds: 14400,
                  total_hours: 4,
                  entry_count: 3,
                },
                {
                  user_id: 102,
                  user_name: 'Bob Stone',
                  user_email: 'bob@example.com',
                  total_seconds: 7200,
                  total_hours: 2,
                  entry_count: 2,
                },
              ],
              total: 2,
              page: 1,
              page_size: 50,
              has_next: false,
              has_prev: false,
              total_pages: 1,
            }),
          } as Response;
        }

        if (url.includes('/api/reports/admin/users?period=week')) {
          return {
            ok: true,
            json: async () => [
              {
                user_id: 101,
                user_name: 'Alice Johnson',
                user_email: 'alice@example.com',
                total_seconds: 14400,
                total_hours: 4,
                entry_count: 3,
              },
              {
                user_id: 102,
                user_name: 'Bob Stone',
                user_email: 'bob@example.com',
                total_seconds: 7200,
                total_hours: 2,
                entry_count: 2,
              },
            ],
          } as Response;
        }

        if (url.includes('/api/reports/admin/users/101')) {
          return {
            ok: true,
            json: async () => ({
              user_id: 101,
              user_name: 'Alice Johnson',
              user_email: 'alice@example.com',
              role: 'regular_user',
              teams: [],
              today_seconds: 0,
              today_hours: 0,
              week_seconds: 14400,
              week_hours: 4,
              month_seconds: 30000,
              month_hours: 8.33,
              total_entries: 3,
              active_days_this_month: 2,
              avg_hours_per_day: 2,
              avg_denominator_days: 5,
              avg_denominator_type: 'working_days_completed',
              avg_includes_today: false,
              avg_working_days_source: 'company',
              avg_working_days_used: [0, 1, 2, 3, 4],
              current_timer_running: false,
              projects: [],
              last_activity: null,
            }),
          } as Response;
        }

        return {
          ok: true,
          json: async () => [],
        } as Response;
      })
    );
  });

  it('renders UserSelect on Individuals tab, filters by typing, and propagates selection', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: /individuals/i }));

    const staffInput = await screen.findByLabelText(/select staff/i);
    await user.click(staffInput);
    await user.type(staffInput, 'ali');

    expect(await screen.findByTestId('user-select-option-101')).toBeInTheDocument();
    expect(screen.queryByTestId('user-select-option-102')).not.toBeInTheDocument();

    fireEvent.mouseDown(screen.getByTestId('user-select-option-101'));

    await waitFor(() => {
      expect(screen.getByText(/alice johnson's performance details/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/across 5 completed working days/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Working days for this user: Mon-Fri/i)).toBeInTheDocument();
    expect(screen.getByTitle(/\(company schedule\)/i)).toBeInTheDocument();
  });
});
