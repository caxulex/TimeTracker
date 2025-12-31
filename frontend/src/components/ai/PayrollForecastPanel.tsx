/**
 * Payroll Forecast Panel
 * 
 * Displays payroll predictions with trend analysis and confidence intervals.
 */

import React, { useState } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Minus,
  DollarSign,
  Calendar,
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { usePayrollForecast, usePayrollForecastMutation } from '../../hooks/useForecastingServices';
import type { PayrollForecastItem, PayrollForecastRequest } from '../../api/forecastingServices';

interface PayrollForecastPanelProps {
  className?: string;
}

const PERIOD_TYPES = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'bi_weekly', label: 'Bi-Weekly' },
  { value: 'semi_monthly', label: 'Semi-Monthly' },
  { value: 'monthly', label: 'Monthly' }
];

export function PayrollForecastPanel({ className = '' }: PayrollForecastPanelProps) {
  const [periodType, setPeriodType] = useState<string>('bi_weekly');
  const [periodsAhead, setPeriodsAhead] = useState<number>(2);
  const [showDetails, setShowDetails] = useState<boolean>(false);
  
  const { data, isLoading, error, refetch } = usePayrollForecast({
    period_type: periodType as PayrollForecastRequest['period_type'],
    periods_ahead: periodsAhead,
    include_overtime: true
  });
  
  const mutation = usePayrollForecastMutation();

  const handleRefresh = () => {
    mutation.mutate({
      period_type: periodType as PayrollForecastRequest['period_type'],
      periods_ahead: periodsAhead,
      include_overtime: true
    });
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'increasing':
        return <TrendingUp className="w-5 h-5 text-red-500" />;
      case 'decreasing':
        return <TrendingDown className="w-5 h-5 text-green-500" />;
      default:
        return <Minus className="w-5 h-5 text-gray-500" />;
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-100';
    if (confidence >= 0.6) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    });
  };

  if (!data?.enabled) {
    return (
      <div className={`bg-white rounded-lg shadow-sm border p-6 ${className}`}>
        <div className="text-center text-gray-500">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-yellow-500" />
          <p>Payroll forecasting is disabled</p>
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
            <DollarSign className="w-5 h-5 text-green-600" />
            <h3 className="text-lg font-semibold text-gray-900">Payroll Forecast</h3>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isLoading || mutation.isPending}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${(isLoading || mutation.isPending) ? 'animate-spin' : ''}`} />
          </button>
        </div>
        
        {/* Filters */}
        <div className="mt-3 flex gap-4">
          <select
            value={periodType}
            onChange={(e) => setPeriodType(e.target.value)}
            className="text-sm border rounded-md px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {PERIOD_TYPES.map(pt => (
              <option key={pt.value} value={pt.value}>{pt.label}</option>
            ))}
          </select>
          <select
            value={periodsAhead}
            onChange={(e) => setPeriodsAhead(Number(e.target.value))}
            className="text-sm border rounded-md px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {[1, 2, 3, 4, 5, 6].map(n => (
              <option key={n} value={n}>{n} period{n > 1 ? 's' : ''}</option>
            ))}
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
            <p>Failed to load forecast</p>
          </div>
        ) : data?.forecasts.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <Calendar className="w-8 h-8 mx-auto mb-2 text-gray-400" />
            <p>{data?.message || 'No forecast data available'}</p>
            <p className="text-sm mt-1">Need at least 3 completed payroll periods</p>
          </div>
        ) : (
          <div className="space-y-4">
            {data?.forecasts.map((forecast: PayrollForecastItem, index: number) => (
              <div 
                key={index}
                className="border rounded-lg p-4 hover:border-blue-300 transition-colors"
              >
                {/* Period Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    <span className="font-medium text-gray-700">
                      {formatDate(forecast.period_start)} - {formatDate(forecast.period_end)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {getTrendIcon(forecast.trend)}
                    <span className={`text-xs px-2 py-1 rounded-full ${getConfidenceColor(forecast.confidence)}`}>
                      {Math.round(forecast.confidence * 100)}% confidence
                    </span>
                  </div>
                </div>

                {/* Main Prediction */}
                <div className="text-3xl font-bold text-gray-900 mb-2">
                  {formatCurrency(forecast.predicted_total)}
                </div>

                {/* Range */}
                <div className="text-sm text-gray-500 mb-3">
                  Range: {formatCurrency(forecast.lower_bound)} - {formatCurrency(forecast.upper_bound)}
                </div>

                {/* Breakdown */}
                <div className="grid grid-cols-2 gap-4 pt-3 border-t">
                  <div>
                    <div className="text-sm text-gray-500">Regular</div>
                    <div className="font-semibold text-gray-700">
                      {formatCurrency(forecast.predicted_regular)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500">Overtime</div>
                    <div className="font-semibold text-orange-600">
                      {formatCurrency(forecast.predicted_overtime)}
                    </div>
                  </div>
                </div>

                {/* Factors */}
                {forecast.factors.length > 0 && (
                  <div className="mt-3 pt-3 border-t">
                    <button
                      onClick={() => setShowDetails(!showDetails)}
                      className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
                    >
                      {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      Contributing factors
                    </button>
                    {showDetails && (
                      <ul className="mt-2 space-y-1">
                        {forecast.factors.map((factor, i) => (
                          <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                            <span className={factor.impact === 'positive' ? 'text-red-500' : 'text-green-500'}>
                              {factor.impact === 'positive' ? '↑' : '↓'}
                            </span>
                            {factor.description}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* Meta info */}
            {data?.historical_periods_used && (
              <p className="text-xs text-gray-400 text-center mt-4">
                Based on {data.historical_periods_used} historical periods
                {data.generated_at && ` • Updated ${new Date(data.generated_at).toLocaleTimeString()}`}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default PayrollForecastPanel;
