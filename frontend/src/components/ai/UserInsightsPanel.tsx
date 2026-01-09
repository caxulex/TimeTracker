/**
 * UserInsightsPanel Component
 * 
 * Displays AI-generated user productivity insights
 * Part of Phase 3 AI Reporting features
 */

import React from 'react';
import { 
  User, Brain, TrendingUp, TrendingDown, Clock, Folder, 
  CheckCircle, Award, Target, AlertCircle, Loader2, RefreshCw,
  Sparkles, ChevronRight
} from 'lucide-react';
import { useAIUserInsights, useAIUserInsightsMutation } from '../../hooks/useReportingServices';

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
  
  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-500';
    if (score >= 60) return 'text-blue-500';
    if (score >= 40) return 'text-yellow-500';
    return 'text-red-500';
  };
  
  const getScoreGradient = (score: number) => {
    if (score >= 80) return 'from-green-500 to-emerald-400';
    if (score >= 60) return 'from-blue-500 to-cyan-400';
    if (score >= 40) return 'from-yellow-500 to-amber-400';
    return 'from-red-500 to-orange-400';
  };
  
  const getPatternImpactColor = (impact: string) => {
    switch (impact) {
      case 'positive': return 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20';
      case 'negative': return 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20';
      default: return 'text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-700/50';
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
  
  const insights = data.insights;
  // Ensure insights and all required properties exist
  if (!insights || !insights.metrics) return null;
  
  // Provide defaults for optional arrays
  const patterns = insights.patterns || [];
  const achievements = insights.achievements || [];
  const improvementAreas = insights.improvement_areas || [];
  const recommendations = insights.recommendations || [];
  
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
                {insights.user_name} • Last {periodDays} days
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
      
      {/* Productivity Score */}
      <div className="p-6 bg-gradient-to-r from-gray-50 to-white dark:from-gray-800 dark:to-gray-750">
        <div className="flex items-center gap-6">
          {/* Score Circle */}
          <div className="relative">
            <svg className="w-24 h-24 transform -rotate-90">
              <circle
                cx="48"
                cy="48"
                r="40"
                stroke="currentColor"
                strokeWidth="8"
                fill="none"
                className="text-gray-200 dark:text-gray-700"
              />
              <circle
                cx="48"
                cy="48"
                r="40"
                stroke="url(#scoreGradient)"
                strokeWidth="8"
                fill="none"
                strokeLinecap="round"
                strokeDasharray={`${(insights.productivity_score / 100) * 251.2} 251.2`}
              />
              <defs>
                <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" className={`stop-color-${getScoreColor(insights.productivity_score).split('-')[1]}-500`} stopColor={insights.productivity_score >= 60 ? '#3B82F6' : '#EF4444'} />
                  <stop offset="100%" className={`stop-color-${getScoreColor(insights.productivity_score).split('-')[1]}-400`} stopColor={insights.productivity_score >= 60 ? '#06B6D4' : '#F97316'} />
                </linearGradient>
              </defs>
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className={`text-2xl font-bold ${getScoreColor(insights.productivity_score)}`}>
                {insights.productivity_score}
              </span>
            </div>
          </div>
          
          {/* AI Summary */}
          <div className="flex-1">
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
              {insights.ai_summary}
            </p>
          </div>
        </div>
      </div>
      
      {/* Quick Metrics */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-4 p-4 bg-gray-50 dark:bg-gray-700/30">
        <div className="text-center">
          <Clock className="mx-auto text-blue-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {insights.metrics.total_hours.toFixed(0)}h
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Total</p>
        </div>
        <div className="text-center">
          <TrendingUp className="mx-auto text-green-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {insights.metrics.average_daily_hours.toFixed(1)}h
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Daily Avg</p>
        </div>
        <div className="text-center">
          <Folder className="mx-auto text-purple-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {insights.metrics.projects_contributed}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Projects</p>
        </div>
        <div className="text-center">
          <CheckCircle className="mx-auto text-green-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {insights.metrics.tasks_completed}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Tasks</p>
        </div>
        <div className="text-center">
          <AlertCircle className="mx-auto text-orange-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {insights.metrics.overtime_hours.toFixed(1)}h
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Overtime</p>
        </div>
        <div className="text-center">
          <Target className="mx-auto text-cyan-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {insights.metrics.focus_time_percentage.toFixed(0)}%
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Focus</p>
        </div>
      </div>
      
      {/* Patterns */}
      {patterns.length > 0 && (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
            <Sparkles size={16} className="text-purple-500" />
            Detected Patterns
          </h3>
          <div className="space-y-2">
            {patterns.map((pattern, i) => (
              <div 
                key={i}
                className={`p-3 rounded-lg ${getPatternImpactColor(pattern.impact)}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium">{pattern.name}</span>
                  <span className="text-xs opacity-75">{pattern.frequency}</span>
                </div>
                <p className="text-sm opacity-90">{pattern.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Achievements */}
      {achievements.length > 0 && (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
            <Award size={16} className="text-yellow-500" />
            Recent Achievements
          </h3>
          <div className="flex flex-wrap gap-2">
            {achievements.map((achievement, i) => (
              <span 
                key={i}
                className="px-3 py-1 bg-yellow-50 dark:bg-yellow-900/20 
                  text-yellow-700 dark:text-yellow-400 text-sm rounded-full
                  border border-yellow-200 dark:border-yellow-800"
              >
                🏆 {achievement}
              </span>
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
        Analysis period: {new Date(insights.period_start).toLocaleDateString()} - {new Date(insights.period_end).toLocaleDateString()}
        {' • '}Generated {new Date(insights.generated_at).toLocaleString()}
      </div>
    </div>
  );
};

export default UserInsightsPanel;
