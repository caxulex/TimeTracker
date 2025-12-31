/**
 * Burnout Risk Panel Component (Phase 4)
 * 
 * Displays burnout risk assessment with:
 * - Risk level indicator
 * - Risk score visualization
 * - Contributing factors breakdown
 * - Trend analysis
 * - Recommendations
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  Heart,
  Clock,
  Calendar,
  Sun,
  Moon,
  RefreshCw
} from 'lucide-react';
import { aiApi } from '../../api/aiServices';

interface BurnoutFactor {
  name: string;
  score: number;
  max_score: number;
  detail: string;
}

interface BurnoutAssessment {
  success: boolean;
  user_id?: number;
  user_name?: string;
  risk_level?: 'low' | 'moderate' | 'high' | 'critical';
  risk_score?: number;
  factors?: BurnoutFactor[];
  recommendations?: string[];
  trend?: 'improving' | 'stable' | 'worsening';
  assessed_at?: string;
  error?: string;
}

interface BurnoutRiskPanelProps {
  userId?: number;
  periodDays?: number;
  compact?: boolean;
  onRefresh?: () => void;
}

const riskColors = {
  low: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-300', progress: 'bg-green-500' },
  moderate: { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-300', progress: 'bg-yellow-500' },
  high: { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-300', progress: 'bg-orange-500' },
  critical: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-300', progress: 'bg-red-500' }
};

const riskLabels = {
  low: 'Low Risk',
  moderate: 'Moderate Risk',
  high: 'High Risk',
  critical: 'Critical Risk'
};

const trendIcons = {
  improving: TrendingDown,
  stable: Minus,
  worsening: TrendingUp
};

const trendColors = {
  improving: 'text-green-600',
  stable: 'text-gray-500',
  worsening: 'text-red-600'
};

export const BurnoutRiskPanel: React.FC<BurnoutRiskPanelProps> = ({
  userId,
  periodDays = 30,
  compact = false,
  onRefresh
}) => {
  const { data, isLoading, error, refetch } = useQuery<BurnoutAssessment>({
    queryKey: ['burnout-assessment', userId, periodDays],
    queryFn: async () => {
      const response = await aiApi.assessBurnoutRisk({ user_id: userId, period_days: periodDays });
      return response as BurnoutAssessment;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false
  });

  const handleRefresh = () => {
    refetch();
    onRefresh?.();
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-4 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="h-24 bg-gray-200 rounded mb-4"></div>
        <div className="space-y-2">
          <div className="h-4 bg-gray-200 rounded w-full"></div>
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
        </div>
      </div>
    );
  }

  if (error || !data?.success) {
    return (
      <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-400">
        <div className="flex items-center gap-2 text-red-600">
          <AlertTriangle className="w-5 h-5" />
          <span className="font-medium">Unable to load burnout assessment</span>
        </div>
        <p className="text-sm text-gray-500 mt-1">{data?.error || 'An error occurred'}</p>
        <button
          onClick={handleRefresh}
          className="mt-2 text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
        >
          <RefreshCw className="w-3 h-3" /> Try again
        </button>
      </div>
    );
  }

  const riskLevel = data.risk_level || 'low';
  const colors = riskColors[riskLevel];
  const TrendIcon = trendIcons[data.trend || 'stable'];

  if (compact) {
    return (
      <div className={`rounded-lg p-3 ${colors.bg} ${colors.border} border`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Heart className={`w-5 h-5 ${colors.text}`} />
            <span className={`font-medium ${colors.text}`}>{riskLabels[riskLevel]}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className={`text-lg font-bold ${colors.text}`}>{data.risk_score?.toFixed(0)}</span>
            <span className={`text-sm ${colors.text}`}>/100</span>
          </div>
        </div>
        {data.trend && (
          <div className={`flex items-center gap-1 mt-1 text-sm ${trendColors[data.trend]}`}>
            <TrendIcon className="w-3 h-3" />
            <span className="capitalize">{data.trend}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className={`px-4 py-3 rounded-t-lg ${colors.bg} ${colors.border} border-b flex justify-between items-center`}>
        <div className="flex items-center gap-2">
          <Heart className={`w-5 h-5 ${colors.text}`} />
          <h3 className={`font-semibold ${colors.text}`}>Burnout Risk Assessment</h3>
        </div>
        <button
          onClick={handleRefresh}
          className={`p-1 rounded hover:bg-white/50 ${colors.text}`}
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        {/* Risk Score */}
        <div className="flex items-center justify-between">
          <div>
            <p className={`text-2xl font-bold ${colors.text}`}>{riskLabels[riskLevel]}</p>
            {data.user_name && (
              <p className="text-sm text-gray-500">For {data.user_name}</p>
            )}
          </div>
          <div className="text-right">
            <p className={`text-3xl font-bold ${colors.text}`}>{data.risk_score?.toFixed(0)}</p>
            <p className="text-sm text-gray-500">out of 100</p>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="relative pt-1">
          <div className="flex mb-2 items-center justify-between">
            <div className="flex items-center gap-2">
              {data.trend && (
                <span className={`flex items-center gap-1 text-sm ${trendColors[data.trend]}`}>
                  <TrendIcon className="w-4 h-4" />
                  <span className="capitalize">{data.trend}</span> trend
                </span>
              )}
            </div>
            <span className="text-xs text-gray-500">
              {data.assessed_at && new Date(data.assessed_at).toLocaleDateString()}
            </span>
          </div>
          <div className="overflow-hidden h-3 text-xs flex rounded-full bg-gray-200">
            <div
              style={{ width: `${data.risk_score || 0}%` }}
              className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center ${colors.progress} transition-all duration-500`}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>Low</span>
            <span>Moderate</span>
            <span>High</span>
            <span>Critical</span>
          </div>
        </div>

        {/* Risk Factors */}
        {data.factors && data.factors.length > 0 && (
          <div className="space-y-3">
            <h4 className="font-medium text-gray-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Risk Factors
            </h4>
            <div className="space-y-2">
              {data.factors.map((factor, index) => (
                <div key={index} className="bg-gray-50 rounded p-2">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm font-medium text-gray-700">
                      {factor.name === 'Overtime Frequency' && <Clock className="w-3 h-3 inline mr-1" />}
                      {factor.name === 'Weekend Work' && <Calendar className="w-3 h-3 inline mr-1" />}
                      {factor.name === 'Late Work Hours' && <Moon className="w-3 h-3 inline mr-1" />}
                      {factor.name === 'Schedule Inconsistency' && <Sun className="w-3 h-3 inline mr-1" />}
                      {factor.name}
                    </span>
                    <span className="text-xs text-gray-500">
                      {factor.score.toFixed(0)} / {factor.max_score}
                    </span>
                  </div>
                  <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${factor.score > factor.max_score * 0.7 ? 'bg-red-500' : factor.score > factor.max_score * 0.4 ? 'bg-yellow-500' : 'bg-green-500'}`}
                      style={{ width: `${(factor.score / factor.max_score) * 100}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{factor.detail}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recommendations */}
        {data.recommendations && data.recommendations.length > 0 && (
          <div className="border-t pt-4">
            <h4 className="font-medium text-gray-700 mb-2">💡 Recommendations</h4>
            <ul className="space-y-1">
              {data.recommendations.map((rec, index) => (
                <li key={index} className="text-sm text-gray-600 flex items-start gap-2">
                  <span className="text-green-500 mt-0.5">•</span>
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default BurnoutRiskPanel;
