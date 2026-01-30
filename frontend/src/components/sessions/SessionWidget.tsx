// ============================================
// TIME TRACKER - SESSION WIDGET COMPONENT
// Main widget showing current work session status
// ============================================
import { useEffect, useRef } from 'react';
import { Card } from '../common';
import { useSessionStore, formatDuration, getSessionStatusInfo } from '../../stores/sessionStore';
import { cn } from '../../utils/helpers';
import { useNotifications } from '../../hooks/useNotifications';
import { BreakControls } from './BreakControls';
import { MeetingControls } from './MeetingControls';

export function SessionWidget() {
  const {
    currentSession,
    activeBreak,
    activeMeeting,
    isLoading,
    error,
    sessionElapsedSeconds,
    breakElapsedSeconds,
    meetingElapsedSeconds,
    fetchCurrentSession,
    startSession,
    endSession,
    updateElapsedTimes,
    clearError,
  } = useSessionStore();

  const { addNotification } = useNotifications();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch session status on mount
  useEffect(() => {
    console.log('[SessionWidget] Component mounted, fetching session...');
    fetchCurrentSession();

    // Also fetch on window focus
    const handleFocus = () => {
      console.log('[SessionWidget] Window focused, refreshing session...');
      fetchCurrentSession();
    };
    window.addEventListener('focus', handleFocus);

    return () => {
      window.removeEventListener('focus', handleFocus);
    };
  }, [fetchCurrentSession]);

  // Update elapsed times every second when session is active
  useEffect(() => {
    if (currentSession && currentSession.status !== 'completed') {
      intervalRef.current = setInterval(() => {
        updateElapsedTimes();
      }, 1000);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [currentSession, updateElapsedTimes]);

  const handleStartSession = async () => {
    try {
      await startSession();
      addNotification({
        type: 'success',
        title: 'Session Started',
        message: 'You are now clocked in. Have a productive day!',
        duration: 3000,
      });
    } catch {
      addNotification({
        type: 'error',
        title: 'Failed to Start Session',
        message: 'Please try again',
      });
    }
  };

  const handleEndSession = async () => {
    try {
      await endSession();
      addNotification({
        type: 'success',
        title: 'Session Ended',
        message: `Great work today! You logged ${formatDuration(sessionElapsedSeconds)} of work time.`,
      });
    } catch {
      addNotification({
        type: 'error',
        title: 'Failed to End Session',
        message: 'Please try again',
      });
    }
  };

  const statusInfo = getSessionStatusInfo(currentSession?.status);
  const isOnBreakOrMeeting = !!activeBreak || !!activeMeeting;

  return (
    <Card className={cn(
      'transition-colors duration-300',
      currentSession?.status === 'active' && 'bg-gradient-to-r from-emerald-600 to-emerald-700 text-white',
      currentSession?.status === 'break' && 'bg-gradient-to-r from-amber-500 to-amber-600 text-white',
      currentSession?.status === 'meeting' && 'bg-gradient-to-r from-blue-500 to-blue-600 text-white',
      !currentSession && 'bg-gray-100'
    )}>
      {error && (
        <div className="mb-4 bg-red-500/20 border border-red-300/50 text-white px-4 py-2 rounded-lg text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={clearError} className="ml-2 hover:text-red-200">
            ×
          </button>
        </div>
      )}

      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        {/* Session status and timer */}
        <div className="flex items-center gap-4">
          <div className="text-2xl">{statusInfo.icon}</div>
          <div>
            <div className={cn(
              'text-sm font-medium',
              currentSession ? 'text-white/80' : 'text-gray-500'
            )}>
              {statusInfo.label}
            </div>
            <div className={cn(
              'text-3xl font-mono font-bold tracking-wider',
              !currentSession && 'text-gray-400'
            )}>
              {formatDuration(sessionElapsedSeconds)}
            </div>
          </div>
        </div>

        {/* Sub-timers for break/meeting */}
        {currentSession && (
          <div className="flex gap-6">
            {activeBreak && (
              <div className="text-center">
                <div className="text-xs text-white/70">Break Time</div>
                <div className="text-xl font-mono font-semibold text-amber-200">
                  {formatDuration(breakElapsedSeconds)}
                </div>
              </div>
            )}
            {activeMeeting && (
              <div className="text-center">
                <div className="text-xs text-white/70">Meeting Time</div>
                <div className="text-xl font-mono font-semibold text-blue-200">
                  {formatDuration(meetingElapsedSeconds)}
                </div>
              </div>
            )}
            <div className="text-center">
              <div className="text-xs text-white/70">Total Breaks</div>
              <div className="text-lg font-mono">
                {formatDuration(currentSession.total_break_seconds)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-white/70">Total Meetings</div>
              <div className="text-lg font-mono">
                {formatDuration(currentSession.total_meeting_seconds)}
              </div>
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {currentSession ? (
            <>
              {/* Break/Meeting controls (only when not already on break or in meeting) */}
              {!isOnBreakOrMeeting && (
                <>
                  <BreakControls />
                  <MeetingControls />
                </>
              )}
              
              {/* End break/meeting buttons */}
              {activeBreak && <BreakControls />}
              {activeMeeting && <MeetingControls />}

              {/* Clock Out button */}
              <button
                onClick={handleEndSession}
                disabled={isLoading}
                className={cn(
                  'px-4 py-2 rounded-lg font-semibold text-sm transition-all',
                  'bg-white/20 hover:bg-white/30 text-white border border-white/30',
                  isLoading && 'opacity-50 cursor-not-allowed'
                )}
              >
                {isLoading ? 'Loading...' : '🏠 Clock Out'}
              </button>
            </>
          ) : (
            <button
              onClick={handleStartSession}
              disabled={isLoading}
              className={cn(
                'px-6 py-3 rounded-lg font-semibold text-sm transition-all',
                'bg-emerald-600 hover:bg-emerald-700 text-white',
                isLoading && 'opacity-50 cursor-not-allowed'
              )}
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Loading
                </span>
              ) : (
                '🟢 Clock In'
              )}
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}
