/**
 * API client for AI Feature Toggle System
 */

import api from './client';
import type {
  AIFeatureSetting,
  AIFeatureSettingUpdate,
  FeatureStatus,
  UserFeaturesResponse,
  AdminFeaturesResponse,
  UserPreferenceAdminView,
  AdminOverrideRequest,
  UsageSummary,
  UserUsageSummary,
  BatchUserOverrideRequest,
  BatchUpdateResponse,
  FeatureCheckResponse,
  UserAIPreferenceUpdate,
} from '../types/aiFeatures';

const BASE_URL = '/api/ai/features';

// ============================================
// USER ENDPOINTS
// ============================================

/**
 * List all available AI features
 */
export const listFeatures = async (): Promise<AIFeatureSetting[]> => {
  const response = await api.get<AIFeatureSetting[]>(BASE_URL);
  return response.data;
};

/**
 * Get all features with status for current user
 */
export const getMyFeatures = async (): Promise<UserFeaturesResponse> => {
  const response = await api.get<UserFeaturesResponse>(`${BASE_URL}/me`);
  return response.data;
};

/**
 * Get status of a specific feature for current user
 */
export const getMyFeatureStatus = async (featureId: string): Promise<FeatureStatus> => {
  const response = await api.get<FeatureStatus>(`${BASE_URL}/me/${featureId}`);
  return response.data;
};

/**
 * Toggle a feature for yourself
 */
export const toggleMyFeature = async (
  featureId: string,
  data: UserAIPreferenceUpdate
): Promise<FeatureStatus> => {
  const response = await api.put<FeatureStatus>(`${BASE_URL}/me/${featureId}`, data);
  return response.data;
};

/**
 * Quick check if a feature is enabled for current user
 */
export const checkFeatureEnabled = async (featureId: string): Promise<FeatureCheckResponse> => {
  const response = await api.get<FeatureCheckResponse>(`${BASE_URL}/check/${featureId}`);
  return response.data;
};

// ============================================
// ADMIN ENDPOINTS - GLOBAL SETTINGS
// ============================================

/**
 * Get admin-level features summary
 */
export const getAdminFeaturesSummary = async (): Promise<AdminFeaturesResponse> => {
  const response = await api.get<AdminFeaturesResponse>(`${BASE_URL}/admin`);
  return response.data;
};

/**
 * Toggle a feature globally (super admin only)
 */
export const toggleGlobalFeature = async (
  featureId: string,
  data: AIFeatureSettingUpdate
): Promise<AIFeatureSetting> => {
  const response = await api.put<AIFeatureSetting>(`${BASE_URL}/admin/${featureId}`, data);
  return response.data;
};

// ============================================
// ADMIN ENDPOINTS - USER OVERRIDES
// ============================================

/**
 * Get a specific user's AI preferences (admin view)
 */
export const getUserPreferencesAdmin = async (userId: number): Promise<UserPreferenceAdminView> => {
  const response = await api.get<UserPreferenceAdminView>(`${BASE_URL}/admin/users/${userId}`);
  return response.data;
};

/**
 * Set admin override for a user's feature
 */
export const setUserOverride = async (
  userId: number,
  featureId: string,
  data: AdminOverrideRequest
): Promise<FeatureStatus> => {
  const response = await api.put<FeatureStatus>(
    `${BASE_URL}/admin/users/${userId}/${featureId}`,
    data
  );
  return response.data;
};

/**
 * Remove admin override for a user's feature
 */
export const removeUserOverride = async (
  userId: number,
  featureId: string
): Promise<{ message: string; feature_id: string; user_id: number }> => {
  const response = await api.delete(`${BASE_URL}/admin/users/${userId}/${featureId}`);
  return response.data;
};

/**
 * Batch set overrides for multiple users
 */
export const batchSetOverrides = async (
  data: BatchUserOverrideRequest
): Promise<BatchUpdateResponse> => {
  const response = await api.post<BatchUpdateResponse>(`${BASE_URL}/admin/batch-override`, data);
  return response.data;
};

// ============================================
// USAGE STATISTICS
// ============================================

/**
 * Get overall AI usage summary (admin only)
 */
export const getUsageSummary = async (days: number = 30): Promise<UsageSummary> => {
  const response = await api.get<UsageSummary>(`${BASE_URL}/usage/summary`, {
    params: { days },
  });
  return response.data;
};

/**
 * Get AI usage for a specific user (admin only)
 */
export const getUserUsage = async (userId: number, days: number = 30): Promise<UserUsageSummary> => {
  const response = await api.get<UserUsageSummary>(`${BASE_URL}/usage/user/${userId}`, {
    params: { days },
  });
  return response.data;
};

/**
 * Get your own AI usage statistics
 */
export const getMyUsage = async (days: number = 30): Promise<UserUsageSummary> => {
  const response = await api.get<UserUsageSummary>(`${BASE_URL}/usage/me`, {
    params: { days },
  });
  return response.data;
};

// ============================================
// ADMIN SEED ENDPOINT
// ============================================

interface SeedResponse {
  status: string;
  message: string;
  features?: string[];
  count?: number;
}

/**
 * Seed AI features into the database (admin only)
 */
export const seedFeatures = async (): Promise<SeedResponse> => {
  const response = await api.post<SeedResponse>(`${BASE_URL}/admin/seed`);
  return response.data;
};

// ============================================
// EXPORT ALL
// ============================================

export const aiFeaturesApi = {
  // User endpoints
  listFeatures,
  getMyFeatures,
  getMyFeatureStatus,
  toggleMyFeature,
  checkFeatureEnabled,
  
  // Admin global settings
  getAdminFeaturesSummary,
  toggleGlobalFeature,
  
  // Admin user overrides
  getUserPreferencesAdmin,
  setUserOverride,
  removeUserOverride,
  batchSetOverrides,
  
  // Usage statistics
  getUsageSummary,
  getUserUsage,
  getMyUsage,
  
  // Admin seed
  seedFeatures,
};

export default aiFeaturesApi;
