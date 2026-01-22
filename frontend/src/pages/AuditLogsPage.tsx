// ============================================
// TIME TRACKER - AUDIT LOGS PAGE
// Admin page for viewing security audit logs
// ============================================
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardHeader, LoadingOverlay, Button } from '../components/common';
import { useAuthStore } from '../stores/authStore';
import { isAdminUser } from '../utils/helpers';
import api from '../api/client';

interface AuditLogEntry {
  id: string;
  timestamp: string;
  event_type: string;
  severity: string;
  success: boolean;
  user_id: number | null;
  user_email: string | null;
  ip_address: string | null;
  user_agent: string | null;
  resource_type: string | null;
  resource_id: string | null;
  action: string | null;
  details: Record<string, unknown> | null;
}

interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
}

interface AuditLogSummary {
  total_events: number;
  login_success: number;
  login_failed: number;
  user_events: number;
  admin_actions: number;
  security_events: number;
  time_range_hours: number;
}

interface EventType {
  value: string;
  name: string;
}

const severityColors: Record<string, string> = {
  debug: 'bg-gray-100 text-gray-800',
  info: 'bg-blue-100 text-blue-800',
  warning: 'bg-yellow-100 text-yellow-800',
  error: 'bg-red-100 text-red-800',
  critical: 'bg-red-200 text-red-900',
};

const eventTypeIcons: Record<string, string> = {
  'auth.login.success': '✅',
  'auth.login.failed': '❌',
  'auth.logout': '🚪',
  'auth.token.refresh': '🔄',
  'auth.password.change': '🔑',
  'user.created': '👤',
  'user.updated': '✏️',
  'user.deleted': '🗑️',
  'user.deactivated': '⏸️',
  'user.activated': '▶️',
  'security.account.locked': '🔒',
  'security.rate_limited': '🚫',
  'data.payroll.accessed': '💰',
  'data.report.generated': '📊',
  'admin.action': '⚙️',
  'api.permission.denied': '🚷',
};

