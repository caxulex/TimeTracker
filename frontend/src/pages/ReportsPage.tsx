// ============================================
// TIME TRACKER - REPORTS PAGE
// ============================================
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, LoadingOverlay, Button } from '../components/common';
import { reportsApi, exportApi } from '../api/client';
import { formatDuration, toISODateString, getStartOfWeek, secondsToHours, isAdminUser } from '../utils/helpers';
import { useAuth } from '../hooks/useAuth';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { useStaffNotifications } from '../hooks/useStaffNotifications';
import type { WeeklySummary } from '../types';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316'];

type DatePreset = 'this-week' | 'last-week' | 'this-month' | 'last-month' | 'custom';
type ExportFormat = 'csv' | 'excel' | 'pdf';

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export function ReportsPage() {
  const { user } = useAuth();
  const isAdmin = isAdminUser(user);
  const queryClient = useQueryClient();
  const { lastMessage } = useWebSocketContext();
  const notifications = useStaffNotifications();

  const [datePreset, setDatePreset] = useState<DatePreset>('this-week');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  const [showExportMenu, setShowExportMenu] = useState(false);
  
  // Listen for real-time time entry changes via WebSocket
  useEffect(() => {
    if (!lastMessage) return;
    
    const messageType = lastMessage.type;
    
    // Refresh reports when time entries are created, updated, completed, or deleted
    if (
      messageType === 'time_entry_created' ||
      messageType === 'time_entry_completed' ||
      messageType === 'time_entry_updated' ||
      messageType === 'time_entry_deleted'
    ) {
      // Invalidate and refetch report queries to get updated data
      queryClient.invalidateQueries({ queryKey: ['weekly-report'] });
      queryClient.invalidateQueries({ queryKey: ['project-report'] });
    }
  }, [lastMessage, queryClient]);

  // Calculate date range based on preset
  const getDateRange = () => {
    const today = new Date();
    let startDate: Date;
    let endDate: Date = today;

    switch (datePreset) {
      case 'this-week':
        startDate = getStartOfWeek(today);
        break;
      case 'last-week':
        startDate = getStartOfWeek(new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000));
        endDate = new Date(startDate.getTime() + 6 * 24 * 60 * 60 * 1000);
        break;
      case 'this-month':
        startDate = new Date(today.getFullYear(), today.getMonth(), 1);
        break;
      case 'last-month':
        startDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        endDate = new Date(today.getFullYear(), today.getMonth(), 0);
        break;
      case 'custom':
        return {
          startDate: customStartDate,
          endDate: customEndDate,
        };
      default:
        startDate = getStartOfWeek(today);
    }

    return {
      startDate: toISODateString(startDate),
      endDate: toISODateString(endDate),
    };
  };

  const { startDate, endDate } = getDateRange();

  // Export mutations
  const exportMutation = useMutation({
    mutationFn: async (format: ExportFormat): Promise<{ blob: Blob; ext: string; format: string }> => {
      const params = { start_date: startDate, end_date: endDate };
      switch (format) {
        case 'csv':
          return { blob: await exportApi.downloadCsv(params), ext: 'csv', format: 'CSV' };
        case 'excel':
          return { blob: await exportApi.downloadExcel(params), ext: 'xlsx', format: 'Excel' };
        case 'pdf':
          return { blob: await exportApi.downloadPdf(params), ext: 'pdf', format: 'PDF' };
        default:
          throw new Error(`Unsupported export format: ${format}`);
      }
    },
    onSuccess: (data) => {
      if (data && data.blob) {
        const filename = `time_report_${startDate}_to_${endDate}.${data.ext}`;
        downloadBlob(data.blob, filename);
        setShowExportMenu(false);
        notifications.notifySuccess('Export Complete', `Your ${data.format} report has been downloaded.`);
      }
    },
    onError: (error: any) => {
      console.error('Export failed:', error);
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to export report';
      notifications.notifyError('Export Failed', errorMessage);
      setShowExportMenu(false);
    },
  });

  // Fetch weekly summary (user's own data)
  const { data: weeklyData, isLoading: weeklyLoading } = useQuery<WeeklySummary>({
    queryKey: ['weekly-report', startDate],
    queryFn: () => reportsApi.getWeekly(startDate),
    enabled: !!startDate,
  });

  // Fetch project breakdown (user's own data)
  const { data: projectData, isLoading: projectLoading } = useQuery({
    queryKey: ['project-report', startDate, endDate],
    queryFn: () => reportsApi.getByProject(startDate, endDate),
    enabled: !!startDate && !!endDate,
  });

  const isLoading = weeklyLoading || projectLoading;

  // Prepare chart data
  const dailyChartData = weeklyData?.daily_breakdown?.map((day) => ({
    name: new Date(day.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
    hours: secondsToHours(day.total_seconds),
    entries: day.entry_count,
  })) || [];

  const totalProjectSeconds = projectData?.reduce((sum: number, p: any) => sum + p.total_seconds, 0) || 0;

  const projectChartData = projectData?.map((project: any) => ({
    name: project.project_name,
    value: project.total_seconds,
    hours: secondsToHours(project.total_seconds),
    percentage: totalProjectSeconds > 0 ? Math.round((project.total_seconds / totalProjectSeconds) * 100) : 0,
  })) || [];

  // Calculate totals
  const totalSeconds = weeklyData?.total_seconds || 0;
  const totalHours = secondsToHours(totalSeconds);
  const avgHoursPerDay = dailyChartData.length > 0
    ? Math.round((totalHours / dailyChartData.length) * 10) / 10
    : 0;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {isAdmin ? 'Reports' : 'My Reports'}
          </h1>
          <p className="text-gray-500">
            {isAdmin ? 'Analyze time tracking data' : 'View your personal time tracking data'}
          </p>
        </div>
        
        {/* Export Dropdown */}
        <div className="relative">
          <Button 
            variant="secondary"
            onClick={() => setShowExportMenu(!showExportMenu)}
            disabled={exportMutation.isPending}
          >
            {exportMutation.isPending ? (
              <>
                <svg className="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Exporting...
              </>
            ) : (
              <>
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Export
                <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </>
            )}
          </Button>
          
          {showExportMenu && (
            <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10">
              <button
                onClick={() => exportMutation.mutate('csv')}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
              >
                <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Export as CSV
              </button>
              <button
                onClick={() => exportMutation.mutate('excel')}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
              >
                <svg className="w-4 h-4 text-green-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Export as Excel
              </button>
              <button
                onClick={() => exportMutation.mutate('pdf')}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
              >
                <svg className="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                Export as PDF
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Info banner for workers */}
      {!isAdmin && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm text-blue-800">
              This report shows only your personal time entries.
            </p>
          </div>
        </div>
      )}

      {/* Date filters */}
      <Card padding="sm">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex gap-2">
            {[
              { value: 'this-week', label: 'This Week' },
              { value: 'last-week', label: 'Last Week' },
              { value: 'this-month', label: 'This Month' },
              { value: 'last-month', label: 'Last Month' },
              { value: 'custom', label: 'Custom' },
            ].map((preset) => (
              <button
                key={preset.value}
                onClick={() => setDatePreset(preset.value as DatePreset)}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  datePreset === preset.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          {datePreset === 'custom' && (
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={customStartDate}
                onChange={(e) => setCustomStartDate(e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-gray-500">to</span>
              <input
                type="date"
                value={customEndDate}
                onChange={(e) => setCustomEndDate(e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}
        </div>
      </Card>

      {isLoading ? (
        <LoadingOverlay message="Loading report data..." />
      ) : (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <div className="text-center">
                <p className="text-sm text-gray-500 mb-1">Total Hours</p>
                <p className="text-3xl font-bold text-blue-600">{totalHours.toFixed(1)}h</p>
                <p className="text-xs text-gray-400 mt-1">{formatDuration(totalSeconds)}</p>
              </div>
            </Card>
            <Card>
              <div className="text-center">
                <p className="text-sm text-gray-500 mb-1">Avg Hours/Day</p>
                <p className="text-3xl font-bold text-green-600">{avgHoursPerDay}h</p>
                <p className="text-xs text-gray-400 mt-1">across {dailyChartData.length} days</p>
              </div>
            </Card>
            <Card>
              <div className="text-center">
                <p className="text-sm text-gray-500 mb-1">Active Projects</p>
                <p className="text-3xl font-bold text-purple-600">{projectChartData.length}</p>
                <p className="text-xs text-gray-400 mt-1">in this period</p>
              </div>
            </Card>
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Daily Hours Chart */}
            <Card>
              <CardHeader title="Daily Hours" />
              <div className="h-64">
                {dailyChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dailyChartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" fontSize={12} />
                      <YAxis fontSize={12} />
                      <Tooltip
                        formatter={(value: number) => [`${value.toFixed(1)}h`, 'Hours']}
                      />
                      <Bar dataKey="hours" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-500">
                    No data for selected period
                  </div>
                )}
              </div>
            </Card>

            {/* Project Distribution */}
            <Card>
              <CardHeader title="Time by Project" />
              <div className="h-64">
                {projectChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={projectChartData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percentage }) => `${name}: ${percentage}%`}
                        outerRadius={80}
                        dataKey="value"
                      >
                        {projectChartData.map((_entry: any, index: number) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value: number) => [formatDuration(value), 'Time']}
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-500">
                    No projects in selected period
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Project Details Table */}
          {projectChartData.length > 0 && (
            <Card>
              <CardHeader title="Project Breakdown" />
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Project
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Hours
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Percentage
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Distribution
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {projectChartData.map((project: any, index: number) => (
                      <tr key={project.name}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <div
                              className="w-3 h-3 rounded-full mr-3"
                              style={{ backgroundColor: COLORS[index % COLORS.length] }}
                            />
                            <span className="font-medium text-gray-900">{project.name}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                          {project.hours.toFixed(1)}h
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                          {project.percentage}%
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="w-full bg-gray-200 rounded-full h-2.5">
                            <div
                              className="h-2.5 rounded-full"
                              style={{
                                width: `${project.percentage}%`,
                                backgroundColor: COLORS[index % COLORS.length],
                              }}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

