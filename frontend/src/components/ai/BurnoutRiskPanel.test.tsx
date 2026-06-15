import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const assessBurnoutRiskMock = vi.fn();

vi.mock('../../api/aiServices', () => ({
  aiApi: {
    assessBurnoutRisk: (...args: unknown[]) => assessBurnoutRiskMock(...args),
  },
}));

import BurnoutRiskPanel from './BurnoutRiskPanel';

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe('BurnoutRiskPanel', () => {
  beforeEach(() => {
    assessBurnoutRiskMock.mockReset();
  });

  it('renders insufficient-data honesty copy when insufficient_data is true', async () => {
    assessBurnoutRiskMock.mockResolvedValue({
      success: true,
      insufficient_data: true,
      min_work_days_threshold: 3,
      recommendations: ['Log at least 3 working days to receive a burnout assessment'],
    });

    renderWithQueryClient(<BurnoutRiskPanel periodDays={30} />);

    expect(await screen.findByText('Not enough data to assess yet')).toBeInTheDocument();
    expect(screen.getByText('Need at least 3 working days of logged time')).toBeInTheDocument();
    expect(screen.queryByText('Risk Factors')).toBeNull();
    expect(screen.queryByText('💡 Recommendations')).toBeNull();
  });

  it('renders existing burnout assessment details when insufficient_data is false', async () => {
    assessBurnoutRiskMock.mockResolvedValue({
      success: true,
      insufficient_data: false,
      user_name: 'Alex',
      risk_level: 'low',
      risk_score: 12,
      trend: 'stable',
      factors: [
        {
          name: 'Overtime Frequency',
          score: 0,
          max_score: 30,
          detail: '0 overtime days out of 5 work days',
        },
      ],
      recommendations: ['Keep maintaining your healthy work patterns'],
      assessed_at: '2026-06-15T12:00:00.000Z',
    });

    renderWithQueryClient(<BurnoutRiskPanel periodDays={30} />);

    expect(await screen.findByText('Low Risk')).toBeInTheDocument();
    expect(screen.getByText('Risk Factors')).toBeInTheDocument();
    expect(screen.getByText('💡 Recommendations')).toBeInTheDocument();
  });

  it('gracefully falls back to existing behavior when insufficient_data flag is missing', async () => {
    assessBurnoutRiskMock.mockResolvedValue({
      success: true,
      user_name: 'Alex',
      risk_level: 'moderate',
      risk_score: 34,
      trend: 'worsening',
      factors: [],
      recommendations: ['Set boundaries for work hours to avoid late-night work'],
      assessed_at: '2026-06-15T12:00:00.000Z',
    });

    renderWithQueryClient(<BurnoutRiskPanel periodDays={30} />);

    expect(await screen.findByText('Moderate Risk')).toBeInTheDocument();
    expect(screen.queryByText('Not enough data to assess yet')).toBeNull();
  });
});
