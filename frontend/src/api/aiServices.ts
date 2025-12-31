/**
 * AI Services API Client
 * 
 * API calls for AI features:
 * - Time entry suggestions
 * - Anomaly detection
 * - AI status
 */

import api from './client';

// Types
export interface Suggestion {
  project_id: number;
  project_name: string;
  task_id: number | null;
  task_name: string | null;
  suggested_description: string | null;
  confidence: number;
  reason: string;
  source: 'pattern' | 'ai' | 'recent';
}

export interface SuggestionResponse {
  suggestions: Suggestion[];
  enabled: boolean;
  total_found: number;
  context?: {
    time_of_day: string;
    day_of_week: string;
  };
  rate_limited?: boolean;
  error?: string;
  message?: string;
}

export interface SuggestionRequest {
  partial_description?: string;
  use_ai?: boolean;
  limit?: number;
}

export interface SuggestionFeedback {
  suggestion_project_id: number;
  accepted: boolean;
  actual_project_id?: number;
}

export interface AnomalyDetails {
  type: string;
  severity: 'info' | 'warning' | 'critical';
  user_id: number;
  user_name: string;
  description: string;
  detected_at: string;
  details: Record<string, unknown>;
  recommendation: string | null;
}

export interface AnomalyScanRequest {
  user_id?: number;
  team_id?: number;
  period_days?: number;
  scan_all?: boolean;
}

export interface AnomalyStatistics {
  users_scanned: number;
  users_with_anomalies: number;
  total_anomalies: number;
  critical_count: number;
  warning_count: number;
  info_count: number;
}

export interface AnomalyScanResponse {
  anomalies: AnomalyDetails[];
  enabled: boolean;
  user_id?: number;
  user_name?: string;
  summary?: Record<string, unknown>;
  statistics?: AnomalyStatistics;
  scan_date: string;
  period_days: number;
  error?: string;
  message?: string;
}

export interface AnomalyDismissRequest {
  user_id: number;
  anomaly_type: string;
  reason?: string;
}

export interface AIProviderStatus {
  gemini: boolean;
  openai: boolean;
  any: boolean;
}

export interface AIStatusResponse {
  providers: AIProviderStatus;
  features: Record<string, boolean>;
  cache_stats?: Record<string, number>;
}

// API Functions

/**
 * Get time entry suggestions
 */
export async function getTimeEntrySuggestions(
  request: SuggestionRequest = {}
): Promise<SuggestionResponse> {
  const response = await api.post<SuggestionResponse>(
    '/api/ai/suggestions/time-entry',
    request
  );
  return response.data;
}

/**
 * Submit feedback on a suggestion
 */
export async function submitSuggestionFeedback(
  feedback: SuggestionFeedback
): Promise<{ success: boolean }> {
  const response = await api.post<{ success: boolean }>(
    '/api/ai/suggestions/feedback',
    feedback
  );
  return response.data;
}

/**
 * Scan for anomalies
 */
export async function scanAnomalies(
  request: AnomalyScanRequest = {}
): Promise<AnomalyScanResponse> {
  const response = await api.post<AnomalyScanResponse>(
    '/api/ai/anomalies/scan',
    request
  );
  return response.data;
}

/**
 * Get current user's anomalies
 */
export async function getAnomalies(
  periodDays: number = 7
): Promise<AnomalyScanResponse> {
  const response = await api.get<AnomalyScanResponse>(
    '/api/ai/anomalies',
    { params: { period_days: periodDays } }
  );
  return response.data;
}

/**
 * Get all users' anomalies (admin only)
 */
export async function getAllAnomalies(
  periodDays: number = 7,
  teamId?: number
): Promise<AnomalyScanResponse> {
  const response = await api.get<AnomalyScanResponse>(
    '/api/ai/anomalies/all',
    { params: { period_days: periodDays, team_id: teamId } }
  );
  return response.data;
}

/**
 * Dismiss/acknowledge an anomaly
 */
export async function dismissAnomaly(
  request: AnomalyDismissRequest
): Promise<{ success: boolean }> {
  const response = await api.post<{ success: boolean }>(
    '/api/ai/anomalies/dismiss',
    request
  );
  return response.data;
}

