import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../stores/authStore';
import { reportsApi } from '../api/client';
import {
  ArrowLeftIcon,
  UserCircleIcon,
  ClockIcon,
  ChartBarIcon,
  CalendarIcon,
  BriefcaseIcon,
  FireIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '../components/Icons';
import { BarChart, Bar, PieChart, Pie, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

interface IndividualUserMetrics {
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

export default function UserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);

  // Redirect if not admin
  if (user?.role !== 'admin' && user?.role !== 'super_admin') {
    navigate('/reports');
    return null;
  }

  const { data: userData, isLoading } = useQuery<IndividualUserMetrics>({
    queryKey: ['user-detail', userId],
    queryFn: async () => {
      return reportsApi.getAdminUserDetail(parseInt(userId!));
    },
    enabled: !!userId,
  });

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-gray-600 dark:text-gray-400">Loading user details...</div>
      </div>
    );
  }

  if (!userData) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-red-600">User not found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Back Button */}
        <button
          onClick={() => navigate('/admin/reports')}
          className="mb-6 flex items-center gap-2 text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
        >
          <ArrowLeftIcon className="h-5 w-5" />
          Back to Admin Reports
        </button>

        {/* User Header */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <UserCircleIcon className="h-16 w-16 text-gray-400" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {userData.user_name}
                </h1>
                <p className="text-gray-600 dark:text-gray-400">{userData.user_email}</p>
                <div className="flex items-center gap-3 mt-2">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                    {userData.role}
                  </span>
                  {userData.teams.map((team) => (
                    <span
                      key={team}
                      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200"
                    >
                      {team}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-2">
                {userData.current_timer_running ? (
                  <>
                    <CheckCircleIcon className="h-5 w-5 text-green-500" />
                    <span className="text-sm font-medium text-green-600 dark:text-green-400">
                      Timer Running
                    </span>
                  </>
                ) : (
                  <>
                    <XCircleIcon className="h-5 w-5 text-gray-400" />
                    <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
                      Inactive
                    </span>
                  </>
                )}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Last Activity: {formatDate(userData.last_activity)}
              </p>
            </div>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Today</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                  {userData.today_hours}h
                </p>
                <p className="text-xs text-gray-500 mt-1">{formatTime(userData.today_seconds)}</p>
              </div>
              <ClockIcon className="h-12 w-12 text-blue-500" />
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">This Week</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                  {userData.week_hours}h
                </p>
                <p className="text-xs text-gray-500 mt-1">{formatTime(userData.week_seconds)}</p>
              </div>
              <ChartBarIcon className="h-12 w-12 text-green-500" />
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">This Month</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                  {userData.month_hours}h
                </p>
                <p className="text-xs text-gray-500 mt-1">{formatTime(userData.month_seconds)}</p>
              </div>
              <CalendarIcon className="h-12 w-12 text-purple-500" />
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Avg Hours/Day</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
                  {userData.avg_hours_per_day}h
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {userData.active_days_this_month} active days
                </p>
              </div>
              <FireIcon className="h-12 w-12 text-orange-500" />
            </div>
          </div>
        </div>

        {/* Activity Stats */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Activity Summary
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600 dark:text-gray-400">Total Entries</span>
                <span className="text-lg font-semibold text-gray-900 dark:text-white">
                  {userData.total_entries}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600 dark:text-gray-400">Active Days (Month)</span>
                <span className="text-lg font-semibold text-gray-900 dark:text-white">
                  {userData.active_days_this_month}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600 dark:text-gray-400">Avg Hours/Entry</span>
                <span className="text-lg font-semibold text-gray-900 dark:text-white">
                  {userData.total_entries > 0
                    ? (userData.month_hours / userData.total_entries).toFixed(2)
                    : '0.00'}h
                </span>
              </div>
            </div>
          </div>

          <div className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Time Breakdown (This Month)
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                  {userData.month_hours}h
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Total Hours</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-green-600 dark:text-green-400">
                  {userData.projects.length}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Projects</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-purple-600 dark:text-purple-400">
                  {userData.total_entries}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Entries</p>
              </div>
            </div>
          </div>
        </div>

        {/* Project Breakdown */}
        {userData.projects.length > 0 && (
          <>
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow mb-6">
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <BriefcaseIcon className="h-6 w-6 text-blue-600" />
                  Project Distribution (This Month)
                </h2>
              </div>
              <div className="p-6">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={userData.projects}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="project_name" angle={-45} textAnchor="end" height={100} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="total_hours" fill="#3b82f6" name="Hours" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Project Pie Chart */}
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Time Distribution by Project
                  </h3>
                </div>
                <div className="p-6">
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={userData.projects}
                        dataKey="total_hours"
                        nameKey="project_name"
                        cx="50%"
                        cy="50%"
                        outerRadius={100}
                        label
                      >
                        {userData.projects.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Project Details Table */}
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Project Details
                  </h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gray-50 dark:bg-gray-900">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                          Project
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                          Hours
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                          Entries
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                      {userData.projects.map((project) => (
                        <tr key={project.project_id}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                            {project.project_name}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                            <div className="font-semibold">{project.total_hours}h</div>
                            <div className="text-xs text-gray-500">
                              {formatTime(project.total_seconds)}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                            {project.entry_count}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
