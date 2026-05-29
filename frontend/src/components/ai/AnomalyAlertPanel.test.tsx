// ============================================
// TIME TRACKER - ANOMALY ALERT PANEL TESTS
// Covers the dismiss-failure user-facing error path added in
// fix/anomaly-dismissal-persistence: the legacy flow silently
// closed the modal even when the backend swallowed a persistence
// failure. With the new backend returning HTTP 500 on failure, the
// frontend must show an inline error to the admin.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// ----- Mock the AI hooks layer -----
const refetchMock = vi.fn();
const scanMock = vi.fn();
const dismissMutateMock = vi.fn();

vi.mock('../../hooks/useAIServices', () => ({
  useAllAnomalies: () => ({
    data: {
      anomalies: [
        {
          type: 'extended_day',
          severity: 'warning',
          user_id: 42,
          user_name: 'Target User',
          description: 'Worked 13h on Monday',
          detected_at: new Date().toISOString(),
          details: {},
          recommendation: null,
        },
      ],
      statistics: {
        users_scanned: 1,
        users_with_anomalies: 1,
        total_anomalies: 1,
        critical_count: 0,
        warning_count: 1,
        info_count: 0,
      },
    },
    isLoading: false,
    error: null,
    refetch: refetchMock,
  }),
  useAnomalyScan: () => ({ mutate: scanMock, isPending: false }),
  useDismissAnomaly: () => ({
    mutate: dismissMutateMock,
    isPending: false,
  }),
}));

import { AnomalyAlertPanel } from './AnomalyAlertPanel';

describe('AnomalyAlertPanel - dismiss error path', () => {
  beforeEach(() => {
    refetchMock.mockReset();
    scanMock.mockReset();
    dismissMutateMock.mockReset();
  });

  it('shows a user-facing error when the dismiss mutation fails', async () => {
    // Simulate the new backend behaviour: HTTP 500 surfaces through
    // react-query as an onError callback. The panel must render an
    // inline error instead of silently closing.
    dismissMutateMock.mockImplementation((_payload, options) => {
      options?.onError?.(new Error('Request failed with status code 500'));
    });

    render(<AnomalyAlertPanel isAdmin periodDays={7} />);

    // Open the dismiss modal for the seeded anomaly.
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    // Confirm dismissal.
    const confirmButtons = screen.getAllByRole('button', { name: /dismiss/i });
    // Last button is the modal's confirm button (panel row button is first).
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(dismissMutateMock).toHaveBeenCalledTimes(1);
    });

    const errorBanner = await screen.findByTestId('anomaly-dismiss-error');
    expect(errorBanner).toHaveTextContent(/failed to dismiss anomaly/i);

    // Modal must remain open so the admin can retry.
    expect(screen.getByRole('heading', { name: /dismiss anomaly/i })).toBeInTheDocument();
    // No refetch should fire on the failure path.
    expect(refetchMock).not.toHaveBeenCalled();
  });

  it('clears the error and closes the modal on a successful dismissal', async () => {
    dismissMutateMock.mockImplementation((_payload, options) => {
      options?.onSuccess?.();
    });

    render(<AnomalyAlertPanel isAdmin periodDays={7} />);
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    const confirmButtons = screen.getAllByRole('button', { name: /dismiss/i });
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(refetchMock).toHaveBeenCalledTimes(1);
    });

    expect(screen.queryByTestId('anomaly-dismiss-error')).toBeNull();
  });
});
