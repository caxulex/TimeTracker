// ============================================
// TIME TRACKER - REPORTS PAGE WEEKLY-WINDOW TEST
// --------------------------------------------
// Regression coverage for the 2026-05-14 hotfix that taught the top
// stats card (Total Hours, Avg Hours/Day, Daily Hours chart) to honor
// the user-selected end date instead of being silently truncated to a
// 7-day window by the backend.
//
// Specifically verifies:
//   1. Changing only the custom end date causes reportsApi.getWeekly to
//      be re-invoked with the new end_date (i.e. the React Query key
//      includes endDate).
//   2. The "across N days" label reflects the actual daily_breakdown
//      length returned by the backend, so a 15-day range reads
//      "across 15 days".
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReportsPage } from '../ReportsPage';
import { useAuthStore } from '../../stores/authStore';

vi.mock('../../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('../../contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({ lastMessage: null }),
}));

vi.mock('../../hooks/useStaffNotifications', () => ({
  useStaffNotifications: () => ({
    notifySuccess: vi.fn(),
    notifyError: vi.fn(),
  }),
}));

vi.mock('../../components/reports', () => ({
  TeamTimesheetReport: () => null,
}));

const getWeekly = vi.fn();
const getByProject = vi.fn();

vi.mock('../../api/client', () => ({
  reportsApi: {
    getWeekly: (...args: unknown[]) => getWeekly(...args),
    getByProject: (...args: unknown[]) => getByProject(...args),
  },
  exportApi: {
    downloadCsv: vi.fn(),
    downloadExcel: vi.fn(),
    downloadPdf: vi.fn(),
  },
}));

const mockedAuth = useAuthStore as unknown as ReturnType<typeof vi.fn>;

function makeDailyBreakdown(startISO: string, days: number) {
  const start = new Date(startISO + 'T12:00:00Z');
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(start);
    d.setUTCDate(start.getUTCDate() + i);
    return {
      date: d.toISOString().slice(0, 10),
      total_seconds: 0,
      total_hours: 0,
      entry_count: 0,
    };
  });
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ReportsPage - weekly window honors custom end date', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAuth.mockReturnValue({
      user: { id: 1, email: 'u@example.com', name: 'U', role: 'regular_user' },
      isAuthenticated: true,
    });
    getByProject.mockResolvedValue([]);
    // Default response — overridden per-test as needed.
    getWeekly.mockResolvedValue({
      week_start: '2026-05-01',
      week_end: '2026-05-15',
      total_seconds: 0,
      total_hours: 0,
      daily_breakdown: makeDailyBreakdown('2026-05-01', 15),
    });
  });

  it('passes end_date to reportsApi.getWeekly and refetches when only end_date changes', async () => {
    const user = userEvent.setup();
    renderPage();

    // Switch to Custom range
    await user.click(screen.getByRole('button', { name: /custom/i }));

    const inputs = await screen.findAllByDisplayValue('');
    const dateInputs = inputs.filter(
      (el) => (el as HTMLInputElement).type === 'date'
    ) as HTMLInputElement[];
    expect(dateInputs).toHaveLength(2);
    const [startInput, endInput] = dateInputs;

    await user.type(startInput, '2026-05-01');
    await user.type(endInput, '2026-05-07');

    await waitFor(() => {
      expect(getWeekly).toHaveBeenCalledWith('2026-05-01', '2026-05-07');
    });

    // Now change ONLY the end date — must refetch with the new end_date.
    getWeekly.mockClear();
    await user.clear(endInput);
    await user.type(endInput, '2026-05-15');

    await waitFor(() => {
      expect(getWeekly).toHaveBeenCalledWith('2026-05-01', '2026-05-15');
    });
  });

  it('shows "across N days" matching the daily_breakdown length for a 15-day range', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: /custom/i }));
    const dateInputs = (await screen.findAllByDisplayValue('')).filter(
      (el) => (el as HTMLInputElement).type === 'date'
    ) as HTMLInputElement[];
    await user.type(dateInputs[0], '2026-05-01');
    await user.type(dateInputs[1], '2026-05-15');

    await waitFor(() => {
      expect(screen.getByText(/across 15 days/i)).toBeInTheDocument();
    });
  });

  it('uses backend avg_hours_per_day and shows metadata subtitle and tooltip', async () => {
    getWeekly.mockResolvedValueOnce({
      week_start: '2026-05-01',
      week_end: '2026-05-07',
      total_seconds: 36000,
      total_hours: 10,
      avg_hours_per_day: 6.2,
      avg_denominator_days: 5,
      avg_denominator_type: 'working_days_completed',
      avg_includes_today: false,
      avg_working_days_source: 'user',
      avg_working_days_used: [0, 1, 2, 3, 4],
      daily_breakdown: makeDailyBreakdown('2026-05-01', 7),
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('6.2h')).toBeInTheDocument();
      expect(screen.getByText(/across 5 completed working days/i)).toBeInTheDocument();
    });

    expect(
      screen.getByTitle(/Excludes today \(in progress\) and non-working days\./i),
    ).toBeInTheDocument();
    expect(screen.getByTitle(/Working days for this user: Mon-Fri/i)).toBeInTheDocument();
    expect(screen.getByTitle(/\(custom schedule\)/i)).toBeInTheDocument();
  });

  it('falls back gracefully when avg metadata is absent', async () => {
    getWeekly.mockResolvedValueOnce({
      week_start: '2026-05-01',
      week_end: '2026-05-07',
      total_seconds: 36000,
      total_hours: 10,
      daily_breakdown: makeDailyBreakdown('2026-05-01', 7),
    });

    renderPage();

    await waitFor(() => {
      // Legacy fallback path: 10h across 7 days => 1.4h
      expect(screen.getByText('1.4h')).toBeInTheDocument();
      expect(screen.getByText(/across 7 days/i)).toBeInTheDocument();
    });
  });
});
