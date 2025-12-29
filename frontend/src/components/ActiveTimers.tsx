// ============================================
// TIME TRACKER - ACTIVE TIMERS WIDGET
// "Who's Working Now" Real-time Display
// ============================================
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from './common';
import { useWebSocketContext, type ActiveTimer } from '../contexts/WebSocketContext';
import { timeEntriesApi } from '../api/client';

interface ActiveTimersProps {
  teamId?: number;
  className?: string;
}

export function ActiveTimers({ teamId, className = '' }: ActiveTimersProps) {
  const { isConnected, activeTimers: wsActiveTimers, requestActiveTimers } = useWebSocketContext();
  const [currentTime, setCurrentTime] = useState(new Date());

  // Fallback: Query active timers from API if WebSocket is not connected
  const { data: apiActiveTimers, refetch } = useQuery({
    queryKey: ['active-timers'],
    queryFn: async () => {
      const response = await timeEntriesApi.getActiveTimers();
      return response as ActiveTimer[];
    },
    enabled: !isConnected, // Only query if WebSocket is disconnected
    refetchInterval: isConnected ? false : 5000, // Poll every 5 seconds when not connected
  });

  // Use WebSocket data if connected, otherwise use API data
  const activeTimers = isConnected ? wsActiveTimers : (apiActiveTimers || []);

  // Refresh timer display every second
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Request active timers when teamId changes (WebSocket only)
  useEffect(() => {
    if (isConnected) {
      requestActiveTimers(teamId);
    }
  }, [isConnected, teamId, requestActiveTimers]);

  // Refetch from API when not connected
  useEffect(() => {
    if (!isConnected) {
      refetch();
    }
  }, [isConnected, refetch]);

  const formatElapsed = (startTime: string): string => {
    const start = new Date(startTime);
    const diffMs = currentTime.getTime() - start.getTime();
    const seconds = Math.floor(diffMs / 1000);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return hours.toString().padStart(2, '0') + ':' + minutes.toString().padStart(2, '0') + ':' + secs.toString().padStart(2, '0');
  };

  const getInitials = (name: string | null | undefined): string => {
    if (!name) return '?';
    return name
      .split(' ')
      .map(n => n[0])
      .filter(Boolean)
      .join('')
      .toUpperCase()
      .slice(0, 2) || '?';
  };

  const getRandomColor = (userId: number): string => {
    const colors = [
      'bg-blue-500',
      'bg-green-500',
      'bg-purple-500',
      'bg-pink-500',
      'bg-indigo-500',
      'bg-teal-500',
      'bg-orange-500',
      'bg-red-500',
    ];
    return colors[userId % colors.length];
  };

  const connectionDotClass = isConnected ? 'bg-green-500' : 'bg-gray-400';

  return (
    <Card className={className}>
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Who's Working Now</h3>
          <div className="flex items-center gap-2">
            <span className={'w-2 h-2 rounded-full ' + connectionDotClass}></span>
            <span className="text-xs text-gray-500">
              {isConnected ? 'Live' : 'Connecting...'}
            </span>
          </div>
        </div>

        {activeTimers.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <svg
              className="mx-auto h-12 w-12 text-gray-400 mb-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="text-sm">No one is tracking time right now</p>
          </div>
        ) : (
          <div className="space-y-3">
            {activeTimers.map((timer: ActiveTimer) => (
              <div
                key={timer.user_id}
                className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                {/* User Avatar */}
                <div
                  className={'w-10 h-10 rounded-full flex items-center justify-center text-white font-medium text-sm ' + getRandomColor(timer.user_id)}
                >
                  {getInitials(timer.user_name)}
                </div>

                {/* Timer Info */}
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">
                    {timer.user_name}
                  </p>
                  <p className="text-sm text-gray-500 truncate">
                    {timer.project_name || timer.description || 'Working...'}
                    {timer.task_name ? ' • ' + timer.task_name : ''}
                  </p>
                </div>

                {/* Timer Duration */}
                <div className="flex-shrink-0">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-green-100 text-green-700 rounded-full text-sm font-mono">
                    <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
                    {formatElapsed(timer.start_time)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTimers.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-500 text-center">
              {activeTimers.length} {activeTimers.length === 1 ? 'person' : 'people'} tracking time
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
