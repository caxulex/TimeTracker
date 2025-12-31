/**
 * AI Feature Toggle Component
 * 
 * A toggle switch component for enabling/disabling AI features
 */

import React from 'react';
import { FEATURE_UI_CONFIG } from '../../types/aiFeatures';
import type { FeatureStatus } from '../../types/aiFeatures';

interface AIFeatureToggleProps {
  feature: FeatureStatus;
  onToggle: (featureId: string, enabled: boolean) => void;
  isLoading?: boolean;
  disabled?: boolean;
  showDescription?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export const AIFeatureToggle: React.FC<AIFeatureToggleProps> = ({
  feature,
  onToggle,
  isLoading = false,
  disabled = false,
  showDescription = true,
  size = 'md',
}) => {
  const config = FEATURE_UI_CONFIG[feature.feature_id] || {
    icon: '🤖',
    color: 'text-gray-600',
    bgColor: 'bg-gray-50',
  };

  const isDisabled = disabled || isLoading || feature.admin_override || !feature.global_enabled;
  
  const sizeClasses = {
    sm: {
      container: 'p-3',
      icon: 'text-lg',
      title: 'text-sm',
      description: 'text-xs',
      toggle: 'w-9 h-5',
      toggleDot: 'w-4 h-4',
      translateX: 'translate-x-4',
    },
    md: {
      container: 'p-4',
      icon: 'text-xl',
      title: 'text-base',
      description: 'text-sm',
      toggle: 'w-11 h-6',
      toggleDot: 'w-5 h-5',
      translateX: 'translate-x-5',
    },
    lg: {
      container: 'p-5',
      icon: 'text-2xl',
      title: 'text-lg',
      description: 'text-base',
      toggle: 'w-14 h-7',
      toggleDot: 'w-6 h-6',
      translateX: 'translate-x-7',
    },
  };

  const sizes = sizeClasses[size];

  const handleToggle = () => {
    if (!isDisabled) {
      onToggle(feature.feature_id, !feature.is_enabled);
    }
  };

  return (
    <div
      className={`
        ${sizes.container} rounded-lg border transition-all duration-200
        ${feature.is_enabled ? `${config.bgColor} border-gray-200` : 'bg-gray-50 border-gray-100'}
        ${isDisabled ? 'opacity-75' : 'hover:shadow-sm'}
      `}
    >
      <div className="flex items-start justify-between gap-4">
        {/* Feature Info */}
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <span className={`${sizes.icon} flex-shrink-0`}>{config.icon}</span>
          <div className="min-w-0">
            <h4 className={`${sizes.title} font-medium text-gray-900 truncate`}>
              {feature.feature_name}
            </h4>
            {showDescription && feature.description && (
              <p className={`${sizes.description} text-gray-500 mt-0.5 line-clamp-2`}>
                {feature.description}
              </p>
            )}
            {/* Status indicator */}
            {!feature.global_enabled && (
              <span className={`${sizes.description} text-red-600 font-medium mt-1 inline-block`}>
                Disabled by administrator
              </span>
            )}
            {feature.admin_override && feature.global_enabled && (
              <span className={`${sizes.description} text-amber-600 font-medium mt-1 inline-block`}>
                {feature.is_enabled ? 'Enabled by admin' : 'Locked by administrator'}
              </span>
            )}
          </div>
        </div>

        {/* Toggle Switch */}
        <button
          type="button"
          role="switch"
          aria-checked={feature.is_enabled}
          aria-label={`Toggle ${feature.feature_name}`}
          disabled={isDisabled}
          onClick={handleToggle}
          className={`
            ${sizes.toggle} relative inline-flex flex-shrink-0 rounded-full
            transition-colors duration-200 ease-in-out
            focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500
            ${isDisabled ? 'cursor-not-allowed' : 'cursor-pointer'}
            ${feature.is_enabled 
              ? 'bg-blue-600' 
              : 'bg-gray-200'
            }
          `}
        >
          <span
            className={`
              ${sizes.toggleDot} inline-block rounded-full bg-white shadow-sm
              transform transition-transform duration-200 ease-in-out
              ${feature.is_enabled ? sizes.translateX : 'translate-x-0.5'}
              ${isLoading ? 'animate-pulse' : ''}
            `}
          />
        </button>
      </div>

      {/* Reason tooltip */}
      {feature.reason && feature.reason !== 'Enabled' && feature.reason !== 'Enabled (default)' && (
        <div className={`${sizes.description} text-gray-400 mt-2 flex items-center gap-1`}>
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {feature.reason}
        </div>
      )}
    </div>
  );
};

export default AIFeatureToggle;
