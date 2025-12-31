/**
 * AI Reporting Hooks
 * 
 * React Query hooks for Phase 3 AI-powered reporting
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { reportingApi } from '../api/reportingServices';
import type {
  WeeklySummaryRequest,
  WeeklySummaryResponse,
  ProjectHealthRequest,
  ProjectHealthResponse,
  UserInsightsRequest,
  UserInsightsResponse
} from '../api/reportingServices';

// ============================================
// QUERY KEYS
// ============================================

export const aiReportingKeys = {
  all: ['ai-reports'] as const,
  weeklySummary: (params?: WeeklySummaryRequest) => 
    [...aiReportingKeys.all, 'weekly-summary', params] as const,
  projectHealth: (projectId: number) => 
    [...aiReportingKeys.all, 'project-health', projectId] as const,
  userInsights: (userId?: number, periodDays?: number) => 
    [...aiReportingKeys.all, 'user-insights', userId, periodDays] as const
};

// ============================================
// HOOKS
// ============================================

/**
 * Hook for fetching AI weekly summary (different from basic weekly summary in useApi)
 */
export function useAIWeeklySummary(
  request: WeeklySummaryRequest = {},
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: aiReportingKeys.weeklySummary(request),
    queryFn: () => reportingApi.getWeeklySummary(request),
    staleTime: 1000 * 60 * 60, // 1 hour
    enabled: options?.enabled !== false
  });
}

/**
 * Hook for manually triggering weekly summary generation
 */
export function useAIWeeklySummaryMutation() {
  const queryClient = useQueryClient();
  
  return useMutation<WeeklySummaryResponse, Error, WeeklySummaryRequest>({
    mutationFn: (request) => reportingApi.getWeeklySummary(request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(aiReportingKeys.weeklySummary(variables), data);
    }
  });
}

/**
 * Hook for fetching project health
 */
export function useAIProjectHealth(
  projectId: number,
  options?: { enabled?: boolean; includeTeamMetrics?: boolean }
) {
  return useQuery({
    queryKey: aiReportingKeys.projectHealth(projectId),
    queryFn: () => reportingApi.getProjectHealth({
      project_id: projectId,
      include_team_metrics: options?.includeTeamMetrics
    }),
    staleTime: 1000 * 60 * 30, // 30 minutes
    enabled: options?.enabled !== false && projectId > 0
  });
}

/**
 * Hook for manually triggering project health assessment
 */
export function useAIProjectHealthMutation() {
  const queryClient = useQueryClient();
  
  return useMutation<ProjectHealthResponse, Error, ProjectHealthRequest>({
    mutationFn: (request) => reportingApi.getProjectHealth(request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(
        aiReportingKeys.projectHealth(variables.project_id), 
        data
      );
    }
  });
}

/**
 * Hook for fetching user insights
 */
export function useAIUserInsights(
  request: UserInsightsRequest = {},
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: aiReportingKeys.userInsights(request.user_id, request.period_days),
    queryFn: () => reportingApi.getUserInsights(request),
    staleTime: 1000 * 60 * 60, // 1 hour
    enabled: options?.enabled !== false
  });
}

/**
 * Hook for manually triggering user insights generation
 */
export function useAIUserInsightsMutation() {
  const queryClient = useQueryClient();
  
  return useMutation<UserInsightsResponse, Error, UserInsightsRequest>({
    mutationFn: (request) => reportingApi.getUserInsights(request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(
        aiReportingKeys.userInsights(variables.user_id, variables.period_days), 
        data
      );
    }
  });
}

/**
 * Combined hook for AI reporting dashboard
 */
export function useAIReportsDashboard(
  options?: { 
    enabled?: boolean;
    weekStart?: string;
  }
) {
  const weeklySummary = useAIWeeklySummary(
    { week_start: options?.weekStart },
    { enabled: options?.enabled }
  );
  
  const userInsights = useAIUserInsights(
    {},
    { enabled: options?.enabled }
  );
  
  return {
    weeklySummary,
    userInsights,
    isLoading: weeklySummary.isLoading || userInsights.isLoading,
    isError: weeklySummary.isError || userInsights.isError,
    refetch: () => {
      weeklySummary.refetch();
      userInsights.refetch();
    }
  };
}

export default {
  useAIWeeklySummary,
  useAIWeeklySummaryMutation,
  useAIProjectHealth,
  useAIProjectHealthMutation,
  useAIUserInsights,
  useAIUserInsightsMutation,
  useAIReportsDashboard
};
