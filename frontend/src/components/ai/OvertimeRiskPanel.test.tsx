import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const useOvertimeRiskMock = vi.fn();
const useOvertimeRiskMutationMock = vi.fn();

vi.mock('../../hooks/useForecastingServices', () => ({
  useOvertimeRisk: (...args: unknown[]) => useOvertimeRiskMock(...args),
  useOvertimeRiskMutation: () => useOvertimeRiskMutationMock(),
}));

import { OvertimeRiskPanel } from './OvertimeRiskPanel';

describe('OvertimeRiskPanel', () => {
  beforeEach(() => {
    useOvertimeRiskMock.mockReset();
    useOvertimeRiskMutationMock.mockReset();

    useOvertimeRiskMutationMock.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    });

    useOvertimeRiskMock.mockReturnValue({
      data: {
        enabled: true,
        period: '2026-06-10 to 2026-06-16',
        users_assessed: 4,
        users_at_risk: 1,
        generated_at: '2026-06-10T10:30:00.000Z',
        risks: [
          {
            user_id: 9,
            user_name: 'Jordan',
            current_hours: 38.5,
            projected_hours: 46.2,
            overtime_threshold: 40,
            risk_level: 'high',
            projected_overtime: 6.2,
            estimated_cost: 186.0,
            recommendation: 'Review workload distribution',
          },
        ],
      },
      isLoading: false,
      error: null,
    });
  });

  it('requests the weekly horizon and does not expose unsupported longer options', () => {
    render(<OvertimeRiskPanel />);

    expect(useOvertimeRiskMock).toHaveBeenCalledWith({ days_ahead: 7, team_id: undefined });
    expect(screen.getByText(/Forecast horizon: current week only/i)).toBeInTheDocument();
    expect(screen.getByText(/Hours this week/i)).toBeInTheDocument();
    expect(screen.queryByText(/Next 2 weeks/i)).toBeNull();
    expect(screen.queryByText(/This month/i)).toBeNull();
  });
});
