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
import type { ProjectHealthResponse } from '../../api/reportingServices';

interface ProjectHealthCardProps {
  projectId: number;
  projectName?: string;
  includeTeamMetrics?: boolean;
  className?: string;
  compact?: boolean;
}

interface NormalizedProjectHealth {
  projectName: string;
  healthScore: number | null;
  healthStatus: 'healthy' | 'moderate' | 'at_risk' | 'critical' | null;
  insufficientData: boolean;
  dataThresholds: {
    minHours: number;
    minTasks: number;
  };
  analysis: string;
  generatedAt?: string;
  recommendations: string[];
  metrics: {
    totalHours?: number;
    thisWeekHours?: number;
    lastWeekHours?: number;
    taskCompletionPct?: number;
    contributorCount?: number;
    activityTrend?: 'increasing' | 'decreasing' | 'stable' | 'new';
  };
}

function normalizeProjectHealth(
  data: ProjectHealthResponse | undefined,
  fallbackProjectName?: string,
): NormalizedProjectHealth | null {
  if (!data?.success) return null;

  if (data.insufficient_data === true) {
    const thresholds = data.data_thresholds || {
      min_hours: 5,
      min_tasks: 5,
    };

    return {
      projectName: data.project_name || fallbackProjectName || 'Project',
      healthScore: null,
      healthStatus: null,
      insufficientData: true,
      dataThresholds: {
        minHours: thresholds.min_hours,
        minTasks: thresholds.min_tasks,
      },
      analysis: "Project doesn't have enough activity yet to assess.",
      generatedAt: data.generated_at,
      recommendations: data.recommendations || [],
      metrics: {
        totalHours: data.metrics?.total_hours,
        thisWeekHours: data.metrics?.this_week_hours,
        lastWeekHours: data.metrics?.last_week_hours,
        taskCompletionPct: data.metrics?.task_completion_rate,
        contributorCount: data.metrics?.contributor_count,
        activityTrend: data.metrics?.activity_trend,
      },
    };
  }

  // Preferred shape: flat backend contract.
  if (
    typeof data.health_score === 'number' &&
    typeof data.health_status === 'string'
  ) {
    const insightDescriptions = (data.insights || []).map((insight) => insight.description).filter(Boolean);
    const recommendations = Array.from(
      new Set((data.insights || []).flatMap((insight) => insight.action_items || []).filter(Boolean)),
    );
    const rawCompletion = data.metrics?.task_completion_rate;
    const taskCompletionPct =
      typeof rawCompletion === 'number'
        ? rawCompletion <= 1
          ? rawCompletion * 100
          : rawCompletion
        : undefined;

    return {
      projectName: data.project_name || fallbackProjectName || 'Project',
      healthScore: data.health_score,
      healthStatus: data.health_status,
      insufficientData: false,
      dataThresholds: {
        minHours: 5,
        minTasks: 5,
      },
      analysis:
        insightDescriptions[0] ||
        'Health score generated from recent project activity, completion pace, and collaboration signals.',
      generatedAt: data.generated_at,
      recommendations: Array.from(new Set([...(data.recommendations || []), ...recommendations])),
      metrics: {
        totalHours: data.metrics?.total_hours,
        thisWeekHours: data.metrics?.this_week_hours,
        lastWeekHours: data.metrics?.last_week_hours,
        taskCompletionPct,
        contributorCount: data.metrics?.contributor_count,
        activityTrend: data.metrics?.activity_trend,
      },
    };
  }

  // Legacy nested shape support for rolling deploy compatibility.
  if (data.health && typeof data.health.health_score === 'number' && typeof data.health.status === 'string') {
    return {
      projectName: data.health.project_name || fallbackProjectName || 'Project',
      healthScore: data.health.health_score,
      healthStatus: data.health.status,
      insufficientData: false,
      dataThresholds: {
        minHours: 5,
        minTasks: 5,
      },
      analysis: data.health.ai_analysis || 'Project health assessment ready.',
      generatedAt: data.health.generated_at,
      recommendations: data.health.recommendations || [],
      metrics: {
        taskCompletionPct: data.health.metrics?.task_completion_rate,
        activityTrend: data.health.metrics?.activity_trend,
      },
    };
  }

  return null;
}

