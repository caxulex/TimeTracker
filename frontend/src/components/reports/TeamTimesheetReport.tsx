// ============================================
// TEAM TIMESHEET REPORT COMPONENT
// ============================================
// Displays a grid of hours worked per user per day
// with horizontal (user) and vertical (day) totals

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { reportsApi } from '../../api/client';
import { Card, CardHeader, LoadingOverlay, Button } from '../common';
import { toISODateString, getStartOfWeek } from '../../utils/helpers';
import type { TeamTimesheetReport as TeamTimesheetReportType } from '../../types';

type DatePreset = 'this-week' | 'last-week' | 'this-pay-period' | 'last-pay-period' | 'custom';
type ExportFormat = 'csv' | 'excel';

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

interface Props {
  className?: string;
}

export function TeamTimesheetReport({ className = '' }: Props) {
  const [datePreset, setDatePreset] = useState<DatePreset>('this-week');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');

  // Calculate date range based on preset
  const getDateRange = () => {
    const today = new Date();
    let startDate: Date;
    let endDate: Date = today;

    switch (datePreset) {
      case 'this-week':
        startDate = getStartOfWeek(today);
        endDate = new Date(startDate.getTime() + 6 * 24 * 60 * 60 * 1000);
        break;
      case 'last-week':
        startDate = getStartOfWeek(new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000));
        endDate = new Date(startDate.getTime() + 6 * 24 * 60 * 60 * 1000);
        break;
      case 'this-pay-period':
        // Bi-weekly pay period (1st-15th or 16th-end of month)
        if (today.getDate() <= 15) {
          startDate = new Date(today.getFullYear(), today.getMonth(), 1);
          endDate = new Date(today.getFullYear(), today.getMonth(), 15);
        } else {
          startDate = new Date(today.getFullYear(), today.getMonth(), 16);
          endDate = new Date(today.getFullYear(), today.getMonth() + 1, 0); // Last day of month
        }
        break;
      case 'last-pay-period':
        // Previous bi-weekly pay period
        if (today.getDate() <= 15) {
          // We're in first half, last period was 16th-end of previous month
          const prevMonth = new Date(today.getFullYear(), today.getMonth() - 1, 16);
          startDate = prevMonth;
          endDate = new Date(today.getFullYear(), today.getMonth(), 0);
        } else {
          // We're in second half, last period was 1st-15th of current month
          startDate = new Date(today.getFullYear(), today.getMonth(), 1);
          endDate = new Date(today.getFullYear(), today.getMonth(), 15);
        }
        break;
      case 'custom':
        return {
          startDate: customStartDate,
          endDate: customEndDate,
        };
      default:
        startDate = getStartOfWeek(today);
        endDate = new Date(startDate.getTime() + 6 * 24 * 60 * 60 * 1000);
    }

    return {
      startDate: toISODateString(startDate),
      endDate: toISODateString(endDate),
    };
  };

  const { startDate, endDate } = getDateRange();

  // Fetch team timesheet data
  const { data: timesheetData, isLoading, error } = useQuery<TeamTimesheetReportType>({
    queryKey: ['team-timesheet', startDate, endDate],
    queryFn: () => reportsApi.getTeamTimesheet(startDate, endDate),
    enabled: !!startDate && !!endDate,
  });

  // Export mutations
  const [showExportMenu, setShowExportMenu] = useState(false);
  
  const exportMutation = useMutation({
    mutationFn: async (format: ExportFormat): Promise<{ blob: Blob; ext: string; formatName: string }> => {
      if (format === 'csv') {
        const blob = await reportsApi.exportTeamTimesheetCsv(startDate, endDate);
        return { blob, ext: 'csv', formatName: 'CSV' };
      } else {
        const blob = await reportsApi.exportTeamTimesheetExcel(startDate, endDate);
        return { blob, ext: 'xlsx', formatName: 'Excel' };
      }
    },
    onSuccess: (data) => {
      const filename = `team_timesheet_${startDate}_to_${endDate}.${data.ext}`;
      downloadBlob(data.blob, filename);
      setShowExportMenu(false);
    },
    onError: (error: Error) => {
      console.error('Export failed:', error);
      setShowExportMenu(false);
    },
  });

  // Format date for column header (e.g., "Mon 1/15")
  const formatDateHeader = (dateStr: string) => {
    const date = new Date(dateStr + 'T00:00:00');
    const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
    const monthDay = date.toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' });
    return { dayName, monthDay };
  };

  // Get role badge color
  const getRoleBadgeColor = (role: string) => {
    const normalizedRole = role.toLowerCase().replace(/\s+/g, '_');
    switch (normalizedRole) {
      case 'super_admin':
        return 'bg-purple-100 text-purple-800';
      case 'admin':
      case 'company_admin':
        return 'bg-blue-100 text-blue-800';
      case 'manager':
        return 'bg-green-100 text-green-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Date Preset Selector */}
      <Card padding="sm">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex gap-2 flex-wrap">
            {[
              { value: 'this-week', label: 'This Week' },
              { value: 'last-week', label: 'Last Week' },
              { value: 'this-pay-period', label: 'This Pay Period' },
              { value: 'last-pay-period', label: 'Last Pay Period' },
              { value: 'custom', label: 'Custom' },
            ].map((preset) => (
              <button
                key={preset.value}
                onClick={() => setDatePreset(preset.value as DatePreset)}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  datePreset === preset.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
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
                className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
              />
              <span className="text-gray-500 dark:text-gray-400">to</span>
              <input
                type="date"
                value={customEndDate}
                onChange={(e) => setCustomEndDate(e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
              />
            </div>
          )}

          {/* Export Dropdown */}
          {timesheetData && timesheetData.users.length > 0 && (
            <div className="relative ml-auto">
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
                <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-20">
                  <button
                    onClick={() => exportMutation.mutate('csv')}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                  >
                    <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Export as CSV
                  </button>
                  <button
                    onClick={() => exportMutation.mutate('excel')}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                  >
                    <svg className="w-4 h-4 text-green-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Export as Excel
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Timesheet Table */}
      <Card>
        <CardHeader 
          title="Team Timesheet" 
          subtitle={startDate && endDate ? `${startDate} to ${endDate}` : undefined}
        />
        
        {isLoading ? (
          <div className="py-12">
            <LoadingOverlay message="Loading timesheet data..." />
          </div>
        ) : error ? (
          <div className="p-6 text-center">
            <div className="text-red-500 mb-2">
              <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <p className="text-gray-600 dark:text-gray-400">
              {error instanceof Error ? error.message : 'Failed to load timesheet data'}
            </p>
          </div>
        ) : !timesheetData || timesheetData.users.length === 0 ? (
          <div className="p-6 text-center">
            <div className="text-gray-400 mb-2">
              <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-gray-600 dark:text-gray-400">No timesheet data for this period</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  {/* Member column header */}
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider sticky left-0 bg-gray-50 dark:bg-gray-800 z-10 min-w-[200px]">
                    Member
                  </th>
                  
                  {/* Date column headers */}
                  {timesheetData.dates.map((dateStr) => {
                    const { dayName, monthDay } = formatDateHeader(dateStr);
                    const isWeekend = new Date(dateStr + 'T00:00:00').getDay() % 6 === 0;
                    return (
                      <th 
                        key={dateStr} 
                        className={`px-3 py-3 text-center text-xs font-medium uppercase tracking-wider min-w-[70px] ${
                          isWeekend 
                            ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500' 
                            : 'text-gray-500 dark:text-gray-400'
                        }`}
                      >
                        <div>{dayName}</div>
                        <div className="text-[10px] font-normal">{monthDay}</div>
                      </th>
                    );
                  })}
                  
                  {/* Total column header */}
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider bg-blue-50 dark:bg-blue-900/30 min-w-[80px]">
                    Total
                  </th>
                </tr>
              </thead>
              
              <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                {/* User rows */}
                {timesheetData.users.map((user) => (
                  <tr key={user.user_id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    {/* Member name and role */}
                    <td className="px-4 py-3 whitespace-nowrap sticky left-0 bg-white dark:bg-gray-900 z-10">
                      <div className="flex flex-col">
                        <span className="font-medium text-gray-900 dark:text-white">
                          {user.user_name}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded-full w-fit mt-1 ${getRoleBadgeColor(user.role)}`}>
                          {user.role}
                        </span>
                      </div>
                    </td>
                    
                    {/* Daily hours cells */}
                    {user.daily_hours.map((dayEntry) => {
                      const isWeekend = new Date(dayEntry.date + 'T00:00:00').getDay() % 6 === 0;
                      const hasHours = dayEntry.seconds > 0;
                      return (
                        <td 
                          key={dayEntry.date} 
                          className={`px-3 py-3 text-center text-sm whitespace-nowrap ${
                            isWeekend 
                              ? 'bg-gray-50 dark:bg-gray-800/50' 
                              : ''
                          } ${
                            hasHours 
                              ? 'text-gray-900 dark:text-white font-medium' 
                              : 'text-gray-400 dark:text-gray-600'
                          }`}
                        >
                          {dayEntry.formatted}
                        </td>
                      );
                    })}
                    
                    {/* User total */}
                    <td className="px-4 py-3 text-center text-sm font-semibold whitespace-nowrap bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                      {user.total_formatted}
                    </td>
                  </tr>
                ))}
                
                {/* Daily totals row (footer) */}
                <tr className="bg-gray-100 dark:bg-gray-800 font-semibold">
                  <td className="px-4 py-3 whitespace-nowrap sticky left-0 bg-gray-100 dark:bg-gray-800 z-10 text-gray-700 dark:text-gray-300">
                    Daily Total
                  </td>
                  
                  {timesheetData.daily_totals.map((dayTotal) => {
                    const isWeekend = new Date(dayTotal.date + 'T00:00:00').getDay() % 6 === 0;
                    return (
                      <td 
                        key={dayTotal.date} 
                        className={`px-3 py-3 text-center text-sm whitespace-nowrap ${
                          isWeekend 
                            ? 'bg-gray-200 dark:bg-gray-700' 
                            : ''
                        } text-gray-700 dark:text-gray-300`}
                      >
                        {dayTotal.formatted}
                      </td>
                    );
                  })}
                  
                  {/* Grand total */}
                  <td className="px-4 py-3 text-center text-sm whitespace-nowrap bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200 font-bold">
                    {timesheetData.grand_total_formatted}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Summary Stats */}
      {timesheetData && timesheetData.users.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <div className="text-center p-2">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Team Members</p>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {timesheetData.users.length}
              </p>
            </div>
          </Card>
          <Card>
            <div className="text-center p-2">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Days in Period</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                {timesheetData.dates.length}
              </p>
            </div>
          </Card>
          <Card>
            <div className="text-center p-2">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Total Team Hours</p>
              <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                {timesheetData.grand_total_formatted}
              </p>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

export default TeamTimesheetReport;
