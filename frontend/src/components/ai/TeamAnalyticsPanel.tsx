import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
} from 'recharts';
import {
  type TeamAnalyticsResponse,
  getTeamAnalytics,
} from '../../api/aiServices';

interface TeamAnalyticsPanelProps {
  teamId: number;
  periodDays?: number;
  teamName?: string;
  className?: string;
}

function formatTrendLabel(trend: TeamAnalyticsResponse['current_velocity_trend']): string {
  if (trend === 'increasing') return 'Increasing';
  if (trend === 'decreasing') return 'Decreasing';
  if (trend === 'stable') return 'Stable';
  return 'Unknown';
}

function formatVelocityLabel(isoDate: string): string {
  const d = new Date(isoDate);
  if (Number.isNaN(d.getTime())) return isoDate;
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export default function TeamAnalyticsPanel({
  teamId,
  periodDays = 30,
  teamName,
  className = '',
}: TeamAnalyticsPanelProps) {
  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['ai-team-analytics', teamId, periodDays],
    queryFn: () =>
      getTeamAnalytics({
        team_id: teamId,
        period_days: periodDays,
        include_ai_insights: true,
      }),
    enabled: teamId > 0,
    retry: 1,
  });

  const velocityData = useMemo(
    () =>
      (data?.velocity_history ?? []).map((point) => ({
        ...point,
        label: formatVelocityLabel(point.period_end),
      })),
    [data?.velocity_history]
  );

  const topCollaborationEdges = useMemo(
    () => (data?.collaboration_edges ?? []).slice(0, 6),
    [data?.collaboration_edges]
  );

  if (isLoading) {
    return (
      <div className={`rounded-lg border border-gray-200 dark:border-gray-700 p-6 ${className}`} role="status">
        <div className="flex items-center gap-3 text-gray-600 dark:text-gray-300">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          <span>Loading team analytics...</span>
        </div>
      </div>
    );
  }

  if (isError || !data || !data.success) {
    return (
      <div className={`rounded-lg border border-red-200 bg-red-50 p-6 dark:border-red-800 dark:bg-red-900/20 ${className}`} role="alert">
        <p className="font-medium text-red-800 dark:text-red-300">Failed to load AI team analytics.</p>
        <button
          onClick={() => refetch()}
          className="mt-3 rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  const insights = data.ai_insights ?? [];
  const recommendations = data.recommendations ?? [];
  const topContributors = data.top_contributors ?? [];
  const underutilized = data.underutilized_members ?? [];

  if ((data.total_members ?? 0) === 0) {
    return (
      <div className={`rounded-lg border border-gray-200 bg-gray-50 p-6 dark:border-gray-700 dark:bg-gray-800 ${className}`}>
        <p className="text-gray-700 dark:text-gray-200">No team members available for analytics.</p>
      </div>
    );
  }

  return (
    <div className={`space-y-5 ${className}`} data-testid="team-analytics-panel">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          AI Team Analytics: {data.team_name || teamName || `Team ${teamId}`}
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Last {data.period_days} days, generated {new Date(data.generated_at).toLocaleString()}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-lg bg-white p-3 shadow dark:bg-gray-800">
          <p className="text-xs text-gray-500">Total Hours</p>
          <p className="text-xl font-semibold text-gray-900 dark:text-white">{data.total_hours.toFixed(1)}h</p>
        </div>
        <div className="rounded-lg bg-white p-3 shadow dark:bg-gray-800">
          <p className="text-xs text-gray-500">Active Members</p>
          <p className="text-xl font-semibold text-gray-900 dark:text-white">{data.active_members}/{data.total_members}</p>
        </div>
        <div className="rounded-lg bg-white p-3 shadow dark:bg-gray-800">
          <p className="text-xs text-gray-500">Projects</p>
          <p className="text-xl font-semibold text-gray-900 dark:text-white">{data.total_projects}</p>
        </div>
        <div className="rounded-lg bg-white p-3 shadow dark:bg-gray-800">
          <p className="text-xs text-gray-500">Tasks</p>
          <p className="text-xl font-semibold text-gray-900 dark:text-white">{data.total_tasks}</p>
        </div>
        <div className="rounded-lg bg-white p-3 shadow dark:bg-gray-800">
          <p className="text-xs text-gray-500">Avg/Member</p>
          <p className="text-xl font-semibold text-gray-900 dark:text-white">{data.avg_hours_per_member.toFixed(1)}h</p>
        </div>
        <div className="rounded-lg bg-white p-3 shadow dark:bg-gray-800">
          <p className="text-xs text-gray-500">Velocity Trend</p>
          <p className="text-xl font-semibold text-gray-900 dark:text-white">{formatTrendLabel(data.current_velocity_trend)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section className="rounded-lg bg-white p-4 shadow dark:bg-gray-800">
          <h4 className="mb-3 font-semibold text-gray-900 dark:text-white">Velocity</h4>
          {velocityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={velocityData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="total_hours" stroke="#2563eb" strokeWidth={2} name="Total Hours" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-500">No velocity history available.</p>
          )}
        </section>

        <section className="rounded-lg bg-white p-4 shadow dark:bg-gray-800">
          <h4 className="mb-3 font-semibold text-gray-900 dark:text-white">Workload</h4>
          <p className="mb-3 text-sm text-gray-600 dark:text-gray-300">
            Distribution index (Gini): <span className="font-semibold">{data.workload_gini.toFixed(2)}</span>
          </p>
          {topContributors.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={topContributors}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="hours" fill="#10b981" name="Hours" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-500">No contributor breakdown available.</p>
          )}
        </section>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section className="rounded-lg bg-white p-4 shadow dark:bg-gray-800">
          <h4 className="mb-2 font-semibold text-gray-900 dark:text-white">Collaboration</h4>
          <p className="mb-3 text-sm text-gray-600 dark:text-gray-300">
            Collaboration density: <span className="font-semibold">{data.collaboration_density.toFixed(2)}</span>
          </p>
          {topCollaborationEdges.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {topCollaborationEdges.map((edge) => (
                <li key={`${edge.user1_id}-${edge.user2_id}`} className="flex items-center justify-between rounded border border-gray-200 px-3 py-2 dark:border-gray-700">
                  <span className="text-gray-700 dark:text-gray-200">{edge.user1_name} & {edge.user2_name}</span>
                  <span className="font-medium text-gray-900 dark:text-white">{edge.shared_projects} shared</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">No collaboration edge data available.</p>
          )}
        </section>

        <section className="rounded-lg bg-white p-4 shadow dark:bg-gray-800">
          <h4 className="mb-2 font-semibold text-gray-900 dark:text-white">Underutilized Members</h4>
          {underutilized.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {underutilized.map((member) => (
                <li key={member.user_id} className="flex items-center justify-between rounded border border-gray-200 px-3 py-2 dark:border-gray-700">
                  <span className="text-gray-700 dark:text-gray-200">{member.name}</span>
                  <span className="font-medium text-gray-900 dark:text-white">{member.hours.toFixed(1)}h</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">No underutilization signals available.</p>
          )}
        </section>
      </div>

      {insights.length > 0 && (
        <section className="rounded-lg bg-white p-4 shadow dark:bg-gray-800">
          <h4 className="mb-2 font-semibold text-gray-900 dark:text-white">AI Insights</h4>
          <ul className="space-y-2 text-sm text-gray-700 dark:text-gray-200">
            {insights.map((insight, idx) => (
              <li key={idx} className="rounded border border-gray-200 px-3 py-2 dark:border-gray-700">{insight}</li>
            ))}
          </ul>
        </section>
      )}

      {recommendations.length > 0 && (
        <section className="rounded-lg bg-white p-4 shadow dark:bg-gray-800">
          <h4 className="mb-2 font-semibold text-gray-900 dark:text-white">Recommendations</h4>
          <ul className="space-y-2 text-sm text-gray-700 dark:text-gray-200">
            {recommendations.map((recommendation, idx) => (
              <li key={idx} className="rounded border border-gray-200 px-3 py-2 dark:border-gray-700">{recommendation}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
