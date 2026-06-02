import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const { restoreAnomalyDismissalMock } = vi.hoisted(() => ({
  restoreAnomalyDismissalMock: vi.fn(),
}));

vi.mock('../api/aiServices', () => ({
  getTimeEntrySuggestions: vi.fn(),
  submitSuggestionFeedback: vi.fn(),
  scanAnomalies: vi.fn(),
  getAnomalies: vi.fn(),
  getAllAnomalies: vi.fn(),
  dismissAnomaly: vi.fn(),
  listDismissedAnomalies: vi.fn(),
  restoreAnomalyDismissal: restoreAnomalyDismissalMock,
  getAIStatus: vi.fn(),
  resetAIClient: vi.fn(),
}));

import { useRestoreAnomalyDismissal } from './useAIServices';

describe('useRestoreAnomalyDismissal', () => {
  beforeEach(() => {
    restoreAnomalyDismissalMock.mockReset();
  });

  it('invalidates dismissed and active anomaly queries after success', async () => {
    restoreAnomalyDismissalMock.mockResolvedValue(undefined);

    const queryClient = new QueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useRestoreAnomalyDismissal(), { wrapper });

    act(() => {
      result.current.mutate(123);
    });

    await waitFor(() => {
      expect(restoreAnomalyDismissalMock).toHaveBeenCalledWith(123);
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['ai', 'anomalies', 'dismissed'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['ai', 'anomalies'] });
  });
});