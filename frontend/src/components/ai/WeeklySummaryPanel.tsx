/**
 * WeeklySummaryPanel Component
 * 
 * Displays AI-generated weekly productivity summary
 * Part of Phase 3 AI Reporting features
 */

import React from 'react';
import { 
  TrendingUp, TrendingDown, Minus, Calendar, Clock, 
  Folder, CheckCircle, AlertTriangle, Loader2, RefreshCw,
  Sparkles, ChevronDown, ChevronUp
} from 'lucide-react';
import { useAIWeeklySummary, useAIWeeklySummaryMutation } from '../../hooks/useReportingServices';
import type { Insight, TopProject, AttentionItem } from '../../api/reportingServices';

interface WeeklySummaryPanelProps {
  weekStart?: string;
  teamId?: number;
  className?: string;
  collapsible?: boolean;
  defaultExpanded?: boolean;
}

const WeeklySummaryPanel: React.FC<WeeklySummaryPanelProps> = ({
  weekStart,
  teamId,
  className = '',
  collapsible = false,
  defaultExpanded = true
}) => {
  const [expanded, setExpanded] = React.useState(defaultExpanded);
  
  const { data, isLoading, isError, error, refetch } = useAIWeeklySummary(
    { week_start: weekStart, team_id: teamId },
    { enabled: true }
  );
  
  const refreshMutation = useAIWeeklySummaryMutation();
  
  const handleRefresh = () => {
    refreshMutation.mutate({ week_start: weekStart, team_id: teamId });
  };
  
  const getTrendIcon = (trend: number) => {
    if (trend > 5) return <TrendingUp className="text-green-500" size={16} />;
    if (trend < -5) return <TrendingDown className="text-red-500" size={16} />;
    return <Minus className="text-gray-400" size={16} />;
  };
  
  const getInsightIcon = (type: Insight['type'], severity: Insight['severity']) => {
    const colorMap = {
      info: 'text-blue-500',
      warning: 'text-yellow-500',
      success: 'text-green-500',
      critical: 'text-red-500'
    };
    return <Sparkles size={16} className={colorMap[severity]} />;
  };
  
  const getAttentionColor = (severity: AttentionItem['severity']) => {
    switch (severity) {
      case 'high': return 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800';
      case 'medium': return 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800';
      default: return 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800';
    }
  };
  
  // Not enabled state
  if (data && !data.enabled) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 ${className}`}>
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Sparkles size={32} className="mx-auto mb-2 opacity-50" />
          <p>AI Weekly Summaries are not enabled</p>
          <p className="text-sm mt-1">Enable this feature in AI Settings</p>
        </div>
      </div>
    );
  }
  
  // Loading state
  if (isLoading) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 ${className}`}>
        <div className="flex items-center justify-center gap-2">
          <Loader2 className="animate-spin text-blue-500" size={24} />
          <span className="text-gray-600 dark:text-gray-400">Generating summary...</span>
        </div>
      </div>
    );
  }
  
  // Error state
  if (isError || !data?.success) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 ${className}`}>
        <div className="text-center text-red-500">
          <AlertTriangle size={32} className="mx-auto mb-2" />
          <p>Failed to load weekly summary</p>
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
  
  const summary = data.summary;
  if (!summary) return null;
  
  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden ${className}`}>
      {/* Header */}
      <div 
        className={`p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between
          ${collapsible ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50' : ''}`}
        onClick={collapsible ? () => setExpanded(!expanded) : undefined}
      >
        <div className="flex items-center gap-3">
          <Sparkles className="text-purple-500" size={24} />
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-gray-100">
              Weekly Summary
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {new Date(summary.period_start).toLocaleDateString()} - {new Date(summary.period_end).toLocaleDateString()}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleRefresh();
            }}
            disabled={refreshMutation.isPending}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300
              hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
            title="Refresh summary"
          >
            <RefreshCw 
              size={18} 
              className={refreshMutation.isPending ? 'animate-spin' : ''} 
            />
          </button>
          {collapsible && (
            expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />
          )}
        </div>
      </div>
      
      {/* Content */}
      {(!collapsible || expanded) && (
        <div className="p-4 space-y-6">
          {/* AI Generated Summary */}
          <div className="p-4 bg-gradient-to-r from-purple-50 to-blue-50 
            dark:from-purple-900/20 dark:to-blue-900/20 rounded-lg">
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
              {summary.ai_generated_summary}
            </p>
          </div>
          
          {/* Quick Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <Clock className="mx-auto text-blue-500 mb-1" size={20} />
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {summary.metrics.total_hours.toFixed(1)}h
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Total Hours</p>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <Folder className="mx-auto text-purple-500 mb-1" size={20} />
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {summary.metrics.projects_worked}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Projects</p>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <CheckCircle className="mx-auto text-green-500 mb-1" size={20} />
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {summary.metrics.tasks_completed}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Tasks Done</p>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <div className="flex items-center justify-center gap-1 mb-1">
                {getTrendIcon(summary.metrics.trend_vs_previous)}
              </div>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {summary.metrics.trend_vs_previous > 0 ? '+' : ''}
                {summary.metrics.trend_vs_previous.toFixed(0)}%
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">vs Last Week</p>
            </div>
          </div>
          
          {/* Top Projects */}
          {summary.metrics.top_projects.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Top Projects
              </h3>
              <div className="space-y-2">
                {summary.metrics.top_projects.slice(0, 5).map((project: TopProject) => (
                  <div key={project.project_id} className="flex items-center gap-3">
                    <div className="flex-1">
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium text-gray-700 dark:text-gray-300">
                          {project.project_name}
                        </span>
                        <span className="text-gray-500 dark:text-gray-400">
                          {project.hours.toFixed(1)}h ({project.percentage.toFixed(0)}%)
                        </span>
                      </div>
                      <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-purple-500 rounded-full transition-all"
                          style={{ width: `${project.percentage}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Insights */}
          {summary.insights.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Insights
              </h3>
              <div className="space-y-2">
                {summary.insights.slice(0, 5).map((insight: Insight, i: number) => (
                  <div 
                    key={i}
                    className="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-700/50 rounded"
                  >
                    {getInsightIcon(insight.type, insight.severity)}
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        {insight.title}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {insight.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Attention Items */}
          {summary.attention_items.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
                <AlertTriangle size={16} className="text-yellow-500" />
                Needs Attention
              </h3>
              <div className="space-y-2">
                {summary.attention_items.map((item: AttentionItem, i: number) => (
                  <div 
                    key={i}
                    className={`p-3 border rounded ${getAttentionColor(item.severity)}`}
                  >
                    <p className="font-medium text-gray-800 dark:text-gray-200 text-sm">
                      {item.title}
                    </p>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                      {item.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Footer */}
          <div className="text-xs text-gray-400 dark:text-gray-500 text-center">
            Generated {new Date(summary.generated_at).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  );
};

export default WeeklySummaryPanel;
