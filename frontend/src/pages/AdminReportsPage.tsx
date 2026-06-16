import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { UserSelect } from '../components/users/UserSelect';
import TeamAnalyticsPanel from '../components/ai/TeamAnalyticsPanel';
// Use lazy-loaded AI components to reduce initial bundle size (Task 6.1)
import {
  LazyPayrollForecastPanel as PayrollForecastPanel,
  LazyOvertimeRiskPanel as OvertimeRiskPanel,
  LazyProjectBudgetPanel as ProjectBudgetPanel,
  LazyCashFlowChart as CashFlowChart,
  LazyBurnoutRiskPanel as BurnoutRiskPanel,
} from '../components/ai/lazy';
import { useFeatureEnabled } from '../hooks/useAIFeatures';
import {
  ChartBarIcon,
  UsersIcon,
  ClockIcon,
  TrophyIcon,
  ArrowTrendingUpIcon,
  UserGroupIcon,
  ChartPieIcon,
  UserIcon,
  XMarkIcon,
} from '../components/Icons';
import { getAvgHoursSubtitle, getAvgHoursTooltip } from '../utils/working_days';
import { BarChart, Bar, PieChart, Pie, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { isAdminUser } from '../utils/helpers';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

interface AdminDashboard {
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

interface TeamAnalytics {
  team_id: number;
  team_name: string;
  member_count: number;
  total_today_seconds: number;
  total_today_hours: number;
  total_week_seconds: number;
  total_week_hours: number;
  total_month_seconds: number;
  total_month_hours: number;
  active_members_today: number;
  running_timers: number;
  top_performers: Array<{
    user_id: number;
    user_name: string;
    total_seconds: number;
    total_hours: number;
    entry_count: number;
  }>;
}

interface UserSummary {
  user_id: number;
  user_name: string;
  user_email?: string;
  total_seconds: number;
  total_hours: number;
  entry_count: number;
}

interface SelectedUserDetail {
  user_id: number;
  user_name: string;
  user_email: string;
  role: string;
  teams: string[];
  today_seconds: number;
  today_hours: number;
  week_seconds: number;
  week_hours: number;
  month_seconds: number;
  month_hours: number;
  total_entries: number;
  active_days_this_month: number;
  avg_hours_per_day: number;
  avg_denominator_days?: number;
  avg_denominator_type?: 'working_days_completed' | 'working_days_all' | 'days_with_entries' | 'calendar_days';
  avg_includes_today?: boolean;
  avg_working_days_source?: 'user' | 'company' | 'default';
  avg_working_days_used?: number[];
  current_timer_running: boolean;
  projects: Array<{
    project_id: number;
    project_name: string;
    total_seconds: number;
    total_hours: number;
    entry_count: number;
  }>;
  last_activity: string | null;
}

export default function AdminReportsPage() {
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'overview' | 'teams' | 'individuals'>('overview');
  const [userPeriod, setUserPeriod] = useState<'today' | 'week' | 'month'>('week');
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedTeamForAnalytics, setSelectedTeamForAnalytics] = useState<TeamAnalytics | null>(null);
  // Task 6.2: Pagination state
  const [usersPage, setUsersPage] = useState(1);
  const usersPageSize = 50;

  // AI Feature flags
  const { data: payrollForecastEnabled } = useFeatureEnabled('ai_payroll_forecast');
  const { data: overtimeRiskEnabled } = useFeatureEnabled('ai_payroll_forecast');
  const { data: projectBudgetEnabled } = useFeatureEnabled('ai_payroll_forecast');
  const { data: cashFlowEnabled } = useFeatureEnabled('ai_payroll_forecast');
  const { data: burnoutRiskEnabled } = useFeatureEnabled('ai_anomaly_alerts');

  // Fetch admin dashboard data
  const { data: dashboardData, isLoading: isDashboardLoading, isError: isDashboardError } = useQuery<AdminDashboard>({
    queryKey: ['admin-dashboard'],
    queryFn: async () => {
      const response = await fetch('/api/reports/admin/dashboard', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });
      if (!response.ok) throw new Error('Failed to fetch admin dashboard');
      return response.json();
    },
    refetchInterval: 30000, // Refresh every 30 seconds
    enabled: isAdminUser(user), // Only fetch if admin
  });

  // Fetch team analytics
  const { data: teamData, isLoading: isTeamsLoading, isError: isTeamsError } = useQuery<TeamAnalytics[]>({
    queryKey: ['admin-teams'],
    queryFn: async () => {
      const response = await fetch('/api/reports/admin/teams', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });
      if (!response.ok) throw new Error('Failed to fetch team analytics');
      return response.json();
    },
    refetchInterval: 30000,
    enabled: isAdminUser(user), // Only fetch if admin
  });

  // Fetch all users summary — with pagination (Task 6.2)
  const { data: usersResponse, isLoading: isUsersLoading, isError: isUsersError } = useQuery<UserSummary[] | { data: UserSummary[]; total: number; page: number; page_size: number; has_next: boolean; has_prev: boolean; total_pages: number }>({
    queryKey: ['admin-users', userPeriod, usersPage],
    queryFn: async () => {
      const response = await fetch(`/api/reports/admin/users?period=${userPeriod}&page=${usersPage}&page_size=${usersPageSize}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });
      if (!response.ok) throw new Error('Failed to fetch users summary');
      return response.json();
    },
    refetchInterval: 30000,
    enabled: isAdminUser(user),
  });

  // Separate unpaginated query for the staff dropdown (always shows all users)
  const { data: allUsersForDropdown } = useQuery<UserSummary[]>({
    queryKey: ['admin-users-all', userPeriod],
    queryFn: async () => {
      const response = await fetch(`/api/reports/admin/users?period=${userPeriod}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });
      if (!response.ok) throw new Error('Failed to fetch users list');
      return response.json();
    },
    staleTime: 60000, // cache for 1 minute to avoid extra requests
    enabled: isAdminUser(user),
  });

  // Handle both paginated and legacy array responses
  const usersData: UserSummary[] = Array.isArray(usersResponse)
    ? usersResponse
    : usersResponse?.data ?? [];
  const usersPagination = usersResponse && !Array.isArray(usersResponse) && usersResponse.total != null
    ? {
        total: usersResponse.total,
        page: usersResponse.page,
        pageSize: usersResponse.page_size,
        hasNext: usersResponse.has_next,
        hasPrev: usersResponse.has_prev,
        totalPages: usersResponse.total_pages,
      }
    : null;

  const selectableUsers = useMemo(
    () =>
      (allUsersForDropdown ?? usersData).map((u) => ({
        id: u.user_id,
        name: u.user_name,
        email: u.user_email ?? '',
      })),
    [allUsersForDropdown, usersData]
  );

  // Fetch selected user detail
  const { data: selectedUserDetail, isLoading: isSelectedUserLoading } = useQuery<SelectedUserDetail>({
    queryKey: ['admin-user-detail', selectedUserId],
    queryFn: async () => {
      const response = await fetch(`/api/reports/admin/users/${selectedUserId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });
      if (!response.ok) throw new Error('Failed to fetch user detail');
      return response.json();
    },
    enabled: isAdminUser(user) && selectedUserId !== null,
  });

  const selectedUserAvgSubtitle = selectedUserDetail
    ? getAvgHoursSubtitle(
        {
          avg_denominator_days: selectedUserDetail.avg_denominator_days,
          avg_denominator_type: selectedUserDetail.avg_denominator_type,
          avg_includes_today: selectedUserDetail.avg_includes_today,
        },
        selectedUserDetail.active_days_this_month,
      )
    : 'across 0 days';

  const selectedUserAvgTooltip = selectedUserDetail
    ? getAvgHoursTooltip({
        avg_includes_today: selectedUserDetail.avg_includes_today,
        avg_working_days_source: selectedUserDetail.avg_working_days_source,
        avg_working_days_used: selectedUserDetail.avg_working_days_used,
      })
    : 'Excludes today (in progress) and non-working days.';

  // Redirect if not admin
  if (!isAdminUser(user)) {
    navigate('/reports');
    return null;
  }

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
            <svg className="h-8 w-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Admin Analytics Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Comprehensive insights into team performance and productivity
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="mb-6 border-b border-gray-200 dark:border-gray-700">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('overview')}
              className={`${
                activeTab === 'overview'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" /></svg>
              Overview
            </button>
            <button
              onClick={() => setActiveTab('teams')}
              className={`${
                activeTab === 'teams'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
            >
              <UserGroupIcon className="h-5 w-5" />
              Teams
            </button>
            <button
              onClick={() => setActiveTab('individuals')}
              className={`${
                activeTab === 'individuals'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
            >
              <UsersIcon className="h-5 w-5" />
              Individuals
            </button>
          </nav>
        </div>

        {/* Overview Tab */}
        {activeTab === 'overview' && dashboardData && (
          <div className="space-y-6">
            {/* Key Metrics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Today</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                      {dashboardData.total_today_hours}h
                    </p>
                    <p className="text-xs text-gray-500 mt-1">{formatTime(dashboardData.total_today_seconds)}</p>
                  </div>
                  <ClockIcon className="h-12 w-12 text-blue-500" />
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600 dark:text-gray-400">This Week</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                      {dashboardData.total_week_hours}h
                    </p>
                    <p className="text-xs text-gray-500 mt-1">{formatTime(dashboardData.total_week_seconds)}</p>
                  </div>
                  <ArrowTrendingUpIcon className="h-12 w-12 text-green-500" />
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600 dark:text-gray-400">This Month</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                      {dashboardData.total_month_hours}h
                    </p>
                    <p className="text-xs text-gray-500 mt-1">{formatTime(dashboardData.total_month_seconds)}</p>
                  </div>
                  <ChartBarIcon className="h-12 w-12 text-purple-500" />
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Active Now</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                      {dashboardData.running_timers}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">{dashboardData.active_users_today} users today</p>
                  </div>
                  <UsersIcon className="h-12 w-12 text-orange-500" />
                </div>
              </div>
            </div>

            {/* Top Performers Today */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <TrophyIcon className="h-6 w-6 text-yellow-500" />
                  Top Performers Today
                </h2>
              </div>
              <div className="p-6">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={dashboardData.by_user.slice(0, 10)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="user_name" angle={-45} textAnchor="end" height={100} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="total_hours" fill="#3b82f6" name="Hours Worked" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* User Distribution Pie Chart */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Time Distribution Today
                </h2>
              </div>
              <div className="p-6">
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={dashboardData.by_user.slice(0, 8)}
                      dataKey="total_hours"
                      nameKey="user_name"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label
                    >
                      {dashboardData.by_user.slice(0, 8).map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* AI Payroll Forecast */}
            {payrollForecastEnabled && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    <span>🤖</span> AI Payroll Forecast
                  </h2>
                </div>
                <div className="p-6">
                  <PayrollForecastPanel />
                </div>
              </div>
            )}

            {/* AI Overtime Risk */}
            {overtimeRiskEnabled && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    <span>⏰</span> AI Overtime Risk Analysis
                  </h2>
                </div>
                <div className="p-6">
                  <OvertimeRiskPanel />
                </div>
              </div>
            )}

            {/* AI Project Budget */}
            {projectBudgetEnabled && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    <span>💰</span> AI Project Budget Forecast
                  </h2>
                </div>
                <div className="p-6">
                  <ProjectBudgetPanel />
                </div>
              </div>
            )}

            {/* AI Cash Flow Chart */}
            {cashFlowEnabled && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    <span>📈</span> AI Cash Flow Projection
                  </h2>
                </div>
                <div className="p-6">
                  <CashFlowChart weeksAhead={8} />
                </div>
              </div>
            )}

            {/* AI Burnout Risk Assessment */}
            {burnoutRiskEnabled && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow" role="region" aria-label="AI Burnout Risk Assessment">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    <span>💚</span> AI Burnout Risk Assessment
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    Monitor employee wellbeing and identify burnout risks early
                  </p>
                </div>
                <div className="p-6">
                  <BurnoutRiskPanel periodDays={30} />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Teams Tab */}
        {activeTab === 'teams' && (
          <div className="space-y-6">
            {isTeamsLoading && (
              <div className="flex justify-center items-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              </div>
            )}
            
            {isTeamsError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
                <p className="text-red-800">Failed to load team analytics. Please try refreshing the page.</p>
              </div>
            )}
            
            {!isTeamsLoading && !isTeamsError && teamData && teamData.length === 0 && (
              <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center">
                <UserGroupIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600 dark:text-gray-400 text-lg">No team data available</p>
                <p className="text-gray-500 dark:text-gray-500 text-sm mt-2">Teams will appear here once they have time entries.</p>
              </div>
            )}
            
            {!isTeamsLoading && !isTeamsError && teamData && teamData.length > 0 && (
              <>
            {/* Team Comparison Chart */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Team Performance Comparison (This Week)
                </h2>
              </div>
              <div className="p-6">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={teamData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="team_name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="total_week_hours" fill="#10b981" name="Hours This Week" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Team Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {teamData.map((team) => (
                <div key={team.team_id} className="bg-white dark:bg-gray-800 rounded-lg shadow">
                  <div className="p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                        <UserGroupIcon className="h-6 w-6 text-blue-600" />
                        {team.team_name}
                      </h3>
                      <span className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 text-xs font-medium px-2.5 py-0.5 rounded">
                        {team.member_count} members
                      </span>
                    </div>

                    {/* Team Stats */}
                    <div className="grid grid-cols-3 gap-4 mb-4">
                      <div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Today</p>
                        <p className="text-lg font-semibold text-gray-900 dark:text-white">
                          {team.total_today_hours}h
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">This Week</p>
                        <p className="text-lg font-semibold text-gray-900 dark:text-white">
                          {team.total_week_hours}h
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">This Month</p>
                        <p className="text-lg font-semibold text-gray-900 dark:text-white">
                          {team.total_month_hours}h
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 mb-4 text-sm">
                      <span className="text-gray-600 dark:text-gray-400">
                        Active Today: <strong>{team.active_members_today}</strong>
                      </span>
                      <span className="text-gray-600 dark:text-gray-400">
                        Running: <strong>{team.running_timers}</strong>
                      </span>
                    </div>

                    <div className="mb-4">
                      <button
                        onClick={() => setSelectedTeamForAnalytics(team)}
                        className="inline-flex items-center rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
                      >
                        AI Analytics
                      </button>
                    </div>

                    {/* Top Performers */}
                    {team.top_performers.length > 0 && (
                      <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-1">
                          <TrophyIcon className="h-4 w-4 text-yellow-500" />
                          Top Performers This Week
                        </p>
                        <div className="space-y-2">
                          {team.top_performers.map((performer, index) => (
                            <div key={performer.user_id} className="flex items-center justify-between text-sm">
                              <div className="flex items-center gap-2">
                                <span className="text-gray-400 font-mono">#{index + 1}</span>
                                <span className="text-gray-900 dark:text-white">{performer.user_name}</span>
                              </div>
                              <span className="font-semibold text-blue-600 dark:text-blue-400">
                                {performer.total_hours}h
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {selectedTeamForAnalytics && (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
                role="dialog"
                aria-modal="true"
                aria-label={`AI analytics for ${selectedTeamForAnalytics.team_name}`}
              >
                <div className="max-h-[90vh] w-full max-w-6xl overflow-y-auto rounded-xl bg-gray-50 p-6 dark:bg-gray-900">
                  <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                      {selectedTeamForAnalytics.team_name} AI Analytics
                    </h2>
                    <button
                      onClick={() => setSelectedTeamForAnalytics(null)}
                      className="rounded p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-200"
                      aria-label="Close team analytics"
                    >
                      <XMarkIcon className="h-5 w-5" />
                    </button>
                  </div>

                  <TeamAnalyticsPanel
                    teamId={selectedTeamForAnalytics.team_id}
                    teamName={selectedTeamForAnalytics.team_name}
                    periodDays={30}
                  />
                </div>
              </div>
            )}
              </>
            )}
          </div>
        )}

        {/* Individuals Tab */}
        {activeTab === 'individuals' && (
          <div className="space-y-6">
            {isUsersLoading && (
              <div className="flex justify-center items-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              </div>
            )}
            
            {isUsersError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
                <p className="text-red-800">Failed to load user data. Please try refreshing the page.</p>
              </div>
            )}
            
            {!isUsersLoading && !isUsersError && usersData && usersData.length === 0 && (
              <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center">
                <UsersIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600 dark:text-gray-400 text-lg">No user data available for this period</p>
                <p className="text-gray-500 dark:text-gray-500 text-sm mt-2">Users will appear here once they have time entries.</p>
              </div>
            )}
            
            {!isUsersLoading && !isUsersError && usersData && usersData.length > 0 && (
              <>
            {/* User Selector and Period Selector */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
              <div className="flex flex-wrap items-center gap-4">
                {/* User Selector Dropdown */}
                <div className="flex items-center gap-2">
                  <label htmlFor="admin-reports-user-select" className="text-sm font-medium text-gray-700 dark:text-gray-300">Select Staff:</label>
                  <div className="min-w-[240px]">
                    <UserSelect
                      id="admin-reports-user-select"
                      value={selectedUserId}
                      onChange={setSelectedUserId}
                      users={selectableUsers}
                      clearable
                      clearLabel="-- All Staff Comparison --"
                      placeholder="-- All Staff Comparison --"
                      ariaLabel="Select staff"
                      inputClassName="border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    />
                  </div>
                </div>
                
                {/* Period Selector */}
                <div className="flex items-center gap-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Time Period:</label>
                  <div className="flex gap-2">
                  {(['today', 'week', 'month'] as const).map((period) => (
                    <button
                      key={period}
                      onClick={() => { setUserPeriod(period); setUsersPage(1); }}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        userPeriod === period
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
                      }`}
                    >
                      {period.charAt(0).toUpperCase() + period.slice(1)}
                    </button>
                  ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Selected User Detail Panel */}
            {selectedUserId && selectedUserDetail && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow border-2 border-blue-500">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    <UserIcon className="h-5 w-5 text-blue-500" />
                    {selectedUserDetail.user_name}'s Performance Details
                  </h2>
                  <button
                    onClick={() => setSelectedUserId(null)}
                    className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                </div>
                <div className="p-6">
                  {/* User Info */}
                  <div className="mb-4 text-sm text-gray-600 dark:text-gray-400">
                    <span className="font-medium">{selectedUserDetail.user_email}</span>
                    <span className="mx-2">•</span>
                    <span className="capitalize">{selectedUserDetail.role}</span>
                    {selectedUserDetail.teams.length > 0 && (
                      <>
                        <span className="mx-2">•</span>
                        <span>Teams: {selectedUserDetail.teams.join(', ')}</span>
                      </>
                    )}
                    {selectedUserDetail.current_timer_running && (
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
                        Timer Running
                      </span>
                    )}
                  </div>
                  
                  {/* User Summary Stats */}
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
                    <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-4">
                      <p className="text-sm text-blue-600 dark:text-blue-400">Today</p>
                      <p className="text-xl font-bold text-blue-700 dark:text-blue-300">
                        {selectedUserDetail.today_hours.toFixed(1)}h
                      </p>
                    </div>
                    <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-4">
                      <p className="text-sm text-green-600 dark:text-green-400">This Week</p>
                      <p className="text-xl font-bold text-green-700 dark:text-green-300">
                        {selectedUserDetail.week_hours.toFixed(1)}h
                      </p>
                    </div>
                    <div className="bg-purple-50 dark:bg-purple-900/30 rounded-lg p-4">
                      <p className="text-sm text-purple-600 dark:text-purple-400">This Month</p>
                      <p className="text-xl font-bold text-purple-700 dark:text-purple-300">
                        {selectedUserDetail.month_hours.toFixed(1)}h
                      </p>
                    </div>
                    <div className="bg-orange-50 dark:bg-orange-900/30 rounded-lg p-4">
                      <p className="text-sm text-orange-600 dark:text-orange-400">Total Entries</p>
                      <p className="text-xl font-bold text-orange-700 dark:text-orange-300">
                        {selectedUserDetail.total_entries}
                      </p>
                    </div>
                    <div className="bg-teal-50 dark:bg-teal-900/30 rounded-lg p-4">
                      <p className="text-sm text-teal-600 dark:text-teal-400">Active Days</p>
                      <p className="text-xl font-bold text-teal-700 dark:text-teal-300">
                        {selectedUserDetail.active_days_this_month}
                      </p>
                    </div>
                    <div className="bg-pink-50 dark:bg-pink-900/30 rounded-lg p-4">
                      <div className="flex items-center gap-2">
                        <p className="text-sm text-pink-600 dark:text-pink-400">Avg/Day</p>
                        <button
                          type="button"
                          className="w-4 h-4 rounded-full border border-pink-300 text-[10px] text-pink-600 leading-none"
                          title={selectedUserAvgTooltip}
                          aria-label="Avg/Day calculation details"
                        >
                          ?
                        </button>
                      </div>
                      <p className="text-xl font-bold text-pink-700 dark:text-pink-300">
                        {selectedUserDetail.avg_hours_per_day.toFixed(1)}h
                      </p>
                      <p className="text-xs text-pink-700/80 dark:text-pink-200/80 mt-1">
                        {selectedUserAvgSubtitle}
                      </p>
                    </div>
                  </div>
                  
                  {/* Projects Breakdown */}
                  {selectedUserDetail.projects && selectedUserDetail.projects.length > 0 && (
                    <div>
                      <h3 className="text-md font-semibold text-gray-900 dark:text-white mb-3">Project Breakdown</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                        {selectedUserDetail.projects.map((proj, idx) => (
                          <div key={idx} className="flex justify-between items-center p-3 bg-gray-50 dark:bg-gray-700 rounded">
                            <span className="text-gray-700 dark:text-gray-300 truncate mr-2">{proj.project_name}</span>
                            <span className="font-medium text-gray-900 dark:text-white whitespace-nowrap">
                              {proj.total_hours.toFixed(1)}h ({proj.entry_count} entries)
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Last Activity */}
                  {selectedUserDetail.last_activity && (
                    <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
                      Last activity: {new Date(selectedUserDetail.last_activity).toLocaleString()}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* User Ranking Chart */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  User Performance Ranking
                </h2>
              </div>
              <div className="p-6">
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={usersData.slice(0, 15)} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis dataKey="user_name" type="category" width={120} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="total_hours" fill="#8b5cf6" name="Hours Worked">
                      {usersData.slice(0, 15).map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* User Details Table */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  All Users Detail
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-900">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Rank
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        User
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Hours
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Entries
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Avg Hours/Entry
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                    {usersData.map((user, index) => {
                      const globalRank = usersPagination
                        ? (usersPagination.page - 1) * usersPagination.pageSize + index
                        : index;
                      return (
                      <tr key={user.user_id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            {globalRank < 3 ? (
                              <TrophyIcon
                                className={`h-5 w-5 ${
                                  globalRank === 0
                                    ? 'text-yellow-500'
                                    : globalRank === 1
                                    ? 'text-gray-400'
                                    : 'text-orange-600'
                                }`}
                              />
                            ) : (
                              <span className="text-sm text-gray-500 dark:text-gray-400">#{globalRank + 1}</span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900 dark:text-white">
                            {user.user_name}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900 dark:text-white font-semibold">
                            {user.total_hours}h
                          </div>
                          <div className="text-xs text-gray-500">{formatTime(user.total_seconds)}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                          {user.entry_count}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                          {user.entry_count > 0 ? (user.total_hours / user.entry_count).toFixed(2) : '0.00'}h
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <button
                            onClick={() => navigate(`/admin/user/${user.user_id}`)}
                            className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300 font-medium"
                          >
                            View Details →
                          </button>
                        </td>
                      </tr>
                    );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Pagination Controls (Task 6.2) */}
            {usersPagination && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    Showing {((usersPagination.page - 1) * usersPagination.pageSize) + 1}–
                    {Math.min(usersPagination.page * usersPagination.pageSize, usersPagination.total)} of{' '}
                    {usersPagination.total} users
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setUsersPage((p) => Math.max(1, p - 1))}
                      disabled={!usersPagination.hasPrev}
                      className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                        usersPagination.hasPrev
                          ? 'bg-blue-600 text-white hover:bg-blue-700'
                          : 'bg-gray-200 text-gray-400 cursor-not-allowed dark:bg-gray-700 dark:text-gray-500'
                      }`}
                    >
                      Previous
                    </button>
                    <span className="text-sm text-gray-600 dark:text-gray-400">
                      Page {usersPagination.page} of {usersPagination.totalPages}
                    </span>
                    <button
                      onClick={() => setUsersPage((p) => p + 1)}
                      disabled={!usersPagination.hasNext}
                      className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                        usersPagination.hasNext
                          ? 'bg-blue-600 text-white hover:bg-blue-700'
                          : 'bg-gray-200 text-gray-400 cursor-not-allowed dark:bg-gray-700 dark:text-gray-500'
                      }`}
                    >
                      Next
                    </button>
                  </div>
                </div>
              </div>
            )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

