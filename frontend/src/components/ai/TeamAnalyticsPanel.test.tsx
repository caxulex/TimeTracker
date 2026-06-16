import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import TeamAnalyticsPanel from './TeamAnalyticsPanel';

const getTeamAnalyticsMock = vi.fn();

vi.mock('../../api/aiServices', () => ({
  getTeamAnalytics: (...args: unknown[]) => getTeamAnalyticsMock(...args),
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Line: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  BarChart: ({
    children,
    data,
  }: {
    children: ReactNode;
    data?: Array<{ name: string; hours: number }>;
  }) => (
    <div>
      <div data-testid="mock-workload-bars">{(data ?? []).map((item) => item.name).join('|')}</div>
      {children}
    </div>
  ),
  Bar: () => <div />,
}));

const renderPanel = () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={client}>
      <TeamAnalyticsPanel teamId={7} teamName="Core Team" />
    </QueryClientProvider>
  );
};

const baseResponse = {
  success: true,
  team_id: 7,
  team_name: 'Core Team',
  period_days: 30,
  total_members: 4,
  active_members: 3,
  total_hours: 120,
  avg_hours_per_member: 30,
  total_projects: 5,
  total_tasks: 44,
  current_velocity_trend: 'increasing' as const,
  collaboration_density: 0.62,
  workload_gini: 0.31,
  generated_at: '2026-06-16T10:00:00.000Z',
};

