/**
 * Forecasting Hooks
 * 
 * React Query hooks for Phase 2 predictive analytics
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { forecastingApi } from '../api/forecastingServices';
import type {
  PayrollForecastRequest,
  PayrollForecastResponse,
  OvertimeRiskRequest,
  OvertimeRiskResponse,
  ProjectBudgetRequest,
  ProjectBudgetResponse,
  CashFlowResponse
} from '../api/forecastingServices';

// ============================================
// QUERY KEYS
// ============================================

export const forecastingKeys = {
  all: ['forecasting'] as const,
  payroll: (params?: PayrollForecastRequest) => 
    [...forecastingKeys.all, 'payroll', params] as const,
  overtimeRisk: (params?: OvertimeRiskRequest) => 
    [...forecastingKeys.all, 'overtime-risk', params] as const,
  projectBudget: (params?: ProjectBudgetRequest) => 
    [...forecastingKeys.all, 'project-budget', params] as const,
  cashFlow: (weeksAhead?: number) => 
    [...forecastingKeys.all, 'cash-flow', weeksAhead] as const
};

// ============================================
// HOOKS
// ============================================

/**
 * Hook for payroll forecasting
 */
export function usePayrollForecast(
  request: PayrollForecastRequest = {},
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: forecastingKeys.payroll(request),
    queryFn: () => forecastingApi.forecastPayroll(request),
    staleTime: 1000 * 60 * 30, // 30 minutes
    enabled: options?.enabled !== false
  });
}

/**
 * Hook for manually triggering payroll forecast
 */
export function usePayrollForecastMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: PayrollForecastRequest) => 
      forecastingApi.forecastPayroll(request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(forecastingKeys.payroll(variables), data);
    }
  });
}

/**
 * Hook for overtime risk assessment
 */
export function useOvertimeRisk(
  request: OvertimeRiskRequest = {},
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: forecastingKeys.overtimeRisk(request),
    queryFn: () => forecastingApi.assessOvertimeRisk(request),
    staleTime: 1000 * 60 * 15, // 15 minutes
    enabled: options?.enabled !== false
  });
}

/**
 * Hook for manually triggering overtime risk assessment
 */
export function useOvertimeRiskMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: OvertimeRiskRequest) => 
      forecastingApi.assessOvertimeRisk(request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(forecastingKeys.overtimeRisk(variables), data);
    }
  });
}

/**
 * Hook for project budget forecasting
 */
export function useProjectBudgetForecast(
  request: ProjectBudgetRequest = {},
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: forecastingKeys.projectBudget(request),
    queryFn: () => forecastingApi.forecastProjectBudget(request),
    staleTime: 1000 * 60 * 30, // 30 minutes
    enabled: options?.enabled !== false
  });
}

/**
 * Hook for manually triggering project budget forecast
 */
export function useProjectBudgetMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: ProjectBudgetRequest) => 
      forecastingApi.forecastProjectBudget(request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(forecastingKeys.projectBudget(variables), data);
    }
  });
}

/**
 * Hook for cash flow forecasting
 */
export function useCashFlowForecast(
  weeksAhead: number = 4,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: forecastingKeys.cashFlow(weeksAhead),
    queryFn: () => forecastingApi.forecastCashFlow(weeksAhead),
    staleTime: 1000 * 60 * 60, // 1 hour
    enabled: options?.enabled !== false
  });
}

/**
 * Combined hook for all forecasting data
 * Useful for dashboard views
 */
export function useForecastingDashboard(options?: { enabled?: boolean }) {
  const payroll = usePayrollForecast({}, options);
  const overtime = useOvertimeRisk({}, options);
  const budget = useProjectBudgetForecast({}, options);
  const cashFlow = useCashFlowForecast(4, options);
  
  const isLoading = payroll.isLoading || overtime.isLoading || 
                    budget.isLoading || cashFlow.isLoading;
  const isError = payroll.isError || overtime.isError || 
                  budget.isError || cashFlow.isError;
  
  return {
    payroll,
    overtime,
    budget,
    cashFlow,
    isLoading,
    isError,
    refetchAll: () => {
      payroll.refetch();
      overtime.refetch();
      budget.refetch();
      cashFlow.refetch();
    }
  };
}
