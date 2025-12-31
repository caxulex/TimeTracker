/**
 * SuggestionDropdown Component
 * 
 * Displays AI-powered suggestions for time entries.
 * Shows as a dropdown below the project selector.
 */

import React, { useState, useEffect } from 'react';
import { useSuggestionsOnDemand, useSuggestionFeedback } from '../../hooks/useAIServices';
import { Suggestion } from '../../api/aiServices';

interface SuggestionDropdownProps {
  // Called when user selects a suggestion
  onSelect: (suggestion: {
    projectId: number;
    projectName: string;
    taskId?: number | null;
    taskName?: string | null;
    description?: string;
  }) => void;
  // Current partial description (for context-aware suggestions)
  partialDescription?: string;
  // Whether component is visible
  isOpen?: boolean;
  // Close dropdown
  onClose?: () => void;
  // Whether to auto-fetch suggestions
  autoFetch?: boolean;
  // CSS class for positioning
  className?: string;
}

export const SuggestionDropdown: React.FC<SuggestionDropdownProps> = ({
  onSelect,
  partialDescription,
  isOpen = true,
  onClose,
  autoFetch = true,
  className = '',
}) => {
  const [showDropdown, setShowDropdown] = useState(isOpen);
  const { mutate: fetchSuggestions, data, isPending, error } = useSuggestionsOnDemand();
  const { mutate: submitFeedback } = useSuggestionFeedback();

  // Fetch suggestions when component opens or description changes
  useEffect(() => {
    if (isOpen && autoFetch) {
      const timeoutId = setTimeout(() => {
        fetchSuggestions({
          partial_description: partialDescription,
          use_ai: true,
          limit: 5,
        });
      }, 300); // Debounce

      return () => clearTimeout(timeoutId);
    }
  }, [isOpen, partialDescription, autoFetch, fetchSuggestions]);

  useEffect(() => {
    setShowDropdown(isOpen);
  }, [isOpen]);

  const handleSelect = (suggestion: Suggestion) => {
    // Submit positive feedback
    submitFeedback({
      suggestion_project_id: suggestion.project_id,
      accepted: true,
    });

    // Call parent handler
    onSelect({
      projectId: suggestion.project_id,
      projectName: suggestion.project_name,
      taskId: suggestion.task_id,
      taskName: suggestion.task_name,
      description: suggestion.suggested_description || undefined,
    });

    setShowDropdown(false);
    onClose?.();
  };

  const handleReject = (suggestion: Suggestion) => {
    submitFeedback({
      suggestion_project_id: suggestion.project_id,
      accepted: false,
    });
  };

  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 0.8) return 'bg-green-500';
    if (confidence >= 0.6) return 'bg-yellow-500';
    return 'bg-gray-400';
  };

  const getSourceIcon = (source: string): string => {
    switch (source) {
      case 'ai':
        return '✨';
      case 'recent':
        return '🕐';
      case 'pattern':
      default:
        return '📊';
    }
  };

  if (!showDropdown) return null;

  const suggestions = data?.suggestions || [];
  const enabled = data?.enabled !== false;

  return (
    <div
      className={`
        absolute z-50 w-full mt-1 bg-white dark:bg-gray-800 
        border border-gray-200 dark:border-gray-700 
        rounded-lg shadow-lg overflow-hidden
        ${className}
      `}
    >
      {/* Header */}
      <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
            ✨ AI Suggestions
          </span>
          {isPending && (
            <span className="animate-pulse text-blue-500 text-xs">
              Loading...
            </span>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            title="Close"
          >
            ✕
          </button>
        )}
      </div>

      {/* Content */}
      <div className="max-h-64 overflow-y-auto">
        {!enabled ? (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">
            <p>AI suggestions are disabled</p>
            <p className="text-xs mt-1">Enable in settings to get smart suggestions</p>
          </div>
        ) : error ? (
          <div className="p-4 text-center text-red-500">
            <p>Failed to load suggestions</p>
            <button
              onClick={() => fetchSuggestions({ partial_description: partialDescription })}
              className="text-sm text-blue-500 hover:underline mt-1"
            >
              Retry
            </button>
          </div>
        ) : suggestions.length === 0 ? (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">
            {isPending ? (
              <p>Finding suggestions...</p>
            ) : (
              <p>No suggestions available</p>
            )}
          </div>
        ) : (
          <ul>
            {suggestions.map((suggestion, index) => (
              <li
                key={`${suggestion.project_id}-${suggestion.task_id || 'no-task'}-${index}`}
                className="border-b border-gray-100 dark:border-gray-700 last:border-b-0"
              >
                <button
                  onClick={() => handleSelect(suggestion)}
                  className="w-full px-3 py-2 text-left hover:bg-blue-50 dark:hover:bg-gray-700 
                           transition-colors flex items-start space-x-2 group"
                >
                  {/* Source Icon */}
                  <span className="text-lg mt-0.5" title={`Source: ${suggestion.source}`}>
                    {getSourceIcon(suggestion.source)}
                  </span>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-gray-900 dark:text-white truncate">
                        {suggestion.project_name}
                      </span>
                      {suggestion.task_name && (
                        <>
                          <span className="text-gray-400">/</span>
                          <span className="text-gray-600 dark:text-gray-300 truncate">
                            {suggestion.task_name}
                          </span>
                        </>
                      )}
                    </div>

                    {suggestion.suggested_description && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 truncate mt-0.5">
                        {suggestion.suggested_description}
                      </p>
                    )}

                    <div className="flex items-center space-x-2 mt-1">
                      {/* Confidence indicator */}
                      <div className="flex items-center space-x-1">
                        <div
                          className={`w-2 h-2 rounded-full ${getConfidenceColor(suggestion.confidence)}`}
                          title={`Confidence: ${Math.round(suggestion.confidence * 100)}%`}
                        />
                        <span className="text-xs text-gray-400">
                          {Math.round(suggestion.confidence * 100)}%
                        </span>
                      </div>

                      {/* Reason */}
                      <span className="text-xs text-gray-400 truncate">
                        {suggestion.reason}
                      </span>
                    </div>
                  </div>

                  {/* Reject button (appears on hover) */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleReject(suggestion);
                    }}
                    className="opacity-0 group-hover:opacity-100 text-gray-400 
                             hover:text-red-500 transition-opacity p-1"
                    title="Not helpful"
                  >
                    👎
                  </button>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Footer with context info */}
      {data?.context && (
        <div className="px-3 py-1.5 bg-gray-50 dark:bg-gray-700 border-t border-gray-200 dark:border-gray-600">
          <p className="text-xs text-gray-400">
            Based on your {data.context.day_of_week} {data.context.time_of_day} patterns
          </p>
        </div>
      )}
    </div>
  );
};

export default SuggestionDropdown;
