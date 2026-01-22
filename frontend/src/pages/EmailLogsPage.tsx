// ============================================
// TIME TRACKER - EMAIL LOGS PAGE
// ============================================
// Admin page for monitoring email delivery status
// ============================================

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardHeader, LoadingOverlay, Button } from '../components/common';
import { useAuthStore } from '../stores/authStore';
import { isAdminUser } from '../utils/helpers';
import { apiRequest } from '../api/client';

interface EmailLog {
  id: number;
  to_email: string;
  from_email: string;
  subject: string;
  email_type: string;
  status: string;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  sent_at: string | null;
  delivered_at: string | null;
  metadata: Record<string, unknown> | null;
}

interface EmailLogSummary {
  total_emails: number;
  sent_count: number;
  delivered_count: number;
  failed_count: number;
  pending_count: number;
  bounced_count: number;
  success_rate: number;
}

interface PaginatedEmailLogs {
  items: EmailLog[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// API functions
const emailLogsApi = {
  getSummary: async (days: number = 7): Promise<EmailLogSummary> => {
    const response = await apiRequest<EmailLogSummary>(`/admin/email-logs/summary?days=${days}`);
    return response;
  },
  getList: async (
    page: number = 1,
    pageSize: number = 20,
    status?: string,
    emailType?: string,
    toEmail?: string
  ): Promise<PaginatedEmailLogs> => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('page_size', pageSize.toString());
    if (status) params.append('status', status);
    if (emailType) params.append('email_type', emailType);
    if (toEmail) params.append('to_email', toEmail);
    
    const response = await apiRequest<PaginatedEmailLogs>(`/admin/email-logs?${params.toString()}`);
    return response;
  },
  getTypes: async (): Promise<{ email_types: string[] }> => {
    const response = await apiRequest<{ email_types: string[] }>('/admin/email-logs/types');
    return response;
  },
};

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  sent: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  delivered: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  failed: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  bounced: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
};

export function EmailLogsPage() {
  const { user: currentUser } = useAuthStore();
  const isAdmin = isAdminUser(currentUser);
  
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [emailTypeFilter, setEmailTypeFilter] = useState<string>('');
  const [searchEmail, setSearchEmail] = useState<string>('');
  const [summaryDays, setSummaryDays] = useState(7);

  // Fetch summary
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['email-logs-summary', summaryDays],
    queryFn: () => emailLogsApi.getSummary(summaryDays),
    enabled: isAdmin,
  });

  // Fetch email types for filter
  const { data: typesData } = useQuery({
    queryKey: ['email-log-types'],
    queryFn: () => emailLogsApi.getTypes(),
    enabled: isAdmin,
  });

  // Fetch logs
  const { data: logsData, isLoading: logsLoading } = useQuery({
    queryKey: ['email-logs', page, statusFilter, emailTypeFilter, searchEmail],
    queryFn: () => emailLogsApi.getList(page, 20, statusFilter || undefined, emailTypeFilter || undefined, searchEmail || undefined),
    enabled: isAdmin,
  });

  if (!isAdmin) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Card className="bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800">
          <div className="p-6 text-center">
            <p className="text-red-600 dark:text-red-400">
              You don't have permission to view this page.
            </p>
          </div>
        </Card>
      </div>
    );
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Email Delivery Dashboard
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Monitor email delivery status and performance
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Emails</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {summaryLoading ? '...' : summary?.total_emails ?? 0}
              </p>
            </div>
            <div className="text-3xl">📧</div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Delivered</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                {summaryLoading ? '...' : (summary?.sent_count ?? 0) + (summary?.delivered_count ?? 0)}
              </p>
            </div>
            <div className="text-3xl">✅</div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Failed</p>
              <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                {summaryLoading ? '...' : (summary?.failed_count ?? 0) + (summary?.bounced_count ?? 0)}
              </p>
            </div>
            <div className="text-3xl">❌</div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Success Rate</p>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {summaryLoading ? '...' : `${summary?.success_rate?.toFixed(1) ?? 100}%`}
              </p>
            </div>
            <div className="text-3xl">📊</div>
          </div>
        </Card>
      </div>

      {/* Summary Period Selector */}
      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm text-gray-500 dark:text-gray-400">Summary period:</span>
        <select
          value={summaryDays}
          onChange={(e) => setSummaryDays(Number(e.target.value))}
          className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value={1}>Last 24 hours</option>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardHeader
          title="Email Logs"
          subtitle="Filter and search email delivery records"
        />
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Status
              </label>
              <select
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                <option value="">All statuses</option>
                <option value="pending">Pending</option>
                <option value="sent">Sent</option>
                <option value="delivered">Delivered</option>
                <option value="failed">Failed</option>
                <option value="bounced">Bounced</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Email Type
              </label>
              <select
                value={emailTypeFilter}
                onChange={(e) => { setEmailTypeFilter(e.target.value); setPage(1); }}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                <option value="">All types</option>
                {typesData?.email_types.map((type) => (
                  <option key={type} value={type}>
                    {type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Search by Email
              </label>
              <input
                type="text"
                value={searchEmail}
                onChange={(e) => { setSearchEmail(e.target.value); setPage(1); }}
                placeholder="Enter email address..."
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            <div className="flex items-end">
              <Button
                variant="secondary"
                onClick={() => {
                  setStatusFilter('');
                  setEmailTypeFilter('');
                  setSearchEmail('');
                  setPage(1);
                }}
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Email Logs Table */}
      <Card>
        <div className="relative">
          <LoadingOverlay isLoading={logsLoading} />
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Recipient
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Subject
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Sent At
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Error
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                {logsData?.items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                      No email logs found
                    </td>
                  </tr>
                ) : (
                  logsData?.items.map((log) => (
                    <tr key={log.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="px-4 py-3 text-sm text-gray-900 dark:text-white">
                        {log.to_email}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 max-w-xs truncate">
                        {log.subject}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300">
                          {log.email_type.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColors[log.status] || 'bg-gray-100 text-gray-800'}`}>
                          {log.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                        {formatDate(log.sent_at || log.created_at)}
                      </td>
                      <td className="px-4 py-3 text-sm text-red-500 dark:text-red-400 max-w-xs truncate">
                        {log.error_message || '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {logsData && logsData.total_pages > 1 && (
            <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <div className="text-sm text-gray-500 dark:text-gray-400">
                Showing {((page - 1) * 20) + 1} to {Math.min(page * 20, logsData.total)} of {logsData.total} emails
              </div>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <span className="px-3 py-1 text-sm text-gray-700 dark:text-gray-300">
                  Page {page} of {logsData.total_pages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage(p => Math.min(logsData.total_pages, p + 1))}
                  disabled={page >= logsData.total_pages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
