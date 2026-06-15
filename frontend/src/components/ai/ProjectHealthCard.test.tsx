import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ProjectHealthResponse } from '../../api/reportingServices';

const refetchMock = vi.fn();
const mutateMock = vi.fn();

const baseFlatResponse: ProjectHealthResponse = {
  success: true,
  enabled: true,
  project_id: 9,
  project_name: 'Apollo',
  health_score: 78,
  health_status: 'at_risk',
  metrics: {
    total_hours: 140,
    this_week_hours: 28,
    last_week_hours: 32,
    activity_trend: 'decreasing',
    total_tasks: 20,
    completed_tasks: 15,
    task_completion_rate: 0.75,
    contributor_count: 3,
  },
  insights: [
    {
      type: 'anomaly' as const,
      severity: 'warning' as const,
      title: 'Completion Pace',
      description: 'Task completion has slowed this week.',
      action_items: ['Review blockers', 'Rebalance assignments'],
    },
  ],
  generated_at: '2026-06-15T10:30:00.000Z',
};

let mockedData: ProjectHealthResponse = { ...baseFlatResponse };

vi.mock('../../hooks/useReportingServices', () => ({
  useAIProjectHealth: () => ({
    data: mockedData,
    isLoading: false,
    isError: false,
    error: null,
    refetch: refetchMock,
  }),
  useAIProjectHealthMutation: () => ({
    mutate: mutateMock,
    isPending: false,
  }),
}));

import ProjectHealthCard from './ProjectHealthCard';

describe('ProjectHealthCard', () => {
  beforeEach(() => {
    refetchMock.mockReset();
    mutateMock.mockReset();
    mockedData = { ...baseFlatResponse };
  });

  it('renders from the flat backend response contract', () => {
    render(<ProjectHealthCard projectId={9} />);

    expect(screen.getByText(/Apollo/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Health score: 78 out of 100/i)).toBeInTheDocument();
    expect(screen.getByText('140.0h')).toBeInTheDocument();
    expect(screen.getByText('28.0h')).toBeInTheDocument();
    expect(screen.getByText('32.0h')).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText(/Task completion has slowed this week\./i)).toBeInTheDocument();
    expect(screen.getByText(/Review blockers/i)).toBeInTheDocument();
    expect(screen.getByText(/Rebalance assignments/i)).toBeInTheDocument();
  });

  it('supports legacy nested health shape during rolling deploy', () => {
    mockedData = {
      success: true,
      enabled: true,
      health: {
        project_id: 9,
        project_name: 'Legacy Apollo',
        health_score: 64,
        status: 'moderate',
        ai_analysis: 'Legacy nested payload still works.',
        recommendations: ['Legacy recommendation'],
        metrics: {
          task_completion_rate: 66,
          activity_trend: 'stable',
        },
        generated_at: '2026-06-15T10:30:00.000Z',
      },
    } as ProjectHealthResponse;

    render(<ProjectHealthCard projectId={9} />);

    expect(screen.getByText(/Legacy Apollo/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Health score: 64 out of 100/i)).toBeInTheDocument();
    expect(screen.getByText(/Legacy nested payload still works\./i)).toBeInTheDocument();
    expect(screen.getByText(/Legacy recommendation/i)).toBeInTheDocument();
  });

  it('returns null when required health fields are absent', () => {
    mockedData = {
      success: true,
      enabled: true,
      project_name: 'Incomplete',
    } as ProjectHealthResponse;

    const { container } = render(<ProjectHealthCard projectId={9} />);
    expect(container.firstChild).toBeNull();
  });
});