const ProjectHealthCard: React.FC<ProjectHealthCardProps> = ({
  projectId,
  projectName,
  includeTeamMetrics = false,
  className = '',
  compact = false
}) => {
  const { data, isLoading, isError, refetch } = useAIProjectHealth(
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
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="text-green-500" size={24} />;
      case 'moderate':
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

  const renderInsufficientDataState = (health: NormalizedProjectHealth) => {
    const disclosure = `Need at least ${health.dataThresholds.minHours} hours of logged work OR ${health.dataThresholds.minTasks} defined tasks`;

    if (compact) {
      return (
        <div
          className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-3 ${className}`}
          role="region"
          aria-label={`Project health for ${health.projectName}: not enough activity to assess yet`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="text-amber-500 mt-0.5" size={18} aria-hidden="true" />
              <div>
                <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">
                  Not enough activity to assess yet
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {disclosure}
                </p>
              </div>
            </div>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
            {typeof health.metrics.totalHours === 'number' ? `${health.metrics.totalHours.toFixed(1)}h` : '—'} logged · {' '}
            {typeof health.metrics.taskCompletionPct === 'number' ? `${health.metrics.taskCompletionPct.toFixed(0)}% complete` : '—'} · {' '}
            {typeof health.metrics.contributorCount === 'number' ? `${health.metrics.contributorCount} contributors` : '—'}
          </p>
        </div>
      );
    }

    return (
      <div 
        className={`bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden ${className}`}
        role="region"
        aria-label={`AI Project Health Analysis for ${health.projectName}`}
      >
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="text-amber-500" size={24} aria-hidden="true" />
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                  {health.projectName}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Not enough activity to assess yet
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {disclosure}
                </p>
              </div>
            </div>
            <button
              onClick={handleRefresh}
              disabled={refreshMutation.isPending}
              className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300
                hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
              title="Refresh project health analysis"
              aria-label={refreshMutation.isPending ? 'Refreshing project health data...' : 'Refresh project health analysis'}
            >
              <RefreshCw 
                size={18} 
                className={refreshMutation.isPending ? 'animate-spin' : ''} 
                aria-hidden="true"
              />
            </button>
          </div>
        </div>

        <div className="p-4 bg-gray-50 dark:bg-gray-700/50">
          <p className="text-sm text-gray-700 dark:text-gray-300">
            {health.analysis}
          </p>
        </div>

        <div className="p-4 grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center">
            <Target className="mx-auto text-blue-500 mb-1" size={18} />
            <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
              {typeof health.metrics.totalHours === 'number' ? `${health.metrics.totalHours.toFixed(1)}h` : '—'}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Total Hours</p>
          </div>
          <div className="text-center">
            <Calendar className="mx-auto text-green-500 mb-1" size={18} />
            <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
              {typeof health.metrics.thisWeekHours === 'number' ? `${health.metrics.thisWeekHours.toFixed(1)}h` : '—'}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">This Week</p>
          </div>
          <div className="text-center">
            <BarChart3 className="mx-auto text-orange-500 mb-1" size={18} />
            <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
              {typeof health.metrics.lastWeekHours === 'number' ? `${health.metrics.lastWeekHours.toFixed(1)}h` : '—'}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Last Week</p>
          </div>
          <div className="text-center">
            <Calendar className="mx-auto text-green-500 mb-1" size={18} />
            <p className="text-lg font-semibold text-gray-800 dark:text-gray-200 flex items-center justify-center gap-1">
              {typeof health.metrics.taskCompletionPct === 'number' ? `${health.metrics.taskCompletionPct.toFixed(0)}%` : '—'}
              {health.metrics.activityTrend ? getTrendIcon(health.metrics.activityTrend) : null}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Completion</p>
          </div>
          <div className="text-center">
            <Users className="mx-auto text-purple-500 mb-1" size={18} />
            <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
              {typeof health.metrics.contributorCount === 'number' ? health.metrics.contributorCount : '—'}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Contributors</p>
          </div>
        </div>

        <div className="px-4 py-2 bg-gray-50 dark:bg-gray-700/30 text-xs text-gray-400 dark:text-gray-500 text-center">
          Generated {health.generatedAt ? new Date(health.generatedAt).toLocaleString() : 'just now'}
        </div>
      </div>
    );
  };
  
  // Not enabled
  if (data && !data.enabled) {
    return (
      <div 
        className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 ${className}`}
        role="region"
        aria-label="Project Health - Feature disabled"
      >
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Heart size={24} className="mx-auto mb-2 opacity-50" aria-hidden="true" />
          <p className="text-sm">Project Health not enabled</p>
        </div>
      </div>
    );
  }
  
  // Loading
  if (isLoading) {
    return (
      <div 
        className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 ${className}`}
        role="status"
        aria-label="Loading project health analysis"
      >
        <div className="flex items-center justify-center gap-2">
          <Loader2 className="animate-spin text-blue-500" size={20} aria-hidden="true" />
          <span className="text-sm text-gray-500">Analyzing...</span>
        </div>
        <span className="sr-only">Analyzing project health data, please wait...</span>
      </div>
    );
  }
  
  // Error
  if (isError || !data?.success) {
    return (
      <div 
        className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 ${className}`}
        role="alert"
        aria-label="Project health analysis error"
      >
        <div className="text-center text-red-500">
          <AlertTriangle size={20} className="mx-auto mb-1" aria-hidden="true" />
          <p className="text-sm">Failed to load health data</p>
          <button
            onClick={() => refetch()}
            aria-label="Retry loading project health data"
            className="mt-2 text-xs text-blue-500 hover:underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const health = normalizeProjectHealth(data, projectName);
  if (!health) return null;

  if (health.insufficientData) {
    return renderInsufficientDataState(health);
  }

  const displayHealthScore = health.healthScore ?? 0;
  const displayHealthStatus = health.healthStatus ?? 'moderate';
  
  // Compact mode
  if (compact) {
    return (
      <div 
        className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-3 ${className}`}
        role="region"
        aria-label={`Project health for ${health.projectName}: score ${health.healthScore} out of 100, status ${health.healthStatus}`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getStatusIcon(displayHealthStatus)}
            <span className="font-medium text-gray-800 dark:text-gray-200 text-sm">
              {health.projectName}
            </span>
          </div>
          <div className={`text-xl font-bold ${getHealthColor(displayHealthScore)}`}>
            {health.healthScore}
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div 
      className={`bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden ${className}`}
      role="region"
      aria-label={`AI Project Health Analysis for ${health.projectName}`}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {getStatusIcon(displayHealthStatus)}
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                {health.projectName}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 capitalize">
                Status: {displayHealthStatus.replace('_', ' ')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-center" role="status" aria-live="polite">
              <div 
                className={`text-3xl font-bold ${getHealthColor(displayHealthScore)}`}
                aria-label={`Health score: ${health.healthScore} out of 100`}
              >
                {health.healthScore}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Health Score</p>
            </div>
            <button
              onClick={handleRefresh}
              disabled={refreshMutation.isPending}
              className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300
                hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
              title="Refresh project health analysis"
              aria-label={refreshMutation.isPending ? 'Refreshing project health data...' : 'Refresh project health analysis'}
            >
              <RefreshCw 
                size={18} 
                className={refreshMutation.isPending ? 'animate-spin' : ''} 
                aria-hidden="true"
              />
            </button>
          </div>
        </div>
      </div>
      
      {/* AI Analysis */}
      <div className="p-4 bg-gray-50 dark:bg-gray-700/50">
        <p className="text-sm text-gray-700 dark:text-gray-300">
          {health.analysis}
        </p>
      </div>
      
      {/* Metrics */}
      <div className="p-4 grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="text-center">
          <Target className="mx-auto text-blue-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {typeof health.metrics.totalHours === 'number' ? `${health.metrics.totalHours.toFixed(1)}h` : '—'}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Total Hours</p>
        </div>
        <div className="text-center">
          <Calendar className="mx-auto text-green-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {typeof health.metrics.thisWeekHours === 'number' ? `${health.metrics.thisWeekHours.toFixed(1)}h` : '—'}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">This Week</p>
        </div>
        <div className="text-center">
          <BarChart3 className="mx-auto text-orange-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {typeof health.metrics.lastWeekHours === 'number' ? `${health.metrics.lastWeekHours.toFixed(1)}h` : '—'}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Last Week</p>
        </div>
        <div className="text-center">
          <Calendar className="mx-auto text-green-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200 flex items-center justify-center gap-1">
            {typeof health.metrics.taskCompletionPct === 'number' ? `${health.metrics.taskCompletionPct.toFixed(0)}%` : '—'}
            {health.metrics.activityTrend ? getTrendIcon(health.metrics.activityTrend) : null}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Completion</p>
        </div>
        <div className="text-center">
          <Users className="mx-auto text-purple-500 mb-1" size={18} />
          <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            {typeof health.metrics.contributorCount === 'number' ? health.metrics.contributorCount : '—'}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">Contributors</p>
        </div>
      </div>
      
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
        Generated {health.generatedAt ? new Date(health.generatedAt).toLocaleString() : 'just now'}
      </div>
    </div>
  );
};

export default ProjectHealthCard;
