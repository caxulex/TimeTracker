/**
 * AI Feature Panel Component
 * 
 * Displays all AI features with toggles for the current user.
 * Used in the user Settings page.
 */

import React from 'react';
import { useMyAIFeatures, useToggleMyFeature, useMyUsage } from '../../hooks/useAIFeatures';
import { AIFeatureToggle } from './AIFeatureToggle';
import type { FeatureStatus } from '../../types/aiFeatures';

interface AIFeaturePanelProps {
  className?: string;
}

export const AIFeaturePanel: React.FC<AIFeaturePanelProps> = ({ className = '' }) => {
  const { data, isLoading, error, refetch } = useMyAIFeatures();
  const { data: usage } = useMyUsage(30);
  const toggleMutation = useToggleMyFeature();

  const handleToggle = (featureId: string, enabled: boolean) => {
    toggleMutation.mutate(
      { featureId, isEnabled: enabled },
      {
        onError: (error: Error) => {
          console.error('Failed to toggle feature:', error);
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className={`bg-white rounded-lg shadow-sm p-6 ${className}`}>
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-gray-100 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`bg-white rounded-lg shadow-sm p-6 ${className}`}>
        <div className="text-center py-8">
          <div className="text-red-500 text-4xl mb-4">⚠️</div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">Failed to load AI features</h3>
          <p className="text-gray-500 mb-4">{error.message}</p>
          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const features = data?.features || [];
  const enabledCount = features.filter((f) => f.is_enabled).length;
  const availableCount = features.filter((f) => f.global_enabled).length;

  return (
    <div className={`bg-white rounded-lg shadow-sm ${className}`}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🤖</span>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">AI Features</h3>
              <p className="text-sm text-gray-500">
                {enabledCount} of {availableCount} features enabled
              </p>
            </div>
          </div>
          {usage && usage.total_tokens > 0 && (
            <div className="text-right">
              <p className="text-sm font-medium text-gray-700">
                {usage.total_tokens.toLocaleString()} tokens used
              </p>
              <p className="text-xs text-gray-500">Last 30 days</p>
            </div>
          )}
        </div>
      </div>

      {/* Features List */}
      <div className="p-6">
        {features.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <span className="text-4xl block mb-4">🔮</span>
            <p>No AI features available yet.</p>
            <p className="text-sm mt-1">Check back later for new capabilities!</p>
          </div>
        ) : (
          <div className="space-y-4">
            {features.map((feature: FeatureStatus) => (
              <AIFeatureToggle
                key={feature.feature_id}
                feature={feature}
                onToggle={handleToggle}
                isLoading={
                  toggleMutation.isPending &&
                  toggleMutation.variables?.featureId === feature.feature_id
                }
                disabled={toggleMutation.isPending}
              />
            ))}
          </div>
        )}

        {/* Info Box */}
        <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-100">
          <div className="flex gap-3">
            <svg className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="text-sm text-blue-700">
              <p className="font-medium">About AI Features</p>
              <p className="mt-1 text-blue-600">
                These features use AI to help you work more efficiently. Some features may be 
                disabled by your administrator. Toggle any feature off if you prefer to work 
                without AI assistance.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AIFeaturePanel;
