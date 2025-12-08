// ============================================
// TIME TRACKER - ADMIN TIME ENTRIES VIEWER
// TASK-009: Admin can view all users' time entries
// ============================================
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardHeader, LoadingOverlay, Button } from '../components/common';
import { reportsApi, teamsApi, usersApi } from '../api/client';
import { formatDuration, formatDate, toISODateString, getStartOfWeek } from '../utils/helpers';
import { useAuth } from '../hooks/useAuth';
import type { User, Team } from '../types';

interface TimeEntryWithUser {
  id: number;
  user_id: number;
  user_name: string;
  project_id: number;
  project_name: string;
  task_id?: number;
  task_name?: string;
  description?: string;
  start_time: string;
  end_time?: string;
  duration_seconds: number;
}

interface AdminTimeEntriesResponse {
  entries: TimeEntryWithUser[];
  total: number;
  total_seconds: number;
}

type DatePreset = 'today' | 'yesterday' | 'this-week' | 'last-week' | 'this-month' | 'custom';

export function AdminTimeEntriesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'super_admin';

  const [datePreset, setDatePreset] = useState<DatePreset>('today');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  const [selectedUser, setSelectedUser] = useState<number | ''>('');
  const [selectedTeam, setSelectedTeam] = useState<number | ''>('');

  const { data: usersData } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersApi.getAll(),
    enabled: isAdmin,
  });

  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsApi.getAll(),
    enabled: isAdmin,
  });

  const users = usersData?.items || [];
  const teams = teamsData?.items || [];

  const getDateRange = () => {
    const today = new Date();
    let startDate: Date;
    let endDate: Date = today;

    switch (datePreset) {
      case 'today':
        startDate = today;
        break;
      case 'yesterday':
        startDate = new Date(today.getTime() - 24 * 60 * 60 * 1000);
        endDate = startDate;
        break;
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
      case 'custom':
        return { startDate: customStartDate, endDate: customEndDate };
      default:
        startDate = today;
    }
    return { startDate: toISODateString(startDate), endDate: toISODateString(endDate) };
  };

  const { startDate, endDate } = getDateRange();

  const { data: entriesData, isLoading } = useQuery<AdminTimeEntriesResponse>({
    queryKey: ['admin-time-entries', startDate, endDate, selectedUser, selectedTeam],
    queryFn: () => reportsApi.getAdminTimeEntries({
      start_date: startDate,
      end_date: endDate,
      user_id: selectedUser || undefined,
      team_id: selectedTeam || undefined,
    }),
    enabled: isAdmin && !!startDate && !!endDate,
  });

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <h3 className="mt-2 text-sm font-medium text-gray-900">Access Denied</h3>
          <p className="mt-1 text-sm text-gray-500">Admin privileges required.</p>
        </div>
      </div>
    );
  }

  const entries = entriesData?.entries || [];
  const totalSeconds = entriesData?.total_seconds || 0;

  const presets = [
    { value: 'today', label: 'Today' },
    { value: 'yesterday', label: 'Yesterday' },
    { value: 'this-week', label: 'This Week' },
    { value: 'last-week', label: 'Last Week' },
    { value: 'this-month', label: 'This Month' },
    { value: 'custom', label: 'Custom' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">All Time Entries</h1>
          <p className="text-gray-500">View and manage all users time entries</p>
        </div>
        <Button variant="secondary">Export</Button>
      </div>

      <Card padding="sm">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <button
                key={preset.value}
                onClick={() => setDatePreset(preset.value as DatePreset)}
                className={datePreset === preset.value
                  ? 'px-3 py-1.5 text-sm font-medium rounded-lg bg-blue-600 text-white'
                  : 'px-3 py-1.5 text-sm font-medium rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200'
                }
              >
                {preset.label}
              </button>
            ))}
          </div>
          {datePreset === 'custom' && (
            <div className="flex items-center gap-2">
              <input type="date" value={customStartDate} onChange={(e) => setCustomStartDate(e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm" />
              <span className="text-gray-500">to</span>
              <input type="date" value={customEndDate} onChange={(e) => setCustomEndDate(e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm" />
            </div>
          )}
          <select value={selectedUser} onChange={(e) => setSelectedUser(e.target.value ? Number(e.target.value) : '')}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm">
            <option value="">All Users</option>
            {users.map((u: User) => (<option key={u.id} value={u.id}>{u.name}</option>))}
          </select>
          <select value={selectedTeam} onChange={(e) => setSelectedTeam(e.target.value ? Number(e.target.value) : '')}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm">
            <option value="">All Teams</option>
            {teams.map((t: Team) => (<option key={t.id} value={t.id}>{t.name}</option>))}
          </select>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card><div className="text-center"><p className="text-sm text-gray-500">Total Entries</p><p className="text-3xl font-bold text-gray-900">{entries.length}</p></div></Card>
        <Card><div className="text-center"><p className="text-sm text-gray-500">Total Time</p><p className="text-3xl font-bold text-gray-900">{formatDuration(totalSeconds)}</p></div></Card>
        <Card><div className="text-center"><p className="text-sm text-gray-500">Unique Users</p><p className="text-3xl font-bold text-gray-900">{new Set(entries.map((e: TimeEntryWithUser) => e.user_id)).size}</p></div></Card>
      </div>

      {isLoading ? (
        <LoadingOverlay message="Loading time entries..." />
      ) : (
        <Card>
          <CardHeader title="Time Entries" subtitle={entries.length + ' entries found'} />
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">User</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Date</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Project</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Task</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Description</th>
                  <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Duration</th>
                </tr>
              </thead>
              <tbody>
                {entries.length > 0 ? entries.map((entry: TimeEntryWithUser) => (
                  <tr key={entry.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4"><span className="font-medium text-gray-900">{entry.user_name}</span></td>
                    <td className="py-3 px-4 text-gray-600">{formatDate(entry.start_time)}</td>
                    <td className="py-3 px-4 text-gray-600">{entry.project_name}</td>
                    <td className="py-3 px-4 text-gray-500">{entry.task_name || '-'}</td>
                    <td className="py-3 px-4 text-gray-500 max-w-xs truncate">{entry.description || '-'}</td>
                    <td className="text-right py-3 px-4 font-mono text-gray-900">{formatDuration(entry.duration_seconds)}</td>
                  </tr>
                )) : (
                  <tr><td colSpan={6} className="py-8 text-center text-gray-500">No time entries found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
