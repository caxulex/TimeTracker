/**
 * Task Estimation Card Component (Phase 4)
 * 
 * Input component for estimating task durations using ML.
 * Shows confidence, range, and similar historical tasks.
 */

import React, { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Clock,
  Target,
  TrendingUp,
  Loader2,
  ChevronDown,
  ChevronUp,
  Info,
  Sparkles
} from 'lucide-react';
import { aiApi } from '../../api/aiServices';

interface EstimationFactor {
  name: string;
  description: string;
  impact?: 'faster' | 'slower' | 'neutral';
}

interface SimilarTask {
  description: string;
  duration_minutes: number;
  similarity: number;
}

interface EstimationResult {
  success: boolean;
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

interface TaskEstimationCardProps {
  projectId?: number;
  onEstimate?: (estimate: EstimationResult) => void;
  initialDescription?: string;
  compact?: boolean;
}

const methodLabels = {
  ml: { label: 'ML Prediction', icon: Sparkles, color: 'text-purple-600' },
  historical: { label: 'Historical Data', icon: Clock, color: 'text-blue-600' },
  fallback: { label: 'Default Estimate', icon: Target, color: 'text-gray-600' }
};

const formatDuration = (minutes: number): string => {
  if (minutes < 60) {
    return `${Math.round(minutes)} min`;
  }
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
};

export const TaskEstimationCard: React.FC<TaskEstimationCardProps> = ({
  projectId,
  onEstimate,
  initialDescription = '',
  compact = false
}) => {
  const [description, setDescription] = useState(initialDescription);
  const [scheduledHour, setScheduledHour] = useState<number | undefined>();
  const [showDetails, setShowDetails] = useState(false);
  const [result, setResult] = useState<EstimationResult | null>(null);

  const mutation = useMutation({
    mutationFn: async (data: { description: string; project_id?: number; scheduled_hour?: number }) => {
      const response = await aiApi.estimateTaskDuration(data);
      return response as EstimationResult;
    },
    onSuccess: (data) => {
      setResult(data);
      onEstimate?.(data);
    }
  });

  const handleEstimate = useCallback(() => {
    if (!description.trim()) return;
    mutation.mutate({
      description: description.trim(),
      project_id: projectId,
      scheduled_hour: scheduledHour
    });
  }, [description, projectId, scheduledHour, mutation]);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleEstimate();
    }
  };

  const methodInfo = result?.method ? methodLabels[result.method] : null;
  const MethodIcon = methodInfo?.icon || Target;

  if (compact) {
    return (
      <div className="bg-white rounded-lg shadow p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Enter task description..."
            className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleEstimate}
            disabled={!description.trim() || mutation.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 text-sm"
          >
            {mutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <Clock className="w-4 h-4" />
                Estimate
              </>
            )}
          </button>
        </div>
        {result?.success && result.estimated_minutes && (
          <div className="mt-2 flex items-center justify-between text-sm">
            <span className="text-gray-600">
              Estimated: <span className="font-semibold text-gray-900">{formatDuration(result.estimated_minutes)}</span>
            </span>
            <span className="text-gray-500">
              {Math.round((result.confidence || 0) * 100)}% confidence
            </span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="px-4 py-3 border-b bg-gradient-to-r from-blue-50 to-purple-50 rounded-t-lg">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-purple-600" />
          <h3 className="font-semibold text-gray-800">Task Duration Estimator</h3>
        </div>
        <p className="text-sm text-gray-500 mt-0.5">Get AI-powered time estimates for your tasks</p>
      </div>

      <div className="p-4 space-y-4">
        {/* Input Form */}
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Task Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Describe the task (e.g., 'Implement user authentication feature')"
              rows={2}
              className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Scheduled Hour (optional)
              </label>
              <select
                value={scheduledHour ?? ''}
                onChange={(e) => setScheduledHour(e.target.value ? parseInt(e.target.value) : undefined)}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Any time</option>
                {Array.from({ length: 24 }, (_, i) => (
                  <option key={i} value={i}>
                    {i.toString().padStart(2, '0')}:00
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <button
                onClick={handleEstimate}
                disabled={!description.trim() || mutation.isPending}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
              >
                {mutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Estimating...
                  </>
                ) : (
                  <>
                    <Target className="w-4 h-4" />
                    Estimate Duration
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Error State */}
        {result && !result.success && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-sm text-red-600">{result.error || 'Failed to estimate duration'}</p>
          </div>
        )}

        {/* Result */}
        {result?.success && result.estimated_minutes && (
          <div className="bg-gradient-to-r from-green-50 to-blue-50 rounded-lg p-4 border border-green-200">
            {/* Main Estimate */}
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-sm text-gray-600">Estimated Duration</p>
                <p className="text-3xl font-bold text-gray-900">
                  {formatDuration(result.estimated_minutes)}
                </p>
              </div>
              <div className="text-right">
                <div className={`flex items-center gap-1 ${methodInfo?.color || 'text-gray-600'}`}>
                  <MethodIcon className="w-4 h-4" />
                  <span className="text-sm font-medium">{methodInfo?.label || 'Estimate'}</span>
                </div>
                <p className="text-sm text-gray-500 mt-1">
                  {Math.round((result.confidence || 0) * 100)}% confidence
                </p>
              </div>
            </div>

            {/* Confidence Bar */}
            <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden mb-3">
              <div
                className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500 to-green-500 rounded-full transition-all duration-500"
                style={{ width: `${(result.confidence || 0) * 100}%` }}
              />
            </div>

            {/* Range */}
            {result.range_min_minutes && result.range_max_minutes && (
              <div className="flex items-center justify-between text-sm text-gray-600 mb-3">
                <span>Range: {formatDuration(result.range_min_minutes)}</span>
                <div className="flex-1 mx-3 border-t border-dashed border-gray-300" />
                <span>{formatDuration(result.range_max_minutes)}</span>
              </div>
            )}

            {/* Recommendation */}
            {result.recommendation && (
              <div className="bg-white/50 rounded p-2 flex items-start gap-2">
                <Info className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                <p className="text-sm text-gray-600">{result.recommendation}</p>
              </div>
            )}

            {/* Toggle Details */}
            {(result.factors?.length || result.similar_tasks?.length) && (
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="mt-3 flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
              >
                {showDetails ? (
                  <>
                    <ChevronUp className="w-4 h-4" />
                    Hide details
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4" />
                    Show details
                  </>
                )}
              </button>
            )}

            {/* Expanded Details */}
            {showDetails && (
              <div className="mt-3 space-y-3 pt-3 border-t border-gray-200">
                {/* Factors */}
                {result.factors && result.factors.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Contributing Factors</h4>
                    <div className="space-y-1">
                      {result.factors.map((factor, index) => (
                        <div key={index} className="flex items-center justify-between text-sm">
                          <span className="text-gray-600">{factor.name}</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            factor.impact === 'faster' ? 'bg-green-100 text-green-700' :
                            factor.impact === 'slower' ? 'bg-red-100 text-red-700' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            {factor.impact || 'neutral'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Similar Tasks */}
                {result.similar_tasks && result.similar_tasks.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Similar Completed Tasks</h4>
                    <div className="space-y-2">
                      {result.similar_tasks.map((task, index) => (
                        <div key={index} className="bg-white/50 rounded p-2 text-sm">
                          <div className="flex items-center justify-between">
                            <span className="text-gray-600 truncate flex-1 mr-2">
                              {task.description || 'No description'}
                            </span>
                            <span className="font-medium text-gray-900 whitespace-nowrap">
                              {formatDuration(task.duration_minutes)}
                            </span>
                          </div>
                          <div className="mt-1 flex items-center gap-1">
                            <div className="flex-1 h-1 bg-gray-200 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-blue-400 rounded-full"
                                style={{ width: `${task.similarity * 100}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-500">
                              {Math.round(task.similarity * 100)}% similar
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default TaskEstimationCard;
