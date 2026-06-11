// ============================================
// TIME TRACKER - DASHBOARD PAGE POLLING TEST
// ============================================
import { describe, it, expect, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const capturedQueries: unknown[] = [];

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
  return {
    ...actual,
    useQuery: vi.fn((options: { queryKey?: unknown[] }) => {
      capturedQueries.push(options);
      const queryKey = Array.isArray(options?.queryKey) ? options.queryKey[0] : undefined;
      if (queryKey === 'dashboard') {
        return { data: { today_seconds: 0, week_seconds: 0, month_seconds: 0, active_projects: 0 }, isLoading: false, dataUpdatedAt: 0 };
      }
      if (queryKey === 'admin-dashboard') {
        return { data: null, isLoading: false, dataUpdatedAt: 0 };
      }
      if (queryKey === 'weekly-summary') {
        return { data: { daily_breakdown: [] }, isLoading: false, dataUpdatedAt: 0 };
      }
      if (queryKey === 'project-report-dashboard') {
        return { data: [], isLoading: false, dataUpdatedAt: 0 };
      }
      return { data: null, isLoading: false, dataUpdatedAt: 0 };
    }),
    useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
  };
});

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({
    user: {
      id: 1,
      email: 'user@test.com',
      name: 'Test User',
      role: 'user',
      company_id: 1,
    },
    isAuthenticated: true,
  })),
}));

vi.mock('../hooks/useAIFeatures', () => ({
  useFeatureEnabled: vi.fn(() => ({ data: false })),
}));

vi.mock('../contexts/WebSocketContext', () => ({
  WebSocketProvider: ({ children }: { children: React.ReactNode }) => children,
  useWebSocketContext: vi.fn(() => ({
    isConnected: false,
    activeTimers: [],
    connectionState: 'disconnected',
  })),
}));

vi.mock('../components/Notifications', () => ({
  NotificationProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('../contexts/BrandingContext', () => ({
  BrandingProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('../components/common', () => ({
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardHeader: ({ title }: { title: string }) => <div>{title}</div>,
  LoadingOverlay: ({ message }: { message: string }) => <div>{message}</div>,
}));

vi.mock('../components/time/TimerWidget', () => ({
  TimerWidget: () => <div data-testid="timer-widget" />,
}));

vi.mock('../components/time/LongTimerBanner', () => ({
  LongTimerBanner: () => <div data-testid="long-timer-banner" />,
}));

vi.mock('../components/sessions', () => ({
  SessionWidget: () => <div data-testid="session-widget" />,
}));

vi.mock('../components/ActiveTimers', () => ({
  ActiveTimers: () => <div data-testid="active-timers" />,
}));

vi.mock('../components/AdminAlertsPanel', () => ({
  AdminAlertsPanel: () => <div data-testid="admin-alerts" />,
}));

vi.mock('../components/ai/AnomalyAlertPanel', () => ({
  AnomalyAlertPanel: () => <div data-testid="anomaly-alerts" />,
}));

vi.mock('../components/ai/WeeklySummaryPanel', () => ({
  default: () => <div data-testid="weekly-summary" />,
}));

vi.mock('../components/ai/UserInsightsPanel', () => ({
  default: () => <div data-testid="user-insights" />,
}));

vi.mock('../stores/timerStore', () => {
  const mockTimerState = {
    currentEntry: null,
    isRunning: false,
    isPaused: false,
    elapsedSeconds: 0,
    isLoading: false,
    error: null,
    lastSyncTime: null,
    fetchTimer: vi.fn(() => Promise.resolve()),
    startTimer: vi.fn(() => Promise.resolve()),
    stopTimer: vi.fn(() => Promise.resolve(null)),
    switchTimer: vi.fn(() => Promise.resolve()),
    updateElapsed: vi.fn(),
    clearError: vi.fn(),
    syncWithBackend: vi.fn(() => Promise.resolve()),
    applyServerState: vi.fn(),
  };

  return {
    useTimerStore: vi.fn().mockImplementation((selector?: (state: typeof mockTimerState) => unknown) => {
      if (typeof selector === 'function') {
        return selector(mockTimerState);
      }
      return mockTimerState;
    }),
  };
});

vi.mock('../stores/sessionStore', () => {
  const mockSessionState = {
    currentSession: null,
    activeBreak: null,
    activeMeeting: null,
    isLoading: false,
    error: null,
    sessionElapsedSeconds: 0,
    breakElapsedSeconds: 0,
    meetingElapsedSeconds: 0,
    fetchCurrentSession: vi.fn(() => Promise.resolve()),
    startSession: vi.fn(() => Promise.resolve()),
    endSession: vi.fn(() => Promise.resolve()),
    updateElapsedTimes: vi.fn(),
    clearError: vi.fn(),
    getSessionStatusInfo: vi.fn(),
  };

  return {
    useSessionStore: vi.fn().mockImplementation((selector?: (state: typeof mockSessionState) => unknown) => {
      if (typeof selector === 'function') {
        return selector(mockSessionState);
      }
      return mockSessionState;
    }),
    formatDuration: (seconds: number) => `${seconds}s`,
    getSessionStatusInfo: vi.fn(),
  };
});

vi.mock('../api/client', () => ({
  reportsApi: {
    getDashboard: vi.fn(() => Promise.resolve({ today_seconds: 0, week_seconds: 0, month_seconds: 0, active_projects: 0 })),
    getAdminDashboard: vi.fn(() => Promise.resolve(null)),
    getWeekly: vi.fn(() => Promise.resolve({ daily_breakdown: [] })),
    getByProject: vi.fn(() => Promise.resolve([])),
  },
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Pie: () => <div />,
  Cell: () => <div />,
}));

import { DashboardPage } from './DashboardPage';

const renderDashboard = () => render(
  <MemoryRouter>
    <DashboardPage />
  </MemoryRouter>
);

describe('DashboardPage polling', () => {
  it('configures the dashboard query with a 60s refetch interval', async () => {
    renderDashboard();

    await waitFor(() => {
      const dashboardQuery = capturedQueries.find(
        (query) => Array.isArray((query as { queryKey?: unknown[] }).queryKey) && (query as { queryKey?: unknown[] }).queryKey?.[0] === 'dashboard'
      ) as { refetchInterval?: number } | undefined;

      expect(dashboardQuery).toBeDefined();
      expect(dashboardQuery?.refetchInterval).toBe(60_000);
    });
  });
});
