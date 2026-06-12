/**
 * UserInsightsPanel Component
 * 
 * Displays AI-generated user productivity insights
 * Part of Phase 3 AI Reporting features
 */

import React from 'react';
import { 
  Brain, TrendingUp, TrendingDown, Clock, Folder,
  Target, AlertCircle, Loader2, RefreshCw,
  Sparkles, ChevronRight, Minus
} from 'lucide-react';
import { useAIUserInsights, useAIUserInsightsMutation } from '../../hooks/useReportingServices';
import { getAvgHoursSubtitle, getAvgHoursTooltip } from '../../utils/working_days';

interface UserInsightsPanelProps {
  userId?: number;
  periodDays?: number;
  className?: string;
  showHeader?: boolean;
}

const UserInsightsPanel: React.FC<UserInsightsPanelProps> = ({
  userId,
  periodDays = 30,
  className = '',
  showHeader = true
}) => {
  const { data, isLoading, isError, error, refetch } = useAIUserInsights(
    { user_id: userId, period_days: periodDays },
    { enabled: true }
  );
  
  const refreshMutation = useAIUserInsightsMutation();
  
  const handleRefresh = () => {
    refreshMutation.mutate({ user_id: userId, period_days: periodDays });
  };
  
  const getTrendVisual = (trend?: string) => {
    switch (trend) {
      case 'improving':
        return { icon: TrendingUp, color: 'text-green-500', label: 'Improving' };
      case 'declining':
        return { icon: TrendingDown, color: 'text-red-500', label: 'Declining' };
      case 'stable':
        return { icon: Minus, color: 'text-blue-500', label: 'Stable' };
      default:
        return { icon: Minus, color: 'text-gray-500', label: 'New' };
    }
  };
  
  // Not enabled
  if (data && !data.enabled) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 ${className}`}>
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Brain size={32} className="mx-auto mb-2 opacity-50" />
          <p>AI User Insights are not enabled</p>
          <p className="text-sm mt-1">Enable this feature in AI Settings</p>
        </div>
      </div>
    );
  }
  
  // Loading
  if (isLoading) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 ${className}`}>
        <div className="flex items-center justify-center gap-2">
          <Loader2 className="animate-spin text-blue-500" size={24} />
          <span className="text-gray-600 dark:text-gray-400">Analyzing your patterns...</span>
        </div>
      </div>
    );
  }
  
  // Error
  if (isError || !data?.success) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 ${className}`}>
        <div className="text-center text-red-500">
          <AlertCircle size={32} className="mx-auto mb-2" />
          <p>Failed to load insights</p>
          <p className="text-sm mt-1">{error?.message || data?.error}</p>
          <button
            onClick={() => refetch()}
            className="mt-3 px-4 py-2 bg-red-100 dark:bg-red-900/30 
              text-red-600 dark:text-red-400 rounded hover:bg-red-200 
              dark:hover:bg-red-900/50 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }
  
  const metrics = data.metrics;
  if (!metrics) return null;

  const insightItems = data.insights || [];
  const improvementAreas = insightItems
    .filter((item) => item.severity === 'warning' || item.severity === 'critical')
    .map((item) => item.description);
  const recommendations = insightItems.flatMap((item) => item.action_items || []);
  const highlights = insightItems
    .filter((item) => item.severity === 'info')
    .map((item) => item.description)
    .slice(0, 3);

  const trend = getTrendVisual(metrics.productivity_trend);
  const TrendIcon = trend.icon;
  const avgSubtitle = getAvgHoursSubtitle(
    {
      avg_denominator_days: metrics.avg_denominator_days,
      avg_denominator_type: metrics.avg_denominator_type,
      avg_includes_today: metrics.avg_includes_today,
    },
    periodDays,
  );
  const avgTooltip = getAvgHoursTooltip({
    avg_includes_today: metrics.avg_includes_today,
    avg_working_days_source: metrics.avg_working_days_source,
    avg_working_days_used: metrics.avg_working_days_used,
  });
  
  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden ${className}`}>
      {/* Header */}
      {showHeader && (
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-purple-500 to-blue-500 rounded-full">
              <Brain className="text-white" size={20} />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900 dark:text-gray-100">
                Your Insights
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {metrics.user_name || 'User'} • Last {periodDays} days
              </p>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshMutation.isPending}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300
              hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
            title="Refresh insights"
          >
            <RefreshCw 
              size={18} 
              className={refreshMutation.isPending ? 'animate-spin' : ''} 
            />
          </button>
        </div>
      )}
      
      {/* Trend Summary */}
      <div className="p-6 bg-gradient-to-r from-gray-50 to-white dark:from-gray-800 dark:to-gray-750">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white dark:bg-gray-700 rounded-full">
              <TrendIcon className={trend.color} size={26} />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Productivity Trend</p>
              <p className={`text-xl font-semibold ${trend.color}`}>{trend.label}</p>
            </div>
          </div>

          <div className="flex-1">
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
              {highlights.length > 0
                ? highlights[0]
                : 'No major changes detected in your recent work pattern.'}
            </p>
          </div>
        </div>
      </div>
      
      {/* Quick Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 p-4 bg-gray-50 dark:bg-gray-700/30">
        <div className="text-center">
          <Clock className="mx-auto text-blue-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {metrics.total_hours_30d.toFixed(0)}h
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">30d Total</p>
        </div>
        <div className="text-center">
          <TrendingUp className="mx-auto text-green-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {metrics.avg_daily_hours.toFixed(1)}h
          </p>
          <div className="flex items-center justify-center gap-2">
            <p className="text-xs text-gray-500 dark:text-gray-400">Daily Avg</p>
            <button
              type="button"
              className="w-4 h-4 rounded-full border border-gray-300 text-[10px] text-gray-500 leading-none"
              title={avgTooltip}
              aria-label="Daily Avg calculation details"
            >
              ?
            </button>
          </div>
          <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">{avgSubtitle}</p>
        </div>
        <div className="text-center">
          <Folder className="mx-auto text-purple-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {metrics.active_projects}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Projects</p>
        </div>
        <div className="text-center">
          <Target className="mx-auto text-cyan-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {metrics.expected_hours.toFixed(0)}h
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Expected / Week</p>
        </div>
        <div className="text-center">
          <Sparkles className="mx-auto text-orange-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {insightItems.length}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Insights</p>
        </div>
      </div>
      
      {/* Insight Highlights */}
      {highlights.length > 0 && (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
            <Sparkles size={16} className="text-purple-500" />
            Highlights
          </h3>
          <div className="space-y-2">
            {highlights.map((item, i) => (
              <div 
                key={i}
                className="p-3 rounded-lg text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-700/50"
              >
                <p className="text-sm opacity-90">{item}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Improvement Areas & Recommendations */}
      <div className="grid md:grid-cols-2 gap-4 p-4 border-t border-gray-200 dark:border-gray-700">
        {/* Improvement Areas */}
        {improvementAreas.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
              <Target size={16} className="text-orange-500" />
              Areas to Improve
            </h3>
            <ul className="space-y-1">
              {improvementAreas.map((area, i) => (
                <li 
                  key={i}
                  className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400"
                >
                  <ChevronRight size={14} className="text-orange-500 mt-1 flex-shrink-0" />
                  {area}
                </li>
              ))}
            </ul>
          </div>
        )}
        
        {/* Recommendations */}
        {recommendations.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
              <Sparkles size={16} className="text-blue-500" />
              Recommendations
            </h3>
            <ul className="space-y-1">
              {recommendations.map((rec, i) => (
                <li 
                  key={i}
                  className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400"
                >
                  <ChevronRight size={14} className="text-blue-500 mt-1 flex-shrink-0" />
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      
      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-700/30 
        text-xs text-gray-400 dark:text-gray-500 text-center">
        {data.generated_at
          ? `Generated ${new Date(data.generated_at).toLocaleString()}`
          : `Analysis window: last ${periodDays} days`}
      </div>
    </div>
  );
};

export default UserInsightsPanel;
