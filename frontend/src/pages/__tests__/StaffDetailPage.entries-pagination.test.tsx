// ============================================
// TIME TRACKER - STAFF DETAIL PAGE
//   ENTRIES TABLE PAGINATION TESTS
// Covers the useInfiniteQuery refactor introduced in
// feat/admin-lists-pagination for the per-staff time-entries list:
//   - initial fetch scoped to user_id + date range, page_size=50,
//   - "Showing X of N entries" indicator renders,
//   - Load More advances pages and disappears at the end,
//   - changing the date range resets pagination to page 1.
//
// The per-staff *analytics* totals already come from the
// server-aggregated endpoint (PR fix/staff-analytics-server-side-
// aggregation); this test file only covers the entries table.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

// Recharts mock — StaffDetailPage renders charts on overview/time tabs.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Pie: () => null,
  Cell: () => null,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
  Area: () => null,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Legend: () => null,
}));

const mockAdmin = {
  id: 1,
  name: 'Admin',
  email: 'admin@example.com',
  role: 'super_admin' as const,
  is_active: true,
  company_id: 1,
  created_at: '2026-01-01T00:00:00Z',
};

vi.mock('../../stores/authStore', () => ({
  useAuthStore: vi.fn(() => ({ user: mockAdmin })),
}));

vi.mock('../../hooks/useStaffNotifications', () => ({
  useStaffNotifications: vi.fn(() => ({
    notifyStaffUpdated: vi.fn(),
    notifyStaffActivated: vi.fn(),
    notifyStaffDeactivated: vi.fn(),
    notifyStaffUpdateFailed: vi.fn(),
    notifyError: vi.fn(),
    notifyWarning: vi.fn(),
    notifyValidationError: vi.fn(),
  })),
}));

vi.mock('../../hooks/usePermissions', () => ({
  usePermissions: vi.fn(() => ({
    canModifyStaff: () => true,
    canDeactivateStaff: () => true,
  })),
}));

vi.mock('../../hooks/useStaffFormValidation', () => ({
  useStaffFormValidation: vi.fn(() => ({
    secureAndValidate: vi.fn(() => ({ valid: true, securedData: {} })),
    hasFieldError: vi.fn(() => false),
    getFieldError: vi.fn(() => ''),
    clearErrors: vi.fn(),
  })),
}));

vi.mock('../../utils/helpers', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../utils/helpers')>();
  return { ...actual, isAdminUser: vi.fn(() => true) };
});

const mockStaff = {
  id: 10,
  name: 'Alice Johnson',
  email: 'alice@company.com',
  role: 'regular_user',
  is_active: true,
  company_id: 1,
  job_title: 'Dev',
  department: 'Eng',
  expected_hours_per_week: 40,
  created_at: '2025-01-15T00:00:00Z',
};

const timeEntriesGetAll = vi.fn();

vi.mock('../../api/client', () => ({
  usersApi: {
    getById: vi.fn(() => Promise.resolve(mockStaff)),
    update: vi.fn(),
    delete: vi.fn(),
  },
  teamsApi: {
    getAll: vi.fn(() =>
      Promise.resolve({ items: [], total: 0, page: 1, page_size: 100, pages: 1 })
    ),
    getById: vi.fn(),
  },
  payRatesApi: {
    getUserCurrentRate: vi.fn(() => Promise.resolve(null)),
    getUserPayRates: vi.fn(() => Promise.resolve([])),
  },
  timeEntriesApi: {
    getAll: (...args: unknown[]) => timeEntriesGetAll(...args),
  },
  reportsApi: {
    getAdminUserAnalytics: vi.fn(() =>
      Promise.resolve({
        user_id: 10,
        total_hours: 0,
        total_entries: 0,
        days_worked: 0,
        project_count: 0,
        projects: [],
      })
    ),
  },
  projectsApi: {
    getAll: vi.fn(() =>
      Promise.resolve({ items: [], total: 0, page: 1, page_size: 100, pages: 1 })
    ),
  },
}));

