/**
 * AI Reporting API Services
 * 
 * API client functions for Phase 3 AI-powered reporting:
 * - Weekly productivity summaries
 * - Project health assessments
 * - User-specific insights
 */

import api from './client';

// ============================================
// TYPES
// ============================================

export type InsightType = 
  | 'productivity'
  | 'workload'
  | 'pattern'
  | 'anomaly'
  | 'achievement'
  | 'recommendation';

export type InsightSeverity = 'info' | 'warning' | 'success' | 'critical';

export interface Insight {
  type: InsightType;
  severity: InsightSeverity;
  title: string;
  description: string;
  metric_value?: number;
  metric_label?: string;
  action_items?: string[];
}

export interface WeeklySummaryRequest {
  user_id?: number;
  team_id?: number;
  week_start?: string;  // ISO date string
}

export interface TopProject {
  project_id: number;
  project_name: string;
  hours: number;
  percentage: number;
}

export interface ProjectDailyHours {
  date: string;
  hours: number;
  project_breakdown: Record<string, number>;
}

export interface SummaryMetrics {
  total_hours: number;
  daily_average: number;
  projects_worked: number;
  tasks_completed: number;
  trend_vs_previous: number;  // percentage change
  most_productive_day: string;
  top_projects: TopProject[];
  daily_breakdown: ProjectDailyHours[];
}

export interface AttentionItem {
  type: 'deadline' | 'budget' | 'workload' | 'overtime';
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
  project_id?: number;
  project_name?: string;
}

export interface WeeklySummaryResponse {
  success: boolean;
  enabled?: boolean;
  summary?: {
    period_start: string;
    period_end: string;
    ai_generated_summary: string;
    metrics: SummaryMetrics;
    insights: Insight[];
    attention_items: AttentionItem[];
    generated_at: string;
  };
  error?: string;
  message?: string;
}

export interface ProjectHealthRequest {
  project_id: number;
  include_team_metrics?: boolean;
}

export interface ProjectHealthResponse {
  success: boolean;
  enabled?: boolean;
  health?: {
    project_id: number;
    project_name: string;
    health_score: number;  // 0-100
    status: 'healthy' | 'at_risk' | 'critical';
    ai_analysis: string;
    factors: Array<{
      name: string;
      score: number;
      weight: number;
      description: string;
    }>;
    recommendations: string[];
    metrics: {
      budget_utilization: number;
      schedule_adherence: number;
      team_capacity: number;
      task_completion_rate: number;
      activity_trend: 'increasing' | 'decreasing' | 'stable';
    };
    generated_at: string;
  };
  error?: string;
  message?: string;
}

export interface UserInsightsRequest {
  user_id?: number;  // defaults to current user
  period_days?: number;  // defaults to 30
}

export interface UserInsightsResponse {
  success: boolean;
  enabled?: boolean;
  insights?: {
    user_id: number;
    user_name: string;
    period_start: string;
    period_end: string;
    ai_summary: string;
    productivity_score: number;  // 0-100
    patterns: Array<{
      name: string;
      description: string;
      frequency: string;
      impact: 'positive' | 'negative' | 'neutral';
    }>;
    achievements: string[];
    improvement_areas: string[];
    recommendations: string[];
    metrics: {
      total_hours: number;
      average_daily_hours: number;
      projects_contributed: number;
      tasks_completed: number;
      overtime_hours: number;
      focus_time_percentage: number;
    };
    generated_at: string;
  };
  error?: string;
  message?: string;
}

// ============================================
// API FUNCTIONS
// ============================================

/**
 * Generate weekly productivity summary
 */
export async function getWeeklySummary(
  request: WeeklySummaryRequest = {}
): Promise<WeeklySummaryResponse> {
  const response = await api.post<WeeklySummaryResponse>(
    '/api/ai/reports/weekly-summary',
    request
  );
  return response.data;
}

/**
 * Get project health assessment
 */
export async function getProjectHealth(
  request: ProjectHealthRequest
): Promise<ProjectHealthResponse> {
  const response = await api.post<ProjectHealthResponse>(
    '/api/ai/reports/project-health',
    request
  );
  return response.data;
}

/**
 * Get user-specific insights
 */
export async function getUserInsights(
  request: UserInsightsRequest = {}
): Promise<UserInsightsResponse> {
  const response = await api.post<UserInsightsResponse>(
    '/api/ai/reports/user-insights',
    request
  );
  return response.data;
}

// ============================================
// EXPORT API OBJECT
// ============================================

export const reportingApi = {
  getWeeklySummary,
  getProjectHealth,
  getUserInsights
};

export default reportingApi;
