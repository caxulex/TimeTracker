/**
 * React hooks for AI Feature Toggle System
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiFeaturesApi } from '../api/aiFeatures';
import type {
  AIFeatureSetting,
  FeatureStatus,
  UserFeaturesResponse,
  AdminFeaturesResponse,
  UserPreferenceAdminView,
  UsageSummary,
  UserUsageSummary,
  BatchUserOverrideRequest,
} from '../types/aiFeatures';

// Query keys
const QUERY_KEYS = {
  features: ['ai-features'] as const,
  myFeatures: ['ai-features', 'me'] as const,
  myFeatureStatus: (featureId: string) => ['ai-features', 'me', featureId] as const,
  featureCheck: (featureId: string) => ['ai-features', 'check', featureId] as const,
  adminFeatures: ['ai-features', 'admin'] as const,
  userPreferences: (userId: number) => ['ai-features', 'admin', 'users', userId] as const,
  usageSummary: (days: number) => ['ai-features', 'usage', 'summary', days] as const,
  userUsage: (userId: number, days: number) => ['ai-features', 'usage', 'user', userId, days] as const,
  myUsage: (days: number) => ['ai-features', 'usage', 'me', days] as const,
};

// ============================================
// USER HOOKS
// ============================================

/**
 * Hook to get all available AI features
 */
export function useAIFeatures() {
  return useQuery<AIFeatureSetting[], Error>({
    queryKey: QUERY_KEYS.features,
    queryFn: aiFeaturesApi.listFeatures,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to get all features with status for current user
 */
export function useMyAIFeatures() {
  return useQuery<UserFeaturesResponse, Error>({
    queryKey: QUERY_KEYS.myFeatures,
    queryFn: aiFeaturesApi.getMyFeatures,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to get status of a specific feature for current user
 */
export function useMyFeatureStatus(featureId: string) {
  return useQuery<FeatureStatus, Error>({
    queryKey: QUERY_KEYS.myFeatureStatus(featureId),
    queryFn: () => aiFeaturesApi.getMyFeatureStatus(featureId),
    staleTime: 1 * 60 * 1000, // 1 minute
    enabled: !!featureId,
  });
}

/**
 * Hook to quickly check if a feature is enabled
 */
export function useFeatureEnabled(featureId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.featureCheck(featureId),
    queryFn: () => aiFeaturesApi.checkFeatureEnabled(featureId),
    staleTime: 30 * 1000, // 30 seconds
    enabled: !!featureId,
    select: (data) => data.is_enabled,
  });
}

/**
 * Hook to toggle a feature for yourself
 */
export function useToggleMyFeature() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ featureId, isEnabled }: { featureId: string; isEnabled: boolean }) =>
      aiFeaturesApi.toggleMyFeature(featureId, { is_enabled: isEnabled }),
    onSuccess: (data, variables) => {
      // Update the feature status in cache
      queryClient.setQueryData<FeatureStatus>(
        QUERY_KEYS.myFeatureStatus(variables.featureId),
        data
      );
      // Invalidate the full list
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.myFeatures });
      // Invalidate the quick check
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.featureCheck(variables.featureId) 
      });
    },
  });
}

// ============================================
// ADMIN HOOKS
// ============================================

/**
 * Hook to get admin-level features summary
 */
export function useAdminAIFeatures() {
  return useQuery<AdminFeaturesResponse, Error>({
    queryKey: QUERY_KEYS.adminFeatures,
    queryFn: aiFeaturesApi.getAdminFeaturesSummary,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to toggle a feature globally
 */
export function useToggleGlobalFeature() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ featureId, isEnabled }: { featureId: string; isEnabled: boolean }) =>
      aiFeaturesApi.toggleGlobalFeature(featureId, { is_enabled: isEnabled }),
    onSuccess: () => {
      // Invalidate all feature-related queries
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.features });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.adminFeatures });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.myFeatures });
    },
  });
}

/**
 * Hook to get a specific user's AI preferences (admin view)
 */
export function useUserPreferencesAdmin(userId: number | null) {
  return useQuery<UserPreferenceAdminView, Error>({
    queryKey: QUERY_KEYS.userPreferences(userId!),
    queryFn: () => aiFeaturesApi.getUserPreferencesAdmin(userId!),
    enabled: userId !== null,
    staleTime: 1 * 60 * 1000, // 1 minute
  });
}

/**
 * Hook to set admin override for a user's feature
 */
export function useSetUserOverride() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      userId,
      featureId,
      isEnabled,
    }: {
      userId: number;
      featureId: string;
      isEnabled: boolean;
    }) => aiFeaturesApi.setUserOverride(userId, featureId, { is_enabled: isEnabled }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.userPreferences(variables.userId) 
      });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.adminFeatures });
    },
  });
}

/**
 * Hook to remove admin override for a user's feature
 */
export function useRemoveUserOverride() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, featureId }: { userId: number; featureId: string }) =>
      aiFeaturesApi.removeUserOverride(userId, featureId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.userPreferences(variables.userId) 
      });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.adminFeatures });
    },
  });
}

/**
 * Hook to batch set overrides for multiple users
 */
export function useBatchSetOverrides() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: BatchUserOverrideRequest) => aiFeaturesApi.batchSetOverrides(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.adminFeatures });
    },
  });
}

// ============================================
// USAGE HOOKS
// ============================================

/**
 * Hook to get overall AI usage summary (admin only)
 */
export function useUsageSummary(days: number = 30) {
  return useQuery<UsageSummary, Error>({
    queryKey: QUERY_KEYS.usageSummary(days),
    queryFn: () => aiFeaturesApi.getUsageSummary(days),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to get AI usage for a specific user (admin only)
 */
export function useUserUsage(userId: number | null, days: number = 30) {
  return useQuery<UserUsageSummary, Error>({
    queryKey: QUERY_KEYS.userUsage(userId!, days),
    queryFn: () => aiFeaturesApi.getUserUsage(userId!, days),
    enabled: userId !== null,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to get your own AI usage statistics
 */
export function useMyUsage(days: number = 30) {
  return useQuery<UserUsageSummary, Error>({
    queryKey: QUERY_KEYS.myUsage(days),
    queryFn: () => aiFeaturesApi.getMyUsage(days),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to seed AI features (admin only)
 */
export function useSeedAIFeatures() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => aiFeaturesApi.seedFeatures(),
    onSuccess: () => {
      // Invalidate all feature queries to refresh the UI
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.features });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.adminFeatures });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.myFeatures });
    },
  });
}

// ============================================
// UTILITY HOOKS
// ============================================

/**
 * Hook that returns a function to check if a feature is enabled
 * Uses cached data when available
 */
export function useIsFeatureEnabled() {
  const { data: features } = useMyAIFeatures();

  return (featureId: string): boolean => {
    if (!features?.features) return false;
    const feature = features.features.find((f) => f.feature_id === featureId);
    return feature?.is_enabled ?? false;
  };
}

/**
 * Export query keys for external use
 */
export { QUERY_KEYS as AI_FEATURES_QUERY_KEYS };
