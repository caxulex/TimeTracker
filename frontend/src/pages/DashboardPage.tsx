// ============================================
// TIME TRACKER - DASHBOARD PAGE
// ============================================

import { useQuery } from '@tanstack/react-query';
import { useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, LoadingOverlay } from '../components/common';
import { TimerWidget } from '../components/time/TimerWidget';
import { ActiveTimers } from '../components/ActiveTimers';
import { AdminAlertsPanel } from '../components/AdminAlertsPanel';
import { AnomalyAlertPanel } from '../components/ai/AnomalyAlertPanel';
import WeeklySummaryPanel from '../components/ai/WeeklySummaryPanel';
import UserInsightsPanel from '../components/ai/UserInsightsPanel';
import { useFeatureEnabled } from '../hooks/useAIFeatures';
import { reportsApi } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { formatDuration } from '../utils/helpers';
import type { DashboardStats, WeeklySummary } from '../types';
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
} from 'recharts';

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];

interface AdminDashboardStats {
  total_today_seconds: number;
  total_today_hours: number;
  total_week_seconds: number;
  total_week_hours: number;
  total_month_seconds: number;
  total_month_hours: number;
  active_users_today: number;
  active_projects: number;
  running_timers: number;
  by_user: Array<{
    user_id: number;
    user_name: string;
    total_seconds: number;
    total_hours: number;
    entry_count: number;
  }>;
}

