/**
 * Forecasting API Services
 * 
 * API client functions for Phase 2 predictive analytics:
 * - Payroll forecasting
 * - Overtime risk assessment
 * - Project budget predictions
 * - Cash flow planning
 */

import api from './client';

// ============================================
// TYPES
// ============================================

export interface PayrollForecastRequest {
  period_type?: 'weekly' | 'bi_weekly' | 'semi_monthly' | 'monthly';
  periods_ahead?: number;
  include_overtime?: boolean;
}

export interface PayrollForecastItem {
  period_start: string;
  period_end: string;
  predicted_total: number;
  predicted_regular: number;
  predicted_overtime: number;
  confidence: number;
  lower_bound: number;
  upper_bound: number;
  trend: 'increasing' | 'decreasing' | 'stable';
  factors: Array<{
    factor: string;
    description: string;
    impact: string;
  }>;
}

export interface PayrollForecastResponse {
  forecasts: PayrollForecastItem[];
  enabled: boolean;
  period_type?: string;
  historical_periods_used?: number;
  generated_at?: string;
  error?: string;
  message?: string;
}

export interface OvertimeRiskRequest {
  days_ahead?: number;
  team_id?: number;
}

export interface OvertimeRiskItem {
  user_id: number;
  user_name: string;
  current_hours: number;
  projected_hours: number;
  overtime_threshold: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  projected_overtime: number;
  estimated_cost: number;
  recommendation: string;
}

export interface OvertimeRiskResponse {
  risks: OvertimeRiskItem[];
  enabled: boolean;
  period?: string;
  users_assessed?: number;
  users_at_risk?: number;
  generated_at?: string;
  error?: string;
  message?: string;
}

export interface ProjectBudgetRequest {
  project_id?: number;
  team_id?: number;
}

export interface ProjectBudgetItem {
  project_id: number;
  project_name: string;
  budget_total: number;
  spent_to_date: number;
  projected_total: number;
  burn_rate_daily: number;
  days_remaining: number;
  projected_completion: string | null;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  budget_utilization_pct: number;
  recommendations: string[];
}

export interface ProjectBudgetResponse {
  forecasts: ProjectBudgetItem[];
  enabled: boolean;
  projects_analyzed?: number;
  generated_at?: string;
  error?: string;
  message?: string;
}

export interface CashFlowWeek {
  week_start: string;
  week_end: string;
  is_payroll_week: boolean;
  projected_payroll: number;
  cumulative: number;
}

export interface CashFlowResponse {
  forecast: CashFlowWeek[];
  enabled: boolean;
  average_payroll?: number;
  generated_at?: string;
  error?: string;
  message?: string;
}

// ============================================
// API FUNCTIONS
// ============================================

/**
 * Forecast payroll for upcoming periods
 */
export async function forecastPayroll(
  request: PayrollForecastRequest = {}
): Promise<PayrollForecastResponse> {
  const response = await api.post<PayrollForecastResponse>(
    '/api/ai/forecast/payroll',
    request
  );
  return response.data;
}

/**
 * Assess overtime risk for employees
 */
export async function assessOvertimeRisk(
  request: OvertimeRiskRequest = {}
): Promise<OvertimeRiskResponse> {
  const response = await api.post<OvertimeRiskResponse>(
    '/api/ai/forecast/overtime-risk',
    request
  );
  return response.data;
}

/**
 * Forecast project budget consumption
 */
export async function forecastProjectBudget(
  request: ProjectBudgetRequest = {}
): Promise<ProjectBudgetResponse> {
  const response = await api.post<ProjectBudgetResponse>(
    '/api/ai/forecast/project-budget',
    request
  );
  return response.data;
}

/**
 * Forecast cash flow for payroll obligations
 */
export async function forecastCashFlow(
  weeksAhead: number = 4
): Promise<CashFlowResponse> {
  const response = await api.get<CashFlowResponse>(
    '/api/ai/forecast/cash-flow',
    { params: { weeks_ahead: weeksAhead } }
  );
  return response.data;
}

export const forecastingApi = {
  forecastPayroll,
  assessOvertimeRisk,
  forecastProjectBudget,
  forecastCashFlow
};

export default forecastingApi;
