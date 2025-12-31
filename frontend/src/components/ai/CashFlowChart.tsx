/**
 * Cash Flow Chart
 * 
 * Displays weekly cash flow projections for payroll obligations.
 */

import React from 'react';
import { 
  DollarSign,
  Calendar,
  AlertTriangle,
  RefreshCw,
  TrendingUp
} from 'lucide-react';
import { useCashFlowForecast } from '../../hooks/useForecastingServices';
import type { CashFlowWeek } from '../../api/forecastingServices';

interface CashFlowChartProps {
  className?: string;
  weeksAhead?: number;
}

export function CashFlowChart({ className = '', weeksAhead = 4 }: CashFlowChartProps) {
  const { data, isLoading, error, refetch } = useCashFlowForecast(weeksAhead);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatDateRange = (start: string, end: string) => {
    const startDate = new Date(start);
    const endDate = new Date(end);
    return `${startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
  };

  // Calculate max value for chart scaling
  const maxValue = data?.forecast 
    ? Math.max(...data.forecast.map(w => w.cumulative), data.average_payroll || 0)
    : 0;

  if (!data?.enabled) {
    return (
      <div className={`bg-white rounded-lg shadow-sm border p-6 ${className}`}>
        <div className="text-center text-gray-500">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-yellow-500" />
          <p>Cash flow forecasting is disabled</p>
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
            <TrendingUp className="w-5 h-5 text-purple-600" />
            <h3 className="text-lg font-semibold text-gray-900">Cash Flow Forecast</h3>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
        {data?.average_payroll && (
          <p className="text-sm text-gray-500 mt-1">
            Average bi-weekly payroll: {formatCurrency(data.average_payroll)}
          </p>
        )}
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
            <p>Failed to load cash flow forecast</p>
          </div>
        ) : data?.forecast.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <Calendar className="w-8 h-8 mx-auto mb-2 text-gray-400" />
            <p>{data?.message || 'No forecast data available'}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Visual Chart */}
            <div className="flex items-end gap-2 h-40 border-b pb-2">
              {data?.forecast.map((week: CashFlowWeek, index: number) => {
                const height = maxValue > 0 ? (week.cumulative / maxValue) * 100 : 0;
                
                return (
                  <div 
                    key={index}
                    className="flex-1 flex flex-col items-center"
                  >
                    <div 
                      className="w-full relative group"
                      style={{ height: '140px' }}
                    >
                      {/* Bar */}
                      <div 
                        className={`absolute bottom-0 w-full rounded-t transition-all ${
                          week.is_payroll_week 
                            ? 'bg-gradient-to-t from-purple-600 to-purple-400' 
                            : 'bg-gradient-to-t from-gray-300 to-gray-200'
                        }`}
                        style={{ height: `${height}%` }}
                      />
                      
                      {/* Payroll indicator */}
                      {week.is_payroll_week && week.projected_payroll > 0 && (
                        <div 
                          className="absolute w-full flex justify-center"
                          style={{ bottom: `${(week.projected_payroll / maxValue) * 100}%` }}
                        >
                          <div className="w-3 h-3 rounded-full bg-purple-600 border-2 border-white shadow-sm" />
                        </div>
                      )}
                      
                      {/* Tooltip */}
                      <div className="absolute -top-10 left-1/2 transform -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap z-10">
                        {week.is_payroll_week 
                          ? `Payroll: ${formatCurrency(week.projected_payroll)}`
                          : 'No payroll'}
                      </div>
                    </div>
                    
                    {/* Week label */}
                    <div className="text-xs text-gray-500 mt-2 text-center">
                      {index === 0 ? 'This' : `+${index}`}
                      {week.is_payroll_week && (
                        <DollarSign className="w-3 h-3 mx-auto text-purple-600 mt-0.5" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Weekly Breakdown */}
            <div className="space-y-2">
              {data?.forecast.map((week: CashFlowWeek, index: number) => (
                <div 
                  key={index}
                  className={`flex items-center justify-between p-3 rounded-lg ${
                    week.is_payroll_week ? 'bg-purple-50 border border-purple-200' : 'bg-gray-50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      week.is_payroll_week ? 'bg-purple-100' : 'bg-gray-100'
                    }`}>
                      {week.is_payroll_week ? (
                        <DollarSign className="w-5 h-5 text-purple-600" />
                      ) : (
                        <Calendar className="w-5 h-5 text-gray-400" />
                      )}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        {formatDateRange(week.week_start, week.week_end)}
                      </div>
                      <div className="text-xs text-gray-500">
                        {week.is_payroll_week ? 'Payroll week' : 'Non-payroll week'}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    {week.is_payroll_week && (
                      <div className="text-sm font-semibold text-purple-600">
                        {formatCurrency(week.projected_payroll)}
                      </div>
                    )}
                    <div className="text-xs text-gray-500">
                      Cumulative: {formatCurrency(week.cumulative)}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Total */}
            {data?.forecast && data.forecast.length > 0 && (
              <div className="mt-4 pt-4 border-t">
                <div className="flex justify-between items-center">
                  <span className="font-medium text-gray-700">
                    Total Payroll ({weeksAhead} weeks)
                  </span>
                  <span className="text-xl font-bold text-gray-900">
                    {formatCurrency(data.forecast[data.forecast.length - 1].cumulative)}
                  </span>
                </div>
              </div>
            )}

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

export default CashFlowChart;