/**
 * Get AI system status
 */
export async function getAIStatus(): Promise<AIStatusResponse> {
  const response = await api.get<AIStatusResponse>('/api/ai/status');
  return response.data;
}

/**
 * Reset AI client (admin only)
 */
export async function resetAIClient(): Promise<{
  success: boolean;
  providers: AIProviderStatus;
}> {
  const response = await api.post<{
    success: boolean;
    providers: AIProviderStatus;
  }>('/api/ai/status/reset-client');
  return response.data;
}


// ============================================
// PHASE 4: ML ANOMALY DETECTION API
// ============================================

export interface MLAnomalyScanRequest {
  user_id?: number;
  period_days?: number;
}

export interface MLAnomalyItem {
  type: string;
  severity: string;
  user_id: number;
  user_name: string;
  description: string;
  confidence: number;
  detected_at: string;
  details: Record<string, unknown>;
  recommendation?: string;
}

export interface MLAnomalyScanResponse {
  success: boolean;
  enabled?: boolean;
  anomalies: MLAnomalyItem[];
  total_found: number;
  ml_enabled?: boolean;
  scanned_at?: string;
  error?: string;
}

export interface BurnoutFactor {
  name: string;
  score: number;
  max_score: number;
  detail: string;
}

export interface BurnoutAssessmentRequest {
  user_id?: number;
  period_days?: number;
}

export interface BurnoutAssessmentResponse {
  success: boolean;
  enabled?: boolean;
  user_id?: number;
  user_name?: string;
  risk_level?: 'low' | 'moderate' | 'high' | 'critical';
  risk_score?: number;
  factors?: BurnoutFactor[];
  recommendations?: string[];
  trend?: 'improving' | 'stable' | 'worsening';
  assessed_at?: string;
  error?: string;
}

export interface TeamBurnoutResponse {
  success: boolean;
  enabled?: boolean;
  assessments: Array<Record<string, unknown>>;
  risk_distribution: Record<string, number>;
  total_users: number;
  high_risk_count: number;
  assessed_at?: string;
  error?: string;
}

export interface UserBaselineRequest {
  user_id?: number;
  period_days?: number;
}

export interface UserBaselineResponse {
  success: boolean;
  enabled?: boolean;
  user_id?: number;
  avg_daily_hours?: number;
  std_daily_hours?: number;
  avg_weekly_hours?: number;
  typical_start_hour?: number;
  typical_end_hour?: number;
  preferred_days?: number[];
  avg_entry_duration?: number;
  entries_per_day?: number;
  data_points?: number;
  calculated_at?: string;
  error?: string;
}

/**
 * Scan for ML-based anomalies
 */
export async function scanMLAnomalies(
  request: MLAnomalyScanRequest = {}
): Promise<MLAnomalyScanResponse> {
  const response = await api.post<MLAnomalyScanResponse>(
    '/api/ai/ml/anomalies/scan',
    request
  );
  return response.data;
}

/**
 * Assess burnout risk for a user
 */
export async function assessBurnoutRisk(
  request: BurnoutAssessmentRequest = {}
): Promise<BurnoutAssessmentResponse> {
  const response = await api.post<BurnoutAssessmentResponse>(
    '/api/ai/ml/burnout/assess',
    request
  );
  return response.data;
}

/**
 * Scan team for burnout risk
 */
export async function scanTeamBurnout(
  teamId?: number
): Promise<TeamBurnoutResponse> {
  const response = await api.post<TeamBurnoutResponse>(
    '/api/ai/ml/burnout/team-scan',
    { team_id: teamId }
  );
  return response.data;
}

/**
 * Calculate user behavioral baseline
 */
export async function calculateUserBaseline(
  request: UserBaselineRequest = {}
): Promise<UserBaselineResponse> {
  const response = await api.post<UserBaselineResponse>(
    '/api/ai/ml/baseline/calculate',
    request
  );
  return response.data;
}


// ============================================
// PHASE 4: TASK DURATION ESTIMATION API
// ============================================

export interface TaskEstimationRequest {
  description: string;
  project_id?: number;
  scheduled_hour?: number;
}

