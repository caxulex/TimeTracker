/**
 * Project Budget Panel
 * 
 * Displays project budget forecasts and risk assessments.
 */

import React from 'react';
import { 
  Briefcase,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  TrendingUp,
  Calendar,
  RefreshCw,
  DollarSign
} from 'lucide-react';
import { useProjectBudgetForecast, useProjectBudgetMutation } from '../../hooks/useForecastingServices';
import type { ProjectBudgetItem } from '../../api/forecastingServices';

interface ProjectBudgetPanelProps {
  className?: string;
  projectId?: number;
  teamId?: number;
}

export function ProjectBudgetPanel({ className = '', projectId, teamId }: ProjectBudgetPanelProps) {
  const { data, isLoading, error } = useProjectBudgetForecast({
    project_id: projectId,
    team_id: teamId
  });
  
  const mutation = useProjectBudgetMutation();

  const handleRefresh = () => {
    mutation.mutate({ project_id: projectId, team_id: teamId });
  };

  const getRiskIcon = (risk: string) => {
    switch (risk) {
      case 'critical':
        return <AlertTriangle className="w-5 h-5 text-red-500" />;
      case 'high':
        return <AlertCircle className="w-5 h-5 text-orange-500" />;
      case 'medium':
        return <TrendingUp className="w-5 h-5 text-yellow-500" />;
      default:
        return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'critical':
        return 'border-red-200 bg-red-50';
      case 'high':
        return 'border-orange-200 bg-orange-50';
      case 'medium':
        return 'border-yellow-200 bg-yellow-50';
      default:
        return 'border-green-200 bg-green-50';
    }
  };

  const getProgressColor = (utilization: number) => {
    if (utilization >= 90) return 'bg-red-500';
    if (utilization >= 75) return 'bg-orange-500';
    if (utilization >= 50) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  if (!data?.enabled) {
    return (
      <div className={`bg-white rounded-lg shadow-sm border p-6 ${className}`}>
        <div className="text-center text-gray-500">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-yellow-500" />
          <p>Budget forecasting is disabled</p>
          <p className="text-sm mt-1">Contact an administrator to enable this feature</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white rounded-lg shadow-sm border ${className}`}>
      {/* Header */}
      <div className="px-6 py-4 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-blue-600" />
            <h3 className="text-lg font-semibold text-gray-900">Project Budgets</h3>
            {data?.projects_analyzed !== undefined && (
              <span className="ml-2 bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full">
                {data.projects_analyzed} projects
              </span>
            )}
          </div>
          <button
            onClick={handleRefresh}
            disabled={isLoading || mutation.isPending}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${(isLoading || mutation.isPending) ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : error ? (
          <div className="text-center text-red-500 py-4">
            <AlertTriangle className="w-6 h-6 mx-auto mb-2" />
            <p>Failed to load budget forecasts</p>
          </div>
        ) : data?.forecasts.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <Briefcase className="w-8 h-8 mx-auto mb-2 text-gray-400" />
            <p>No projects to analyze</p>
          </div>
        ) : (
          <div className="space-y-4">
            {data?.forecasts.map((project: ProjectBudgetItem) => (
              <div 
                key={project.project_id}
                className={`border rounded-lg p-4 ${getRiskColor(project.risk_level)}`}
              >
                {/* Project Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    {getRiskIcon(project.risk_level)}
                    <span className="font-semibold text-gray-900">{project.project_name}</span>
                  </div>
                  <span className={`text-sm font-medium ${
                    project.budget_utilization_pct >= 90 ? 'text-red-600' :
                    project.budget_utilization_pct >= 75 ? 'text-orange-600' :
                    'text-green-600'
                  }`}>
                    {project.budget_utilization_pct}% used
                  </span>
                </div>

                {/* Progress Bar */}
                <div className="mb-4">
                  <div className="h-3 bg-white bg-opacity-60 rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${getProgressColor(project.budget_utilization_pct)} transition-all`}
                      style={{ width: `${Math.min(project.budget_utilization_pct, 100)}%` }}
                    />
                  </div>
                </div>

                {/* Budget Details */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                  <div className="bg-white bg-opacity-60 rounded p-2">
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <DollarSign className="w-3 h-3" />
                      Budget
                    </div>
                    <div className="font-semibold text-gray-900">
                      {formatCurrency(project.budget_total)}
                    </div>
                  </div>
                  <div className="bg-white bg-opacity-60 rounded p-2">
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <TrendingUp className="w-3 h-3" />
                      Spent
                    </div>
                    <div className="font-semibold text-gray-900">
                      {formatCurrency(project.spent_to_date)}
                    </div>
                  </div>
                  <div className="bg-white bg-opacity-60 rounded p-2">
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <Calendar className="w-3 h-3" />
                      Days Left
                    </div>
                    <div className="font-semibold text-gray-900">
                      {project.days_remaining}
                    </div>
                  </div>
                  <div className="bg-white bg-opacity-60 rounded p-2">
                    <div className="text-xs text-gray-500">Daily Burn</div>
                    <div className="font-semibold text-gray-900">
                      {formatCurrency(project.burn_rate_daily)}/day
                    </div>
                  </div>
                </div>

                {/* Projected Completion */}
                {project.projected_completion && (
                  <div className="text-sm text-gray-600 mb-3">
                    <span className="font-medium">Est. Completion:</span>{' '}
                    {formatDate(project.projected_completion)}
                    {project.projected_total > project.budget_total && (
                      <span className="text-red-600 ml-2">
                        (Over budget by {formatCurrency(project.projected_total - project.budget_total)})
                      </span>
                    )}
                  </div>
                )}

                {/* Recommendations */}
                {project.recommendations.length > 0 && (
                  <div className="bg-white bg-opacity-60 rounded p-3">
                    <div className="text-xs font-medium text-gray-500 mb-1">Recommendations</div>
                    <ul className="space-y-1">
                      {project.recommendations.map((rec, i) => (
                        <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                          <span className="text-blue-500">•</span>
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}

            {/* Meta info */}
            {data?.generated_at && (
              <p className="text-xs text-gray-400 text-center mt-4">
                Updated {new Date(data.generated_at).toLocaleTimeString()}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ProjectBudgetPanel;
