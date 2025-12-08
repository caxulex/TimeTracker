// ============================================
// TIME TRACKER - ADMIN ALERTS PANEL
// TASK-022: Admin alerts for worker activity
// ============================================
import { useQuery } from '@tanstack/react-query';
import { Card, CardHeader } from './common';
import { adminApi } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { formatDistanceToNow } from '../utils/helpers';

interface Alert {
  type: 'long_timer' | 'no_activity' | 'active_timer';
  severity: 'warning' | 'info' | 'success';
  message: string;
  user_name: string;
  entry_id?: number;
  project_name?: string;
  start_time?: string;
  hours?: number;
  last_activity?: string;
  days_inactive?: number;
}

interface AlertsResponse {
  alerts: Alert[];
  summary: {
    total_alerts: number;
    running_timers: number;
    long_timers: number;
    inactive_users: number;
  };
}

interface AdminAlertsPanelProps {
  className?: string;
}

export function AdminAlertsPanel({ className = '' }: AdminAlertsPanelProps) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'super_admin';

  const { data, isLoading, refetch } = useQuery<AlertsResponse>({
    queryKey: ['admin-alerts'],
    queryFn: adminApi.getActivityAlerts,
    enabled: isAdmin,
    refetchInterval: 60000,
  });

  if (!isAdmin) return null;

  const alerts = data?.alerts || [];
  const summary = data?.summary;

  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case 'warning': return 'bg-amber-50 border-amber-200 text-amber-800';
      case 'success': return 'bg-green-50 border-green-200 text-green-800';
      default: return 'bg-blue-50 border-blue-200 text-blue-800';
    }
  };

  const getSeverityIcon = (severity: string) => {
    const iconClass = severity === 'warning' ? 'text-amber-500' : severity === 'success' ? 'text-green-500' : 'text-blue-500';
    const path = severity === 'warning' 
      ? 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z'
      : severity === 'success'
      ? 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'
      : 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
    
    return (
      <svg className={'w-5 h-5 ' + iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={path} />
      </svg>
    );
  };

  return (
    <Card className={className}>
      <CardHeader 
        title="Activity Alerts" 
        subtitle="Real-time team notifications"
        action={
          <button onClick={() => refetch()} className="p-1 text-gray-400 hover:text-gray-600 rounded" title="Refresh">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        }
      />
      {summary && (
        <div className="flex flex-wrap gap-2 mb-4 px-4">
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            <span className="w-2 h-2 bg-green-400 rounded-full mr-1.5 animate-pulse"></span>
            {summary.running_timers} Active
          </span>
          {summary.long_timers > 0 && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
              {summary.long_timers} Long Sessions
            </span>
          )}
        </div>
      )}
      <div className="space-y-2 px-4 pb-4 max-h-96 overflow-y-auto">
        {isLoading ? (
          <div className="text-center py-8 text-gray-500">Loading alerts...</div>
        ) : alerts.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p className="text-sm">All clear! No alerts at this time.</p>
          </div>
        ) : (
          alerts.map((alert, index) => (
            <div key={index} className={'flex items-start gap-3 p-3 rounded-lg border ' + getSeverityStyles(alert.severity)}>
              {getSeverityIcon(alert.severity)}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{alert.message}</p>
                {alert.project_name && <p className="text-xs opacity-75 mt-0.5">Project: {alert.project_name}</p>}
                {alert.start_time && <p className="text-xs opacity-75 mt-0.5">Started {formatDistanceToNow(new Date(alert.start_time))}</p>}
              </div>
              {alert.hours !== undefined && <span className="flex-shrink-0 text-xs font-mono">{alert.hours.toFixed(1)}h</span>}
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
