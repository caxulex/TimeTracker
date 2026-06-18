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
    completion_measured: true,
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

const insufficientResponse: ProjectHealthResponse = {
  success: true,
  enabled: true,
  project_id: 9,
  project_name: 'Aloha',
  insufficient_data: true,
  data_thresholds: {
    min_hours: 5,
    min_tasks: 5,
  },
  metrics: {
    total_hours: 1.1,
    this_week_hours: 1.1,
    last_week_hours: 0,
    activity_trend: 'new',
    total_tasks: 0,
    completed_tasks: 0,
    task_completion_rate: 0,
    completion_measured: false,
    contributor_count: 1,
  },
  insights: [
    {
      type: 'anomaly' as const,
      severity: 'info' as const,
      title: 'Not enough activity to assess yet',
      description: "Project doesn't have enough activity yet to assess.",
      action_items: [
        'Need at least 5 hours of logged work OR 5 defined tasks to provide a health assessment.',
      ],
    },
  ],
  recommendations: [
    'Need at least 5 hours of logged work OR 5 defined tasks to provide a health assessment.',
  ],
  generated_at: '2026-06-16T10:30:00.000Z',
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

  it('renders the insufficient-activity state when the backend marks sparse data', () => {
    mockedData = insufficientResponse;

    render(<ProjectHealthCard projectId={9} />);

    expect(screen.getByText(/Not enough activity to assess yet/i)).toBeInTheDocument();
    expect(screen.getByText(/Need at least 5 hours of logged work OR 5 defined tasks/i)).toBeInTheDocument();
    expect(screen.getAllByText('1.1h')).toHaveLength(2);
    expect(screen.getByText(/Not tracked/i)).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Health score:/i)).toBeNull();
    expect(screen.queryByText(/Recommendations/i)).toBeNull();
  });

  it('renders completion as not tracked when completion_measured is false', () => {
    mockedData = {
      ...baseFlatResponse,
      metrics: {
        ...baseFlatResponse.metrics!,
        task_completion_rate: 0,
        completion_measured: false,
      },
      insights: [],
    };

    render(<ProjectHealthCard projectId={9} />);

    expect(screen.getByText(/Not tracked/i)).toBeInTheDocument();
    expect(screen.queryByText('0%')).toBeNull();
  });

  it('keeps the existing render path when the insufficient_data flag is missing', () => {
    mockedData = {
      success: true,
      enabled: true,
      project_id: 9,
      project_name: 'Fallback Apollo',
      health_score: 61,
      health_status: 'moderate',
      metrics: {
        total_hours: 5,
        this_week_hours: 2,
        last_week_hours: 3,
        activity_trend: 'stable',
        total_tasks: 2,
        completed_tasks: 1,
        task_completion_rate: 0.5,
        contributor_count: 2,
      },
      insights: [],
      generated_at: '2026-06-16T10:30:00.000Z',
    } as ProjectHealthResponse;

    render(<ProjectHealthCard projectId={9} />);

    expect(screen.getByText(/Fallback Apollo/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Health score: 61 out of 100/i)).toBeInTheDocument();
    expect(screen.queryByText(/Not enough activity to assess yet/i)).toBeNull();
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
