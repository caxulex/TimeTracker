/**
 * Payroll Reports Page
 * Generate and export payroll reports for payables department
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  FileText, 
  Download, 
  Filter, 
  Calendar, 
  DollarSign,
  Users,
  Clock,
  AlertCircle,
  TrendingUp,
  BarChart3
} from 'lucide-react';
import { payrollReportsApi, payrollPeriodsApi } from '../api/payroll';
import { 
  PayrollReportFilters, 
  PayablesDepartmentReport,
  PeriodStatus,
  PeriodType
} from '../types/payroll';

// Status Labels
const STATUS_LABELS: Record<PeriodStatus, string> = {
  draft: 'Draft',
  processing: 'Processing',
  approved: 'Approved',
  paid: 'Paid',
  void: 'Void',
};

// Period Type Labels
const PERIOD_TYPE_LABELS: Record<PeriodType, string> = {
  weekly: 'Weekly',
  bi_weekly: 'Bi-Weekly',
  semi_monthly: 'Semi-Monthly',
  monthly: 'Monthly',
};

export const PayrollReportsPage: React.FC = () => {
  const [filters, setFilters] = useState<PayrollReportFilters>({});
  const [showFilters, setShowFilters] = useState(false);

  // Fetch available periods for filter dropdown
  const { data: periodsData } = useQuery({
    queryKey: ['payrollPeriodsForFilter'],
    queryFn: () => payrollPeriodsApi.list(0, 200),
  });

  // Fetch report data
  const { data: reportData, isLoading, error, refetch } = useQuery({
    queryKey: ['payrollReport', filters],
    queryFn: () => payrollReportsApi.getPayablesReportQuery(filters),
  });

  // Handle filter changes
  const handleFilterChange = (field: keyof PayrollReportFilters, value: string | undefined) => {
    setFilters(prev => ({
      ...prev,
      [field]: value || undefined,
    }));
  };

  // Clear filters
  const clearFilters = () => {
    setFilters({});
  };

  // Export to CSV
  const handleExportCsv = async () => {
    try {
      const blob = await payrollReportsApi.exportCsv(filters);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `payroll_report_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error exporting CSV:', error);
      alert('Failed to export CSV');
    }
  };

  // Export to Excel
  const handleExportExcel = async () => {
    try {
      const blob = await payrollReportsApi.exportExcel(filters);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `payroll_report_${new Date().toISOString().split('T')[0]}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error exporting Excel:', error);
      alert('Failed to export Excel. Make sure openpyxl is installed on the server.');
    }
  };

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  // Format hours
  const formatHours = (hours: number) => {
    return Number(hours).toFixed(2);
  };

  if (error) {
    return (
      <div className="p-6">
        <div className="p-4 bg-red-50 text-red-600 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          Error loading report data
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Payroll Reports</h1>
          <p className="text-gray-600">Generate and export payroll reports for payables</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2 border rounded-lg transition ${
              showFilters ? 'bg-blue-50 border-blue-300 text-blue-700' : 'border-gray-300 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <Filter className="w-4 h-4" />
            Filters
          </button>
          <button
            onClick={handleExportCsv}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 transition"
          >
            <Download className="w-4 h-4" />
            CSV
          </button>
          <button
            onClick={handleExportExcel}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
          >
            <Download className="w-4 h-4" />
            Excel
          </button>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Period
              </label>
              <select
                value={filters.period_id || ''}
                onChange={(e) => handleFilterChange('period_id', e.target.value ? parseInt(e.target.value).toString() : undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Periods</option>
                {periodsData?.items.map(period => (
                  <option key={period.id} value={period.id}>
                    {period.name}
                  </option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <select
                value={filters.status || ''}
                onChange={(e) => handleFilterChange('status', e.target.value || undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Statuses</option>
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Period Type
              </label>
              <select
                value={filters.period_type || ''}
                onChange={(e) => handleFilterChange('period_type', e.target.value || undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Types</option>
                {Object.entries(PERIOD_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Start Date
              </label>
              <input
                type="date"
                value={filters.start_date || ''}
                onChange={(e) => handleFilterChange('start_date', e.target.value || undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                End Date
              </label>
              <input
                type="date"
                value={filters.end_date || ''}
                onChange={(e) => handleFilterChange('end_date', e.target.value || undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="flex justify-end mt-4">
            <button
              onClick={clearFilters}
              className="text-sm text-gray-600 hover:text-gray-800"
            >
              Clear All Filters
            </button>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      {reportData && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-600 mb-1">
              <Users className="w-4 h-4" />
              <span className="text-sm">Employees</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">
              {reportData.summary.total_employees}
            </p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-600 mb-1">
              <Clock className="w-4 h-4" />
              <span className="text-sm">Regular Hours</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">
              {formatHours(reportData.summary.total_regular_hours)}
            </p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-orange-600 mb-1">
              <TrendingUp className="w-4 h-4" />
              <span className="text-sm">OT Hours</span>
            </div>
            <p className="text-2xl font-bold text-orange-600">
              {formatHours(reportData.summary.total_overtime_hours)}
            </p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-600 mb-1">
              <BarChart3 className="w-4 h-4" />
              <span className="text-sm">Gross</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(reportData.summary.total_gross_amount)}
            </p>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-purple-600 mb-1">
              <FileText className="w-4 h-4" />
              <span className="text-sm">Adjustments</span>
            </div>
            <p className="text-2xl font-bold text-purple-600">
              {formatCurrency(reportData.summary.total_adjustments)}
            </p>
          </div>
          
          <div className="bg-green-50 rounded-lg shadow-sm border border-green-200 p-4">
            <div className="flex items-center gap-2 text-green-600 mb-1">
              <DollarSign className="w-4 h-4" />
              <span className="text-sm">Net Total</span>
            </div>
            <p className="text-2xl font-bold text-green-700">
              {formatCurrency(reportData.summary.total_net_amount)}
            </p>
          </div>
        </div>
      )}

      {/* Report Info */}
      {reportData && (
        <div className="bg-blue-50 rounded-lg p-4 flex items-center justify-between">
          <div>
            <p className="text-sm text-blue-600">
              <span className="font-medium">Report Period:</span> {reportData.report_period}
            </p>
            <p className="text-xs text-blue-500">
              Generated: {new Date(reportData.report_generated_at).toLocaleString()}
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="text-sm text-blue-600 hover:text-blue-700"
          >
            Refresh Data
          </button>
        </div>
      )}

      {/* Report Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : reportData && reportData.entries.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Employee
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Period
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Regular Hours
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    OT Hours
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Regular Rate
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    OT Rate
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Gross
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Adjustments
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Net Amount
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {reportData.entries.map((entry, index) => (
                  <tr key={`${entry.user_id}-${entry.period_name}-${index}`} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{entry.user_name}</div>
                      <div className="text-xs text-gray-500">{entry.user_email}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{entry.period_name}</div>
                      <div className="text-xs text-gray-500">
                        {entry.start_date} - {entry.end_date}
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900">
                      {formatHours(entry.regular_hours)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-orange-600">
                      {formatHours(entry.overtime_hours)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-500">
                      {formatCurrency(entry.regular_rate)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-500">
                      {formatCurrency(entry.overtime_rate)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900">
                      {formatCurrency(entry.gross_amount)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right">
                      <span className={entry.adjustments_total >= 0 ? 'text-green-600' : 'text-red-600'}>
                        {formatCurrency(entry.adjustments_total)}
                      </span>
                      {entry.adjustments.length > 0 && (
                        <div className="text-xs text-gray-400">
                          ({entry.adjustments.length} items)
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right font-medium text-gray-900">
                      {formatCurrency(entry.net_amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-gray-50">
                <tr>
                  <td colSpan={2} className="px-4 py-3 text-sm font-medium text-gray-900">
                    TOTALS
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-medium text-gray-900">
                    {formatHours(reportData.summary.total_regular_hours)}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-medium text-orange-600">
                    {formatHours(reportData.summary.total_overtime_hours)}
                  </td>
                  <td colSpan={2}></td>
                  <td className="px-4 py-3 text-sm text-right font-medium text-gray-900">
                    {formatCurrency(reportData.summary.total_gross_amount)}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-medium text-purple-600">
                    {formatCurrency(reportData.summary.total_adjustments)}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-bold text-green-700">
                    {formatCurrency(reportData.summary.total_net_amount)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-gray-500">
            <FileText className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>No payroll data found for the selected filters</p>
            {Object.keys(filters).length > 0 && (
              <button
                onClick={clearFilters}
                className="mt-2 text-blue-600 hover:text-blue-700"
              >
                Clear filters to see all data
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PayrollReportsPage;