describe('TeamAnalyticsPanel', () => {
  beforeEach(() => {
    getTeamAnalyticsMock.mockReset();
  });

  it('shows loading state while fetching', () => {
    getTeamAnalyticsMock.mockReturnValue(new Promise(() => undefined));

    renderPanel();

    expect(screen.getByText(/loading team analytics/i)).toBeInTheDocument();
  });

  it('shows error state when request fails', async () => {
    getTeamAnalyticsMock.mockRejectedValue(new Error('request failed'));

    renderPanel();

    expect(
      await screen.findByText(/request failed/i, {}, { timeout: 3000 })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('surfaces backend error when success is false', async () => {
    getTeamAnalyticsMock.mockResolvedValue({
      ...baseResponse,
      success: false,
      error: 'Team 9999 not found. It may have been deleted.',
    });

    renderPanel();

    expect(
      await screen.findByText(/team 9999 not found\. it may have been deleted\./i)
    ).toBeInTheDocument();
  });

  it('shows empty state when total members is zero', async () => {
    getTeamAnalyticsMock.mockResolvedValue({
      ...baseResponse,
      total_members: 0,
      active_members: 0,
      total_hours: 0,
      avg_hours_per_member: 0,
      total_projects: 0,
      total_tasks: 0,
    });

    renderPanel();

    expect(await screen.findByText(/no team members available for analytics/i)).toBeInTheDocument();
  });

  it('renders fallback blocks for missing optional arrays', async () => {
    getTeamAnalyticsMock.mockResolvedValue({
      ...baseResponse,
      member_metrics: [],
      velocity_history: [],
      top_contributors: [],
      collaboration_edges: [],
      underutilized_members: [],
      ai_insights: [],
      recommendations: [],
    });

    renderPanel();

    expect(await screen.findByTestId('team-analytics-panel')).toBeInTheDocument();
    expect(screen.getByText(/no velocity history available/i)).toBeInTheDocument();
    expect(screen.getByText(/no member workload data available/i)).toBeInTheDocument();
    expect(screen.getByText(/no collaboration edge data available/i)).toBeInTheDocument();
    expect(screen.getByText(/no underutilization signals available/i)).toBeInTheDocument();
  });

  it('renders workload bars for all member metrics, not only top contributors', async () => {
    getTeamAnalyticsMock.mockResolvedValue({
      ...baseResponse,
      member_metrics: [
        { user_id: 1, user_name: 'Joe Bello', total_hours: 180, avg_daily_hours: 6, productive_hours_ratio: 0.9, projects_worked: 3, tasks_completed: 20, consistency_score: 88, overtime_hours: 4, weekend_hours: 2 },
        { user_id: 2, user_name: 'Daniel', total_hours: 146, avg_daily_hours: 4.9, productive_hours_ratio: 0.88, projects_worked: 3, tasks_completed: 18, consistency_score: 86, overtime_hours: 3, weekend_hours: 1 },
        { user_id: 3, user_name: 'Jelry', total_hours: 133, avg_daily_hours: 4.4, productive_hours_ratio: 0.87, projects_worked: 2, tasks_completed: 16, consistency_score: 84, overtime_hours: 2, weekend_hours: 1 },
      ],
      top_contributors: [{ user_id: 1, name: 'Joe Bello', hours: 180 }],
      velocity_history: [],
      underutilized_members: [],
      collaboration_edges: [],
      ai_insights: [],
      recommendations: [],
    });

    renderPanel();

    await screen.findByTestId('team-analytics-panel');
    expect(screen.getByTestId('mock-workload-bars')).toHaveTextContent('Joe Bello|Daniel|Jelry');
  });

  it('renders a single workload bar for single-member teams', async () => {
    getTeamAnalyticsMock.mockResolvedValue({
      ...baseResponse,
      total_members: 1,
      active_members: 1,
      member_metrics: [
        { user_id: 7, user_name: 'Solo Dev', total_hours: 96, avg_daily_hours: 3.2, productive_hours_ratio: 0.92, projects_worked: 2, tasks_completed: 11, consistency_score: 90, overtime_hours: 0, weekend_hours: 0 },
      ],
      top_contributors: [{ user_id: 7, name: 'Solo Dev', hours: 96 }],
      velocity_history: [],
      underutilized_members: [],
      collaboration_edges: [],
      ai_insights: [],
      recommendations: [],
    });

    renderPanel();

    await screen.findByTestId('team-analytics-panel');
    expect(screen.getByTestId('mock-workload-bars')).toHaveTextContent('Solo Dev');
  });

  it('renders metrics, insights, and recommendations on success', async () => {
    getTeamAnalyticsMock.mockResolvedValue({
      ...baseResponse,
      member_metrics: [
        { user_id: 1, user_name: 'Alice', total_hours: 42, avg_daily_hours: 1.4, productive_hours_ratio: 0.9, projects_worked: 2, tasks_completed: 10, consistency_score: 80, overtime_hours: 2, weekend_hours: 1 },
        { user_id: 2, user_name: 'Bob', total_hours: 35, avg_daily_hours: 1.2, productive_hours_ratio: 0.88, projects_worked: 2, tasks_completed: 9, consistency_score: 78, overtime_hours: 1, weekend_hours: 0 },
      ],
      velocity_history: [
        {
          period_start: '2026-06-01T00:00:00.000Z',
          period_end: '2026-06-07T00:00:00.000Z',
          total_hours: 35,
          hours_per_member: 8.75,
          tasks_completed: 12,
          projects_active: 3,
          avg_task_duration_hours: 2.2,
          velocity_trend: 'increasing',
          change_percent: 7.5,
        },
      ],
      top_contributors: [
        { user_id: 1, name: 'Alice', hours: 42 },
        { user_id: 2, name: 'Bob', hours: 35 },
      ],
      underutilized_members: [{ user_id: 3, name: 'Charlie', hours: 8 }],
      collaboration_edges: [
        {
          user1_id: 1,
          user1_name: 'Alice',
          user2_id: 2,
          user2_name: 'Bob',
          shared_projects: 3,
          interaction_score: 0.8,
        },
      ],
      ai_insights: ['Team velocity has increased by 7.5% week over week.'],
      recommendations: ['Rotate ownership to sustain delivery pace.'],
    });

    renderPanel();

    expect(await screen.findByText(/ai team analytics: core team/i)).toBeInTheDocument();
    expect(screen.getByText('120.0h')).toBeInTheDocument();
    expect(screen.getByText('3/4')).toBeInTheDocument();
    expect(screen.getByText('Increasing')).toBeInTheDocument();
    expect(screen.getByText(/team velocity has increased/i)).toBeInTheDocument();
    expect(screen.getByText(/rotate ownership to sustain delivery pace/i)).toBeInTheDocument();
  });
});
