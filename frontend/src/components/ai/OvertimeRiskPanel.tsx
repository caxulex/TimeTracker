/**
 * Overtime Risk Panel
 * 
 * Displays employees at risk of exceeding overtime thresholds.
 */

import React, { useState } from 'react';
import { 
  Clock,
  AlertTriangle,
  AlertCircle,
  User,
  RefreshCw,
  TrendingUp,
  DollarSign,
  Filter
} from 'lucide-react';
import { useOvertimeRisk, useOvertimeRiskMutation } from '../../hooks/useForecastingServices';
import type { OvertimeRiskItem } from '../../api/forecastingServices';

interface OvertimeRiskPanelProps {
  className?: string;
  teamId?: number;
}

export function OvertimeRiskPanel({ className = '', teamId }: OvertimeRiskPanelProps) {
  const [daysAhead, setDaysAhead] = useState<number>(7);
  
  const { data, isLoading, error } = useOvertimeRisk({
    days_ahead: daysAhead,
    team_id: teamId
  });
  
  const mutation = useOvertimeRiskMutation();

  const handleRefresh = () => {
    mutation.mutate({ days_ahead: daysAhead, team_id: teamId });
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'critical':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
            <AlertTriangle className="w-3 h-3" />
            Critical
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
            <AlertCircle className="w-3 h-3" />
            High
          </span>
        );
      case 'medium':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
            <Clock className="w-3 h-3" />
            Medium
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
            Low
          </span>
        );
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const getProgressColor = (current: number, threshold: number) => {
    const ratio = current / threshold;
    if (ratio >= 1) return 'bg-red-500';
    if (ratio >= 0.9) return 'bg-orange-500';
    if (ratio >= 0.75) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  if (!data?.enabled) {
    return (
      <div className={`bg-white rounded-lg shadow-sm border p-6 ${className}`}>
        <div className="text-center text-gray-500">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-yellow-500" />
          <p>Overtime risk assessment is disabled</p>
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
            <Clock className="w-5 h-5 text-orange-600" />
            <h3 className="text-lg font-semibold text-gray-900">Overtime Risk</h3>
            {data?.users_at_risk !== undefined && data.users_at_risk > 0 && (
              <span className="ml-2 bg-red-100 text-red-800 text-xs px-2 py-0.5 rounded-full">
                {data.users_at_risk} at risk
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
        
        {/* Filter */}
        <div className="mt-3 flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={daysAhead}
            onChange={(e) => setDaysAhead(Number(e.target.value))}
            className="text-sm border rounded-md px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value={7}>This week</option>
            <option value={14}>Next 2 weeks</option>
            <option value={30}>This month</option>
          </select>
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
            <p>Failed to load risk assessment</p>
          </div>
        ) : data?.risks.length === 0 ? (
          <div className="text-center text-green-600 py-8">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-green-100 flex items-center justify-center">
              <Clock className="w-6 h-6" />
            </div>
            <p className="font-medium">No overtime risks detected</p>
            <p className="text-sm text-gray-500 mt-1">
              All employees are on track for normal hours
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Summary Stats */}
            {data && (
              <div className="grid grid-cols-3 gap-4 mb-4 p-4 bg-gray-50 rounded-lg">
                <div className="text-center">
                  <div className="text-2xl font-bold text-gray-900">{data.users_assessed}</div>
                  <div className="text-xs text-gray-500">Assessed</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-orange-600">{data.users_at_risk}</div>
                  <div className="text-xs text-gray-500">At Risk</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-red-600">
                    {data.risks.filter(r => r.risk_level === 'critical').length}
                  </div>
                  <div className="text-xs text-gray-500">Critical</div>
                </div>
              </div>
            )}

            {/* Risk Cards */}
            {data?.risks.map((risk: OvertimeRiskItem) => (
              <div 
                key={risk.user_id}
                className={`border rounded-lg p-4 ${
                  risk.risk_level === 'critical' 
                    ? 'border-red-200 bg-red-50' 
                    : risk.risk_level === 'high'
                    ? 'border-orange-200 bg-orange-50'
                    : 'border-yellow-200 bg-yellow-50'
                }`}
              >
                {/* User Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                      <User className="w-4 h-4 text-gray-600" />
                    </div>
                    <span className="font-medium text-gray-900">{risk.user_name}</span>
                  </div>
                  {getRiskBadge(risk.risk_level)}
                </div>

                {/* Progress Bar */}
                <div className="mb-3">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">Hours this week</span>
                    <span className="font-medium">
                      {risk.current_hours.toFixed(1)}h / {risk.overtime_threshold}h
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${getProgressColor(risk.current_hours, risk.overtime_threshold)} transition-all`}
                      style={{ width: `${Math.min((risk.current_hours / risk.overtime_threshold) * 100, 100)}%` }}
                    />
                  </div>
                </div>

                {/* Projection */}
                <div className="grid grid-cols-2 gap-4 mb-3">
                  <div className="bg-white bg-opacity-60 rounded p-2">
                    <div className="flex items-center gap-1 text-sm text-gray-500">
                      <TrendingUp className="w-3 h-3" />
                      Projected
                    </div>
                    <div className="font-semibold text-gray-900">
                      {risk.projected_hours.toFixed(1)}h
                    </div>
                  </div>
                  <div className="bg-white bg-opacity-60 rounded p-2">
                    <div className="flex items-center gap-1 text-sm text-gray-500">
                      <DollarSign className="w-3 h-3" />
                      Est. Cost
                    </div>
                    <div className="font-semibold text-red-600">
                      {formatCurrency(risk.estimated_cost)}
                    </div>
                  </div>
                </div>

                {/* Recommendation */}
                <div className="text-sm text-gray-700 bg-white bg-opacity-60 rounded p-2">
                  <span className="font-medium">💡 </span>
                  {risk.recommendation}
                </div>
              </div>
            ))}

            {/* Meta info */}
            {data?.period && (
              <p className="text-xs text-gray-400 text-center mt-4">
                Period: {data.period}
                {data.generated_at && ` • Updated ${new Date(data.generated_at).toLocaleTimeString()}`}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default OvertimeRiskPanel;
