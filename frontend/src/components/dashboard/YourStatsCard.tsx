// ============================================
// TIME TRACKER - YOUR STATS CARD
// Hybrid live-refresh: Today updates every second
// while timer is running; other stats poll every 60s.
// ============================================
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '../common';
import { formatDuration } from '../../utils/helpers';
import type { DashboardStats } from '../../types';

// ---------------------------------------------------------------------------
// Sub-component: StatCard
// ---------------------------------------------------------------------------

interface StatCardProps {
  title: string;
  value: string;
  icon: React.ReactNode;
  color: 'blue' | 'green' | 'amber' | 'purple';
  live?: boolean;
}

function StatCard({ title, value, icon, color, live }: StatCardProps) {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    amber: 'bg-amber-50 text-amber-600',
    purple: 'bg-purple-50 text-purple-600',
  };
  return (
    <Card>
      <div className="flex items-center space-x-4">
        <div className={'p-3 rounded-lg ' + colorMap[color]}>{icon}</div>
        <div>
          <p className="text-sm text-gray-500 flex items-center gap-1.5">
            {title}
            {live && (
              <span
                className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"
                aria-label="live"
                data-testid="live-indicator"
              />
            )}
          </p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export interface YourStatsCardProps {
  stats: DashboardStats | undefined;
  isAdmin?: boolean;
  /**
   * Unix timestamp (ms) from React Query's `dataUpdatedAt` — the moment the
   * last successful response was received. Used to compute how many seconds
   * have elapsed since the last poll so Today can tick forward accurately.
   */
  dataUpdatedAt?: number;
  /** Whether the current user's task timer is running. */
  isTimerRunning?: boolean;
  /** Whether the timer is paused (break / meeting). A paused timer is not ticking. */
  isTimerPaused?: boolean;
}

export function YourStatsCard({
  stats,
  isAdmin = false,
  dataUpdatedAt,
  isTimerRunning = false,
  isTimerPaused = false,
}: YourStatsCardProps) {
  const { t } = useTranslation();

  // True when the timer is actively ticking (running AND not paused)
  const timerIsLive = isTimerRunning && !isTimerPaused;

  // A dummy counter that increments every second to trigger a re-render
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!timerIsLive) return;
    const id = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [timerIsLive]);

  // Live "Today":
  //   backend already includes the running timer in today_seconds (up to poll time).
  //   We add the seconds that have elapsed *since* the last poll to keep it current.
  const secondsSinceLastPoll =
    timerIsLive && dataUpdatedAt
      ? Math.max(0, Math.floor((Date.now() - dataUpdatedAt) / 1000))
      : 0;
  const todayDisplaySeconds = (stats?.today_seconds ?? 0) + secondsSinceLastPoll;

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-700 mb-3">
        {isAdmin ? t('dashboard.yourPersonalStats') : t('dashboard.yourStats')}
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t('dashboard.today')}
          value={formatDuration(todayDisplaySeconds)}
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          color="blue"
          live={timerIsLive}
        />
        <StatCard
          title={t('dashboard.thisWeek')}
          value={formatDuration(stats?.week_seconds ?? 0)}
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          }
          color="green"
        />
        <StatCard
          title={t('dashboard.thisMonth')}
          value={formatDuration(stats?.month_seconds ?? 0)}
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          }
          color="amber"
        />
        <StatCard
          title={t('dashboard.activeProjects')}
          value={String(stats?.active_projects ?? 0)}
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          }
          color="purple"
        />
      </div>
    </div>
  );
}
