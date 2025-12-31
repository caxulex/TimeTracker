/**
 * TypeScript types for AI Feature Toggle System
 */

// ============================================
// FEATURE SETTINGS TYPES
// ============================================

export interface AIFeatureSetting {
  id: number;
  feature_id: string;
  feature_name: string;
  description: string | null;
  is_enabled: boolean;
  requires_api_key: boolean;
  api_provider: string | null;
  config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  updated_by: number | null;
}

export interface AIFeatureSettingUpdate {
  is_enabled: boolean;
}

// ============================================
// USER PREFERENCE TYPES
// ============================================

export interface UserAIPreference {
  id: number;
  user_id: number;
  feature_id: string;
  is_enabled: boolean;
  admin_override: boolean;
  admin_override_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface UserAIPreferenceUpdate {
  is_enabled: boolean;
}

// ============================================
// FEATURE STATUS TYPES
// ============================================

export interface FeatureStatus {
  feature_id: string;
  feature_name: string;
  description: string | null;
  api_provider: string | null;
  is_enabled: boolean;
  global_enabled: boolean;
  user_enabled: boolean | null;
  admin_override: boolean;
  reason: string;
}

export interface UserFeaturesResponse {
  features: FeatureStatus[];
}

// ============================================
// ADMIN TYPES
// ============================================

export interface FeatureUsageStats {
  total_requests: number;
  total_tokens: number;
  total_cost: number;
  avg_response_time_ms: number;
  success_rate: number;
  period_days: number;
}

export interface AdminFeatureSummary {
  feature_id: string;
  feature_name: string;
  description: string | null;
  is_enabled: boolean;
  api_provider: string | null;
  requires_api_key: boolean;
  enabled_user_count: number;
  total_user_count: number;
  usage_this_month: FeatureUsageStats;
}

export interface AdminFeaturesResponse {
  features: AdminFeatureSummary[];
}

export interface UserPreferenceAdminView {
  user_id: number;
  user_name: string;
  user_email: string;
  preferences: FeatureStatus[];
}

export interface AdminOverrideRequest {
  is_enabled: boolean;
}

// ============================================
// USAGE TYPES
// ============================================

export interface UsageSummary {
  period_days: number;
  total_requests: number;
  total_tokens: number;
  total_cost: number;
  unique_users: number;
  features: Record<string, {
    request_count: number;
    tokens_used: number;
    cost: number;
  }>;
}

export interface UserUsageSummary {
  user_id: number;
  period_days: number;
  total_tokens: number;
  total_cost: number;
  features: Record<string, {
    request_count: number;
    tokens_used: number;
    estimated_cost: number;
  }>;
}

// ============================================
// BATCH OPERATIONS
// ============================================

export interface BatchUserOverrideRequest {
  user_ids: number[];
  feature_id: string;
  is_enabled: boolean;
}

export interface BatchUpdateResponse {
  success: boolean;
  updated_count: number;
  failed_count: number;
  message: string;
}

// ============================================
// FEATURE CHECK RESPONSE
// ============================================

export interface FeatureCheckResponse {
  feature_id: string;
  is_enabled: boolean;
}

// ============================================
// FEATURE ID CONSTANTS
// ============================================

export const AI_FEATURES = {
  SUGGESTIONS: 'ai_suggestions',
  ANOMALY_ALERTS: 'ai_anomaly_alerts',
  PAYROLL_FORECAST: 'ai_payroll_forecast',
  NLP_ENTRY: 'ai_nlp_entry',
  REPORT_SUMMARIES: 'ai_report_summaries',
  TASK_ESTIMATION: 'ai_task_estimation',
} as const;

export type AIFeatureId = typeof AI_FEATURES[keyof typeof AI_FEATURES];

// ============================================
// FEATURE ICONS & COLORS (for UI)
// ============================================

export const FEATURE_UI_CONFIG: Record<string, {
  icon: string;
  color: string;
  bgColor: string;
}> = {
  ai_suggestions: {
    icon: '💡',
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50',
  },
  ai_anomaly_alerts: {
    icon: '🚨',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
  },
  ai_payroll_forecast: {
    icon: '📈',
    color: 'text-green-600',
    bgColor: 'bg-green-50',
  },
  ai_nlp_entry: {
    icon: '💬',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
  },
  ai_report_summaries: {
    icon: '📊',
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
  },
  ai_task_estimation: {
    icon: '🎯',
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
  },
};
