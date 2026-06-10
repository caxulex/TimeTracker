import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const refetchMock = vi.fn();
const mutateMock = vi.fn();

const baseResponse = {
  success: true,
  enabled: true,
  user_id: 5,
  metrics: {
    user_name: 'Ana',
    expected_hours: 40,
    total_hours_30d: 152,
    avg_daily_hours: 7.6,
    active_projects: 4,
    productivity_trend: 'improving' as const,
  },
  insights: [
    {
      type: 'productivity' as const,
      severity: 'info' as const,
      title: 'Improving Productivity',
      description: 'Time logging consistency has improved',
      action_items: [],
    },
    {
      type: 'workload' as const,
      severity: 'warning' as const,
      title: 'High Work Hours',
      description: 'Average 10.2 hours/day - consider workload review',
      action_items: ['Review task priorities', 'Consider delegation'],
    },
  ],
  generated_at: '2026-06-10T10:30:00.000Z',
};

let mockedData: typeof baseResponse = { ...baseResponse };

vi.mock('../../hooks/useReportingServices', () => ({
  useAIUserInsights: () => ({
    data: mockedData,
    isLoading: false,
    isError: false,
    error: null,
    refetch: refetchMock,
  }),
  useAIUserInsightsMutation: () => ({
    mutate: mutateMock,
    isPending: false,
  }),
}));

import UserInsightsPanel from './UserInsightsPanel';

describe('UserInsightsPanel', () => {
  beforeEach(() => {
    refetchMock.mockReset();
    mutateMock.mockReset();
    mockedData = { ...baseResponse };
  });

  it('renders insights from flat backend response contract', () => {
    render(<UserInsightsPanel periodDays={30} />);

    expect(screen.getByText(/Your Insights/i)).toBeInTheDocument();
    expect(screen.getByText(/Ana/i)).toBeInTheDocument();
    expect(screen.getByText('152h')).toBeInTheDocument();
    expect(screen.getByText('7.6h')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('40h')).toBeInTheDocument();
    expect(screen.getByText('Improving')).toBeInTheDocument();
    expect(screen.getAllByText(/Time logging consistency has improved/i).length).toBeGreaterThan(0);
  });

  it('renders warning-derived improvement areas and action recommendations', () => {
    render(<UserInsightsPanel periodDays={30} />);

    expect(screen.getByText(/Areas to Improve/i)).toBeInTheDocument();
    expect(screen.getByText(/Average 10.2 hours\/day - consider workload review/i)).toBeInTheDocument();
    expect(screen.getByText(/Recommendations/i)).toBeInTheDocument();
    expect(screen.getByText(/Review task priorities/i)).toBeInTheDocument();
    expect(screen.getByText(/Consider delegation/i)).toBeInTheDocument();
  });

  it('returns null when metrics are missing (no blank card shell)', () => {
    mockedData = {
      ...baseResponse,
      metrics: undefined,
    } as unknown as typeof baseResponse;

    const { container } = render(<UserInsightsPanel periodDays={30} />);
    expect(container.firstChild).toBeNull();
  });
});