// Import after mocks
import { StaffDetailPage } from '../StaffDetailPage';

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/staff/10']}>
        <Routes>
          <Route path="/staff/:id" element={<StaffDetailPage />} />
          <Route path="/staff" element={<div>Staff List</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const mkEntry = (id: number, overrides: Record<string, unknown> = {}) => ({
  id,
  user_id: 10,
  project_id: 1,
  project: { name: 'Project Alpha' },
  task: null,
  start_time: '2026-01-08T09:00:00Z',
  end_time: '2026-01-08T10:00:00Z',
  duration_seconds: 3600,
  description: `Entry ${id}`,
  is_billable: true,
  is_running: false,
  ...overrides,
});

async function openTimeTab() {
  const user = userEvent.setup();
  // Wait for the page to settle before clicking the tab.
  await screen.findByText('Alice Johnson');
  const timeTab = screen.getByText(/Time Tracking/i);
  await user.click(timeTab);
}

describe('StaffDetailPage - entries table pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initial fetch uses user_id + date range + page_size=50 and renders "Showing X of N entries"', async () => {
    const page1 = Array.from({ length: 50 }, (_, i) => mkEntry(i + 1));
    timeEntriesGetAll.mockResolvedValue({
      items: page1,
      total: 137,
      page: 1,
      page_size: 50,
      pages: 3,
    });
    renderPage();
    await openTimeTab();

    await waitFor(() => {
      expect(screen.getByTestId('staff-entries-count').textContent).toMatch(
        /Showing 50 of 137 entries/
      );
    });
    // The hook fetches once on mount; subsequent renders may re-call with
    // the same args. Just assert the shape of at least one call.
    expect(timeEntriesGetAll).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: 10,
        page: 1,
        page_size: 50,
        start_date: expect.any(String),
        end_date: expect.any(String),
      })
    );
    expect(screen.getByTestId('staff-entries-load-more')).toBeInTheDocument();
  });

  it('"Load More" advances to the next page; indicator updates; button disappears at end', async () => {
    const user = userEvent.setup();
    const page1 = Array.from({ length: 50 }, (_, i) => mkEntry(i + 1));
    const page2 = Array.from({ length: 20 }, (_, i) => mkEntry(i + 51));
    timeEntriesGetAll
      .mockResolvedValueOnce({
        items: page1,
        total: 70,
        page: 1,
        page_size: 50,
        pages: 2,
      })
      .mockResolvedValueOnce({
        items: page2,
        total: 70,
        page: 2,
        page_size: 50,
        pages: 2,
      });
    renderPage();
    await openTimeTab();
    await screen.findByTestId('staff-entries-load-more');

    await user.click(screen.getByTestId('staff-entries-load-more'));

    await waitFor(() => {
      expect(timeEntriesGetAll).toHaveBeenCalledWith(
        expect.objectContaining({ page: 2, page_size: 50, user_id: 10 })
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId('staff-entries-count').textContent).toMatch(
        /Showing 70 of 70 entries/
      );
    });
    expect(
      screen.queryByTestId('staff-entries-load-more')
    ).not.toBeInTheDocument();
  });

  it('Load More is absent when the first page already contains everything', async () => {
    timeEntriesGetAll.mockResolvedValue({
      items: [mkEntry(1), mkEntry(2)],
      total: 2,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    renderPage();
    await openTimeTab();

    await waitFor(() => {
      expect(screen.getByTestId('staff-entries-count').textContent).toMatch(
        /Showing 2 of 2 entries/
      );
    });
    expect(
      screen.queryByTestId('staff-entries-load-more')
    ).not.toBeInTheDocument();
  });

  it('changing the date range resets to page 1 with the new range', async () => {
    const user = userEvent.setup();
    timeEntriesGetAll.mockResolvedValue({
      items: [mkEntry(1)],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    renderPage();
    await openTimeTab();
    await screen.findByTestId('staff-entries-count');

    // Capture which date pair was used for the initial (month) fetch
    // so we can prove the next fetch uses a different range.
    const initialCall = timeEntriesGetAll.mock.calls.at(-1)?.[0] as {
      start_date: string;
      end_date: string;
    };
    timeEntriesGetAll.mockClear();

    await user.click(screen.getByRole('button', { name: /last week/i }));

    await waitFor(() => {
      expect(timeEntriesGetAll).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 1,
          page_size: 50,
          user_id: 10,
        })
      );
    });
    const newCall = timeEntriesGetAll.mock.calls.at(-1)?.[0] as {
      start_date: string;
    };
    // Last-week start_date must differ from the previous (month) range.
    expect(newCall.start_date).not.toBe(initialCall.start_date);
  });
});