export function AuditLogsPage() {
  const { user } = useAuthStore();
  const [selectedEventType, setSelectedEventType] = useState<string>('');
  const [limit, setLimit] = useState(100);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const isAdmin = isAdminUser(user);

  // Fetch summary
  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['audit-summary'],
    queryFn: async () => {
      const response = await api.get('/api/admin/audit-logs/summary', { params: { hours: 24 } });
      return response.data as AuditLogSummary;
    },
    enabled: isAdmin,
    refetchInterval: 60000, // Refresh every minute
  });

  // Fetch event types
  const { data: eventTypes } = useQuery({
    queryKey: ['audit-event-types'],
    queryFn: async () => {
      const response = await api.get('/api/admin/audit-logs/event-types');
      return response.data.event_types as EventType[];
    },
    enabled: isAdmin,
  });

  // Fetch logs
  const { data: logsData, isLoading: loadingLogs, refetch } = useQuery({
    queryKey: ['audit-logs', selectedEventType, limit],
    queryFn: async () => {
      const params: Record<string, unknown> = { limit };
      if (selectedEventType) params.event_type = selectedEventType;
      const response = await api.get('/api/admin/audit-logs', { params });
      return response.data as AuditLogListResponse;
    },
    enabled: isAdmin,
  });

  const toggleRow = (id: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const formatEventType = (eventType: string) => {
    return eventType.replace(/\./g, ' > ').replace(/_/g, ' ');
  };

  const exportToCsv = () => {
    if (!logsData?.items.length) return;
    
    const headers = ['Timestamp', 'Event Type', 'Severity', 'Success', 'User', 'IP Address', 'Action', 'Details'];
    const rows = logsData.items.map(log => [
      log.timestamp,
      log.event_type,
      log.severity,
      log.success ? 'Yes' : 'No',
      log.user_email || log.user_id || '',
      log.ip_address || '',
      log.action || '',
      log.details ? JSON.stringify(log.details) : '',
    ]);
    
    const csv = [headers.join(','), ...rows.map(row => row.map(cell => `"${cell}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-logs-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card>
          <div className="text-center p-8">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Access Denied</h2>
            <p className="text-gray-500">Admin privileges required.</p>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
          <p className="text-gray-500">Security event monitoring and activity tracking</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => refetch()} variant="secondary">
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </Button>
          <Button onClick={exportToCsv} disabled={!logsData?.items.length}>
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export CSV
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      {loadingSummary ? (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          {[...Array(6)].map((_, i) => (
            <Card key={i}>
              <div className="p-4 animate-pulse">
                <div className="h-8 bg-gray-200 rounded mb-2" />
                <div className="h-4 bg-gray-100 rounded w-3/4" />
              </div>
            </Card>
          ))}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          <Card>
            <div className="p-4 text-center">
              <div className="text-2xl font-bold text-gray-900">{summary.total_events}</div>
              <div className="text-sm text-gray-500">Total Events (24h)</div>
            </div>
          </Card>
          <Card>
            <div className="p-4 text-center">
              <div className="text-2xl font-bold text-green-600">{summary.login_success}</div>
              <div className="text-sm text-gray-500">Login Success</div>
            </div>
          </Card>
          <Card>
            <div className="p-4 text-center">
              <div className="text-2xl font-bold text-red-600">{summary.login_failed}</div>
              <div className="text-sm text-gray-500">Login Failed</div>
            </div>
          </Card>
          <Card>
            <div className="p-4 text-center">
              <div className="text-2xl font-bold text-blue-600">{summary.user_events}</div>
              <div className="text-sm text-gray-500">User Events</div>
            </div>
          </Card>
          <Card>
            <div className="p-4 text-center">
              <div className="text-2xl font-bold text-purple-600">{summary.admin_actions}</div>
              <div className="text-sm text-gray-500">Admin Actions</div>
            </div>
          </Card>
          <Card>
            <div className="p-4 text-center">
              <div className="text-2xl font-bold text-amber-600">{summary.security_events}</div>
              <div className="text-sm text-gray-500">Security Events</div>
            </div>
          </Card>
        </div>
      ) : null}

      {/* Filters */}
      <Card>
        <div className="p-4 flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Event Type:</label>
            <select
              value={selectedEventType}
              onChange={(e) => setSelectedEventType(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All Events</option>
              {eventTypes?.map((et) => (
                <option key={et.value} value={et.value}>
                  {eventTypeIcons[et.value] || '📋'} {formatEventType(et.value)}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Show:</label>
            <select
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value))}
              className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value={50}>50 entries</option>
              <option value={100}>100 entries</option>
              <option value={200}>200 entries</option>
              <option value={500}>500 entries</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Logs Table */}
      <Card>
        <CardHeader title={`Audit Log Entries (${logsData?.total || 0})`} />
        {loadingLogs ? (
          <LoadingOverlay message="Loading audit logs..." />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Timestamp
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Event
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    User
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    IP Address
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {logsData?.items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-gray-500">
                      <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                      </svg>
                      <p>No audit logs found</p>
                    </td>
                  </tr>
                ) : (
                  logsData?.items.map((log) => (
                    <>
                      <tr
                        key={log.id}
                        className="hover:bg-gray-50 cursor-pointer"
                        onClick={() => toggleRow(log.id)}
                      >
                        <td className="px-4 py-3 text-sm text-gray-900 whitespace-nowrap">
                          {formatTimestamp(log.timestamp)}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <div className="flex items-center gap-2">
                            <span className="text-lg">{eventTypeIcons[log.event_type] || '📋'}</span>
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${severityColors[log.severity] || severityColors.info}`}>
                              {formatEventType(log.event_type)}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-900">
                          {log.user_email || (log.user_id ? `User #${log.user_id}` : '—')}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500 font-mono">
                          {log.ip_address || '—'}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {log.success ? (
                            <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">
                              ✓ Success
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-800">
                              ✗ Failed
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <button className="text-blue-600 hover:text-blue-800">
                            {expandedRows.has(log.id) ? '▼' : '▶'} View
                          </button>
                        </td>
                      </tr>
                      {expandedRows.has(log.id) && (
                        <tr className="bg-gray-50">
                          <td colSpan={6} className="px-4 py-4">
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                              <div>
                                <span className="font-medium text-gray-700">Log ID:</span>
                                <p className="text-gray-600 font-mono text-xs break-all">{log.id}</p>
                              </div>
                              {log.action && (
                                <div>
                                  <span className="font-medium text-gray-700">Action:</span>
                                  <p className="text-gray-600">{log.action}</p>
                                </div>
                              )}
                              {log.resource_type && (
                                <div>
                                  <span className="font-medium text-gray-700">Resource:</span>
                                  <p className="text-gray-600">{log.resource_type} #{log.resource_id}</p>
                                </div>
                              )}
                              {log.user_agent && (
                                <div className="col-span-2 md:col-span-3">
                                  <span className="font-medium text-gray-700">User Agent:</span>
                                  <p className="text-gray-600 text-xs break-all">{log.user_agent}</p>
                                </div>
                              )}
                              {log.details && Object.keys(log.details).length > 0 && (
                                <div className="col-span-2 md:col-span-3">
                                  <span className="font-medium text-gray-700">Details:</span>
                                  <pre className="mt-1 p-2 bg-gray-100 rounded text-xs overflow-x-auto">
                                    {JSON.stringify(log.details, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