export interface EstimationFactor {
  name: string;
  description: string;
  impact?: 'faster' | 'slower' | 'neutral';
}

export interface SimilarTask {
  description: string;
  duration_minutes: number;
  similarity: number;
}

export interface TaskEstimationResponse {
  success: boolean;
  enabled?: boolean;
  estimated_minutes?: number;
  estimated_hours?: number;
  confidence?: number;
  range_min_minutes?: number;
  range_max_minutes?: number;
  method?: 'ml' | 'historical' | 'fallback';
  factors?: EstimationFactor[];
  similar_tasks?: SimilarTask[];
  recommendation?: string;
  error?: string;
}

export interface BatchTaskEstimationRequest {
  tasks: TaskEstimationRequest[];
}

export interface BatchEstimationItem {
  description: string;
  estimated_minutes: number;
  estimated_hours: number;
  confidence: number;
}

export interface BatchTaskEstimationResponse {
  success: boolean;
  enabled?: boolean;
  estimates: BatchEstimationItem[];
  total_minutes: number;
  total_hours: number;
  error?: string;
}

export interface ModelTrainingRequest {
  period_days?: number;
  team_id?: number;
}

export interface ModelTrainingResponse {
  success: boolean;
  enabled?: boolean;
  samples_used?: number;
  mae_minutes?: number;
  rmse_minutes?: number;
  trained_at?: string;
  error?: string;
}

export interface UserPerformanceProfileResponse {
  success: boolean;
  enabled?: boolean;
  user_id?: number;
  avg_task_duration?: number;
  task_completion_rate?: number;
  speed_factor?: number;
  preferred_task_types?: string[];
  peak_performance_hours?: number[];
  task_count?: number;
  calculated_at?: string;
  error?: string;
}

export interface EstimationStatsResponse {
  success: boolean;
  model_trained: boolean;
  ml_available: boolean;
  cached_profiles: number;
  min_samples_required: number;
  tfidf_features: number;
}

/**
 * Estimate task duration
 */
export async function estimateTaskDuration(
  request: TaskEstimationRequest
): Promise<TaskEstimationResponse> {
  const response = await api.post<TaskEstimationResponse>(
    '/api/ai/estimation/task',
    request
  );
  return response.data;
}

/**
 * Batch estimate task durations
 */
export async function estimateBatchTasks(
  request: BatchTaskEstimationRequest
): Promise<BatchTaskEstimationResponse> {
  const response = await api.post<BatchTaskEstimationResponse>(
    '/api/ai/estimation/batch',
    request
  );
  return response.data;
}

/**
 * Train the estimation model (admin only)
 */
export async function trainEstimationModel(
  request: ModelTrainingRequest = {}
): Promise<ModelTrainingResponse> {
  const response = await api.post<ModelTrainingResponse>(
    '/api/ai/estimation/train',
    request
  );
  return response.data;
}

/**
 * Get user performance profile
 */
export async function getUserPerformanceProfile(
  userId?: number
): Promise<UserPerformanceProfileResponse> {
  const response = await api.get<UserPerformanceProfileResponse>(
    '/api/ai/estimation/profile',
    { params: { user_id: userId } }
  );
  return response.data;
}

/**
 * Get estimation service statistics
 */
export async function getEstimationStats(): Promise<EstimationStatsResponse> {
  const response = await api.get<EstimationStatsResponse>(
    '/api/ai/estimation/stats'
  );
  return response.data;
}


// Create a unified AI API object for convenience
export const aiApi = {
  // Suggestions
  getTimeEntrySuggestions,
  submitSuggestionFeedback,
  
  // Anomalies
  scanAnomalies,
  getAnomalies,
  getAllAnomalies,
  dismissAnomaly,
  
  // Status
  getAIStatus,
  resetAIClient,
  
  // Phase 4: ML Anomaly Detection
  scanMLAnomalies,
  assessBurnoutRisk,
  scanTeamBurnout,
  calculateUserBaseline,
  
  // Phase 4: Task Estimation
  estimateTaskDuration,
  estimateBatchTasks,
  trainEstimationModel,
  getUserPerformanceProfile,
  getEstimationStats
};