export function DashboardPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  // Get WebSocket context - connection is managed by WebSocketProvider
  const { isConnected } = useWebSocketContext();

  // AI Feature flags
  const { data: anomalyEnabled } = useFeatureEnabled('ai_anomaly_alerts');
  const { data: weeklySummaryEnabled } = useFeatureEnabled('ai_report_summaries');
  const { data: userInsightsEnabled } = useFeatureEnabled('ai_report_summaries');

  // User's personal dashboard
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboard'],
    queryFn: reportsApi.getDashboard,
  });

  // Admin dashboard (all users' data)
  const { data: adminStats, isLoading: adminLoading } = useQuery<AdminDashboardStats>({
    queryKey: ['admin-dashboard'],
    queryFn: reportsApi.getAdminDashboard,
    enabled: isAdmin,
  });

  const { data: weekly, isLoading: weeklyLoading } = useQuery<WeeklySummary>({
    queryKey: ['weekly-summary'],
    queryFn: () => reportsApi.getWeekly(),
  });

  const { data: projectData } = useQuery({
    queryKey: ['project-report-dashboard'],
    queryFn: () => reportsApi.getByProject(),
  });

  if (statsLoading || weeklyLoading || (isAdmin && adminLoading)) {
    return <LoadingOverlay message="Loading dashboard..." />;
  }

  const dailyChartData = weekly?.daily_breakdown?.map((day) => ({
    name: new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' }),
    hours: Math.round((day.total_seconds / 3600) * 10) / 10,
  })) || [];

  const totalProjectSeconds = projectData?.reduce((sum: number, p: any) => sum + p.total_seconds, 0) || 0;
  const projectChartData = projectData?.map((project: any) => ({
    name: project.project_name,
    value: project.total_seconds,
    percentage: totalProjectSeconds > 0 ? Math.round((project.total_seconds / totalProjectSeconds) * 100) : 0,
  })) || [];

  // Check if there's any real activity
  const hasTeamActivity = adminStats && (adminStats.total_today_seconds > 0 || adminStats.by_user.length > 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500">
          {isAdmin ? 'Team overview and your personal time tracking' : 'Track your time and see your progress'}
        </p>
      </div>

      {isAdmin && adminStats && (
        <div className="bg-gradient-to-r from-indigo-500 to-purple-600 rounded-xl p-6 text-white">
          <h2 className="text-lg font-semibold mb-4">Team Overview (All Users)</h2>
          {hasTeamActivity ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white/20 rounded-lg p-3">
                  <p className="text-white/80 text-sm">Team Today</p>
                  <p className="text-2xl font-bold">{formatDuration(adminStats.total_today_seconds)}</p>
                </div>
                <div className="bg-white/20 rounded-lg p-3">
                  <p className="text-white/80 text-sm">Team This Week</p>
                  <p className="text-2xl font-bold">{formatDuration(adminStats.total_week_seconds)}</p>
                </div>
                <div className="bg-white/20 rounded-lg p-3">
                  <p className="text-white/80 text-sm">Active Users Today</p>
                  <p className="text-2xl font-bold">{adminStats.active_users_today}</p>
                </div>
                <div className="bg-white/20 rounded-lg p-3">
                  <p className="text-white/80 text-sm">Running Timers</p>
                  <p className="text-2xl font-bold">{adminStats.running_timers}</p>
                </div>
              </div>
              {adminStats.by_user.length > 0 && (
                <div className="mt-4">
                  <h3 className="text-sm font-medium text-white/80 mb-2">Today's Activity by User</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {adminStats.by_user.map((userStat) => (
                      <div key={userStat.user_id} className="bg-white/10 rounded-lg p-2 flex justify-between items-center">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                          <span className="font-medium">{userStat.user_name}</span>
                        </div>
                        <span className="text-white/90">{formatDuration(userStat.total_seconds)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="bg-white/10 rounded-lg p-6 text-center">
              <svg className="w-12 h-12 mx-auto mb-3 text-white/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-white/80 text-lg">No time tracked yet today</p>
              <p className="text-white/60 text-sm mt-1">Team members haven't started tracking time</p>
            </div>
          )}
        </div>
      )}

      <TimerWidget />

      <div>
        <h2 className="text-lg font-semibold text-gray-700 mb-3">
          {isAdmin ? 'Your Personal Stats' : 'Your Stats'}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="Today" value={formatDuration(stats?.today_seconds || 0)}
            icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
            color="blue" />
          <StatCard title="This Week" value={formatDuration(stats?.week_seconds || 0)}
            icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>}
            color="green" />
          <StatCard title="This Month" value={formatDuration(stats?.month_seconds || 0)}
            icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>}
            color="amber" />
          <StatCard title="Active Projects" value={String(stats?.active_projects || 0)}
            icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" /></svg>}
            color="purple" />
        </div>
      </div>

      {/* Real-time monitoring section for admins */}
      {isAdmin ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ActiveTimers />
          <AdminAlertsPanel />
        </div>
      ) : (
        <ActiveTimers />
      )}

      {/* AI Features Section */}
      {isAdmin && anomalyEnabled && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <span>🤖</span> AI Anomaly Detection
          </h2>
          <AnomalyAlertPanel 
            isAdmin={true}
            periodDays={7}
            maxItems={5}
          />
        </div>
      )}

      {/* Weekly AI Summary for all users */}
      {weeklySummaryEnabled && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <span>📊</span> AI Weekly Summary
          </h2>
          <WeeklySummaryPanel collapsible={true} defaultExpanded={false} />
        </div>
      )}

      {/* User AI Insights */}
      {userInsightsEnabled && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <span>🧠</span> AI Productivity Insights
          </h2>
          <UserInsightsPanel periodDays={30} showHeader={false} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader title="Weekly Activity" subtitle="Hours tracked per day" />
          <div className="h-64">
            {dailyChartData.some(d => d.hours > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dailyChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis dataKey="name" stroke="#6B7280" fontSize={12} />
                  <YAxis stroke="#6B7280" fontSize={12} />
                  <Tooltip contentStyle={{ backgroundColor: 'white', border: '1px solid #E5E7EB', borderRadius: '8px' }}
                    formatter={(value: number) => [value + 'h', 'Hours']} />
                  <Bar dataKey="hours" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-500">
                <svg className="w-12 h-12 mb-2 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <p>No time tracked this week</p>
                <p className="text-sm text-gray-400">Start tracking to see your activity</p>
              </div>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Time by Project" subtitle="This week breakdown" />
          <div className="h-64">
            {projectChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={projectChartData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value"
                    label={({ name, percentage }) => name + ' (' + percentage + '%)'}>
                    {projectChartData.map((_: any, index: number) => (
                      <Cell key={'cell-' + index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => [formatDuration(value), 'Time']} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-500">
                <svg className="w-12 h-12 mb-2 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                </svg>
                <p>No time tracked this week</p>
                <p className="text-sm text-gray-400">Track time on projects to see distribution</p>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string;
  icon: React.ReactNode;
  color: 'blue' | 'green' | 'amber' | 'purple';
}

function StatCard({ title, value, icon, color }: StatCardProps) {
  const colors = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    amber: 'bg-amber-50 text-amber-600',
    purple: 'bg-purple-50 text-purple-600',
  };
  return (
    <Card>
      <div className="flex items-center space-x-4">
        <div className={'p-3 rounded-lg ' + colors[color]}>{icon}</div>
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
        </div>
      </div>
    </Card>
  );
}
