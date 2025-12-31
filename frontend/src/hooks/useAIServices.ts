/**
 * AI Services Hooks
 * 
 * React Query hooks for AI features:
 * - useSuggestions: Get time entry suggestions
 * - useAnomalies: Get anomaly detection results
 * - useAIStatus: Get AI system status
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getTimeEntrySuggestions,
  submitSuggestionFeedback,
  scanAnomalies,
  getAnomalies,
  getAllAnomalies,
  dismissAnomaly,
  getAIStatus,
  resetAIClient,
  SuggestionRequest,
  SuggestionFeedback,
  AnomalyScanRequest,
  AnomalyDismissRequest,
} from '../api/aiServices';

// Query Keys
export const aiServiceKeys = {
  all: ['ai-services'] as const,
  suggestions: () => [...aiServiceKeys.all, 'suggestions'] as const,
  suggestionsWithParams: (params: SuggestionRequest) =>
    [...aiServiceKeys.suggestions(), params] as const,
  anomalies: () => [...aiServiceKeys.all, 'anomalies'] as const,
  myAnomalies: (periodDays: number) =>
    [...aiServiceKeys.anomalies(), 'my', periodDays] as const,
  allAnomalies: (periodDays: number, teamId?: number) =>
    [...aiServiceKeys.anomalies(), 'all', periodDays, teamId] as const,
  status: () => [...aiServiceKeys.all, 'status'] as const,
};

// ============================================
// SUGGESTION HOOKS
// ============================================

/**
 * Get time entry suggestions
 */
export function useSuggestions(
  request: SuggestionRequest = {},
  options?: {
    enabled?: boolean;
    staleTime?: number;
    refetchOnWindowFocus?: boolean;
  }
) {
  return useQuery({
    queryKey: aiServiceKeys.suggestionsWithParams(request),
    queryFn: () => getTimeEntrySuggestions(request),
    enabled: options?.enabled ?? true,
    staleTime: options?.staleTime ?? 60 * 1000, // 1 minute
    refetchOnWindowFocus: options?.refetchOnWindowFocus ?? false,
  });
}

/**
 * Get suggestions on demand (manual trigger)
 */
export function useSuggestionsOnDemand() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SuggestionRequest) => getTimeEntrySuggestions(request),
    onSuccess: (data, request) => {
      // Update cache with result
      queryClient.setQueryData(
        aiServiceKeys.suggestionsWithParams(request),
        data
      );
    },
  });
}

/**
 * Submit feedback on a suggestion
 */
export function useSuggestionFeedback() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (feedback: SuggestionFeedback) =>
      submitSuggestionFeedback(feedback),
    onSuccess: () => {
      // Invalidate suggestions to refresh
      queryClient.invalidateQueries({
        queryKey: aiServiceKeys.suggestions(),
      });
    },
  });
}

// ============================================
// ANOMALY HOOKS
// ============================================

/**
 * Get current user's anomalies
 */
export function useMyAnomalies(
  periodDays: number = 7,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: aiServiceKeys.myAnomalies(periodDays),
    queryFn: () => getAnomalies(periodDays),
    enabled: options?.enabled ?? true,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Get all users' anomalies (admin only)
 */
export function useAllAnomalies(
  periodDays: number = 7,
  teamId?: number,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: aiServiceKeys.allAnomalies(periodDays, teamId),
    queryFn: () => getAllAnomalies(periodDays, teamId),
    enabled: options?.enabled ?? true,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Trigger anomaly scan
 */
export function useAnomalyScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: AnomalyScanRequest) => scanAnomalies(request),
    onSuccess: (data, request) => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({
        queryKey: aiServiceKeys.anomalies(),
      });
    },
  });
}

/**
 * Dismiss an anomaly
 */
export function useDismissAnomaly() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: AnomalyDismissRequest) => dismissAnomaly(request),
    onSuccess: () => {
      // Invalidate anomaly queries
      queryClient.invalidateQueries({
        queryKey: aiServiceKeys.anomalies(),
      });
    },
  });
}

// ============================================
// STATUS HOOKS
// ============================================

/**
 * Get AI system status
 */
export function useAIStatus(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: aiServiceKeys.status(),
    queryFn: getAIStatus,
    enabled: options?.enabled ?? true,
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Reset AI client (admin only)
 */
export function useResetAIClient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: resetAIClient,
    onSuccess: () => {
      // Invalidate all AI service queries
      queryClient.invalidateQueries({
        queryKey: aiServiceKeys.all,
      });
    },
  });
}
