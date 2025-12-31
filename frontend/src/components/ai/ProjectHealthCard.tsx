/**
 * ProjectHealthCard Component
 * 
 * Displays AI-generated project health assessment
 * Part of Phase 3 AI Reporting features
 */

import React from 'react';
import { 
  Heart, AlertTriangle, CheckCircle, XCircle, 
  TrendingUp, TrendingDown, Minus, Loader2, RefreshCw,
  Target, Users, Calendar, BarChart3
} from 'lucide-react';
import { useAIProjectHealth, useAIProjectHealthMutation } from '../../hooks/useReportingServices';

interface ProjectHealthCardProps {
  projectId: number;
  projectName?: string;
  includeTeamMetrics?: boolean;
  className?: string;
  compact?: boolean;
}

const ProjectHealthCard: React.FC<ProjectHealthCardProps> = ({
  projectId,
  projectName,
  includeTeamMetrics = false,
  className = '',
  compact = false
}) => {
  const { data, isLoading, isError, error, refetch } = useAIProjectHealth(
    projectId,
    { enabled: projectId > 0, includeTeamMetrics }
  );
  
  const refreshMutation = useAIProjectHealthMutation();
  
  const handleRefresh = () => {
    refreshMutation.mutate({ project_id: projectId, include_team_metrics: includeTeamMetrics });
  };
  
  const getHealthColor = (score: number) => {
    if (score >= 80) return 'text-green-500';
    if (score >= 60) return 'text-yellow-500';
    if (score >= 40) return 'text-orange-500';
    return 'text-red-500';
  };
  
  const getHealthBgColor = (score: number) => {
    if (score >= 80) return 'bg-green-500';
    if (score >= 60) return 'bg-yellow-500';
    if (score >= 40) return 'bg-orange-500';
    return 'bg-red-500';
  };
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="text-green-500" size={24} />;
      case 'at_risk':
        return <AlertTriangle className="text-yellow-500" size={24} />;
      case 'critical':
        return <XCircle className="text-red-500" size={24} />;
      default:
        return <Heart className="text-gray-400" size={24} />;
    }
  };
  
  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'increasing':
        return <TrendingUp className="text-green-500" size={16} />;
      case 'decreasing':
        return <TrendingDown className="text-red-500" size={16} />;
      default:
        return <Minus className="text-gray-400" size={16} />;
    }
  };
  
  // Not enabled
  if (data && !data.enabled) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 ${className}`}>
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Heart size={24} className="mx-auto mb-2 opacity-50" />
          <p className="text-sm">Project Health not enabled</p>
        </div>
      </div>
    );
  }
  
  // Loading
  if (isLoading) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 ${className}`}>
        <div className="flex items-center justify-center gap-2">
          <Loader2 className="animate-spin text-blue-500" size={20} />
          <span className="text-sm text-gray-500">Analyzing...</span>
        </div>
      </div>
    );
  }
  
  // Error
  if (isError || !data?.success) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 ${className}`}>
        <div className="text-center text-red-500">
          <AlertTriangle size={20} className="mx-auto mb-1" />
          <p className="text-sm">Failed to load health data</p>
          <button
            onClick={() => refetch()}
            className="mt-2 text-xs text-blue-500 hover:underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }
  
  const health = data.health;
  if (!health) return null;
  
  // Compact mode
  if (compact) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-3 ${className}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getStatusIcon(health.status)}
            <span className="font-medium text-gray-800 dark:text-gray-200 text-sm">
              {health.project_name || projectName}
            </span>
          </div>
          <div className={`text-xl font-bold ${getHealthColor(health.health_score)}`}>
            {health.health_score}
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {getStatusIcon(health.status)}
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                {health.project_name || projectName}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 capitalize">
                Status: {health.status.replace('_', ' ')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-center">
              <div className={`text-3xl font-bold ${getHealthColor(health.health_score)}`}>
                {health.health_score}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Health Score</p>
            </div>
            <button
              onClick={handleRefresh}
              disabled={refreshMutation.isPending}
              className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300
                hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
              title="Refresh"
            >
              <RefreshCw 
                size={18} 
                className={refreshMutation.isPending ? 'animate-spin' : ''} 
              />
            </button>
          </div>
        </div>
      </div>
      
      {/* AI Analysis */}
      <div className="p-4 bg-gray-50 dark:bg-gray-700/50">
        <p className="text-sm text-gray-700 dark:text-gray-300">
          {health.ai_analysis}
        </p>
      </div>
      
      {/* Metrics */}
      <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="text-center">
          <Target className="mx-auto text-blue-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {health.metrics.budget_utilization.toFixed(0)}%
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Budget Used</p>
        </div>
        <div className="text-center">
          <Calendar className="mx-auto text-green-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {health.metrics.schedule_adherence.toFixed(0)}%
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">On Schedule</p>
        </div>
        <div className="text-center">
          <Users className="mx-auto text-purple-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {health.metrics.team_capacity.toFixed(0)}%
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Team Capacity</p>
        </div>
        <div className="text-center">
          <BarChart3 className="mx-auto text-orange-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200 flex items-center justify-center gap-1">
            {health.metrics.task_completion_rate.toFixed(0)}%
            {getTrendIcon(health.metrics.activity_trend)}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Completion</p>
        </div>
      </div>
      
      {/* Health Factors */}
      {health.factors.length > 0 && (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
            Health Factors
          </h4>
          <div className="space-y-2">
            {health.factors.map((factor, i) => (
              <div key={i}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600 dark:text-gray-400">{factor.name}</span>
                  <span className={getHealthColor(factor.score)}>
                    {factor.score}/100
                  </span>
                </div>
                <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div 
                    className={`h-full rounded-full transition-all ${getHealthBgColor(factor.score)}`}
                    style={{ width: `${factor.score}%` }}
                  />
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                  {factor.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Recommendations */}
      {health.recommendations.length > 0 && (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
            Recommendations
          </h4>
          <ul className="space-y-1">
            {health.recommendations.map((rec, i) => (
              <li 
                key={i}
                className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400"
              >
                <span className="text-blue-500 mt-1">•</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 dark:bg-gray-700/30 
        text-xs text-gray-400 dark:text-gray-500 text-center">
        Generated {new Date(health.generated_at).toLocaleString()}
      </div>
    </div>
  );
};

export default ProjectHealthCard;
