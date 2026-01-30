// ============================================
// TIME TRACKER - SESSION WIDGET COMPONENT
// Combined Clock In + Task Timer - starts both together
// ============================================
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from '../common';
import { useSessionStore, formatDuration, getSessionStatusInfo } from '../../stores/sessionStore';
import { useTimerStore } from '../../stores/timerStore';
import { projectsApi, tasksApi } from '../../api/client';
import { cn } from '../../utils/helpers';
import { useNotifications } from '../../hooks/useNotifications';
import { BreakControls } from './BreakControls';
import { MeetingControls } from './MeetingControls';
import type { Project, Task } from '../../types';

export function SessionWidget() {
  const {
    currentSession,
    activeBreak,
    activeMeeting,
    isLoading: sessionLoading,
    error: sessionError,
    sessionElapsedSeconds,
    breakElapsedSeconds,
    meetingElapsedSeconds,
    fetchCurrentSession,
    startSession,
    endSession,
    updateElapsedTimes,
    clearError,
  } = useSessionStore();

  const {
    isRunning: timerRunning,
    elapsedSeconds: taskElapsedSeconds,
    startTimer,
    stopTimer,
    fetchTimer,
    updateElapsed,
  } = useTimerStore();

  const { addNotification } = useNotifications();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clock In form state
  const [showClockInForm, setShowClockInForm] = useState(false);
  const [description, setDescription] = useState('');
  const [selectedProject, setSelectedProject] = useState<number | undefined>();
  const [selectedTask, setSelectedTask] = useState<number | undefined>();
  const [formError, setFormError] = useState<string | null>(null);

  // Fetch projects
  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.getAll({ include_archived: false }),
  });

  // Fetch tasks for selected project
  const { data: tasksData } = useQuery({
    queryKey: ['tasks', selectedProject],
    queryFn: () => tasksApi.getAll({ project_id: selectedProject }),
    enabled: !!selectedProject,
  });

  const projects = projectsData?.items || [];
  const tasks = tasksData?.items || [];

  // Fetch session and timer status on mount
  useEffect(() => {
    fetchCurrentSession();
    fetchTimer();

    const handleFocus = () => {
      fetchCurrentSession();
      fetchTimer();
    };
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [fetchCurrentSession, fetchTimer]);

  // Update elapsed times every second when session is active
  useEffect(() => {
    if (currentSession && currentSession.status !== 'completed') {
      intervalRef.current = setInterval(() => {
        updateElapsedTimes();
        updateElapsed();
      }, 1000);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [currentSession, updateElapsedTimes, updateElapsed]);

  // Combined Clock In - starts session AND task timer
  const handleClockIn = async () => {
    if (!selectedProject) {
      setFormError('Please select a project');
      return;
    }

    setFormError(null);
    try {
      // Start session first
      await startSession();
      
      // Then start task timer
      await startTimer({
        description: description || undefined,
        project_id: selectedProject,
        task_id: selectedTask,
      });

      const projectName = projects.find((p: Project) => p.id === selectedProject)?.name || 'your project';
      addNotification({
        type: 'success',
        title: 'Clocked In!',
        message: `Session started. Now tracking time on ${projectName}`,
        duration: 3000,
      });

      // Reset form
      setShowClockInForm(false);
      setDescription('');
      setSelectedProject(undefined);
      setSelectedTask(undefined);
    } catch {
      addNotification({
        type: 'error',
        title: 'Failed to Clock In',
        message: 'Please try again',
      });
    }
  };

  // Clock Out - stops task timer AND ends session
  const handleClockOut = async () => {
    try {
      // Stop task timer first if running
      if (timerRunning) {
        await stopTimer();
      }
      
      // Then end session
      await endSession();
      
      addNotification({
        type: 'success',
        title: 'Clocked Out!',
        message: `Great work! You logged ${formatDuration(sessionElapsedSeconds)} today.`,
      });
    } catch {
      addNotification({
        type: 'error',
        title: 'Failed to Clock Out',
        message: 'Please try again',
      });
    }
  };

  const statusInfo = getSessionStatusInfo(currentSession?.status);
  const isOnBreakOrMeeting = !!activeBreak || !!activeMeeting;
  const isLoading = sessionLoading;

  // Not clocked in - show Clock In button or form
  if (!currentSession) {
    return (
      <Card className="bg-gray-100">
        {(sessionError || formError) && (
          <div className="mb-4 bg-red-100 border border-red-300 text-red-700 px-4 py-2 rounded-lg text-sm flex items-center justify-between">
            <span>{sessionError || formError}</span>
            <button onClick={() => { clearError(); setFormError(null); }} className="ml-2 hover:text-red-900">×</button>
          </div>
        )}

        {!showClockInForm ? (
          // Simple Clock In button
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="text-2xl">⚪</div>
              <div>
                <div className="text-sm font-medium text-gray-500">Not Clocked In</div>
                <div className="text-3xl font-mono font-bold text-gray-400">00:00:00</div>
              </div>
            </div>
            <button
              onClick={() => setShowClockInForm(true)}
              disabled={isLoading}
              className={cn(
                'px-6 py-3 rounded-lg font-semibold text-sm transition-all',
                'bg-emerald-600 hover:bg-emerald-700 text-white',
                isLoading && 'opacity-50 cursor-not-allowed'
              )}
            >
              🟢 Clock In
            </button>
          </div>
        ) : (
          // Clock In form with project/task selection
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-700">🟢 Clock In - What will you work on?</h3>
              <button
                onClick={() => setShowClockInForm(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Project *</label>
                <select
                  value={selectedProject || ''}
                  onChange={(e) => {
                    setSelectedProject(e.target.value ? Number(e.target.value) : undefined);
                    setSelectedTask(undefined);
                    setFormError(null);
                  }}
                  className={cn(
                    "w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500",
                    !selectedProject ? "border-amber-400" : "border-gray-300"
                  )}
                >
                  <option value="">Select a project...</option>
                  {projects.map((project: Project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </div>

              {selectedProject && (
                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-1">Task (optional)</label>
                  <select
                    value={selectedTask || ''}
                    onChange={(e) => setSelectedTask(e.target.value ? Number(e.target.value) : undefined)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  >
                    <option value="">No specific task</option>
                    {tasks.map((task: Task) => (
                      <option key={task.id} value={task.id}>
                        {task.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">What are you working on? (optional)</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of your task..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowClockInForm(false)}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleClockIn}
                disabled={isLoading || !selectedProject}
                className={cn(
                  'px-6 py-2 rounded-lg font-semibold text-sm transition-all',
                  'bg-emerald-600 hover:bg-emerald-700 text-white',
                  (isLoading || !selectedProject) && 'opacity-50 cursor-not-allowed'
                )}
              >
                {isLoading ? 'Starting...' : '🟢 Start Working'}
              </button>
            </div>
          </div>
        )}
      </Card>
    );
  }

  // Clocked in - show session status with task timer
  return (
    <Card className={cn(
      'transition-colors duration-300',
      currentSession.status === 'active' && 'bg-gradient-to-r from-emerald-600 to-emerald-700 text-white',
      currentSession.status === 'break' && 'bg-gradient-to-r from-amber-500 to-amber-600 text-white',
      currentSession.status === 'meeting' && 'bg-gradient-to-r from-blue-500 to-blue-600 text-white'
    )}>
      {sessionError && (
        <div className="mb-4 bg-red-500/20 border border-red-300/50 text-white px-4 py-2 rounded-lg text-sm flex items-center justify-between">
          <span>{sessionError}</span>
          <button onClick={clearError} className="ml-2 hover:text-red-200">×</button>
        </div>
      )}

      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        {/* Session timer (global) */}
        <div className="flex items-center gap-4">
          <div className="text-2xl">{statusInfo.icon}</div>
          <div>
            <div className="text-xs text-white/70">{statusInfo.label} - Session Time</div>
            <div className="text-3xl font-mono font-bold tracking-wider">
              {formatDuration(sessionElapsedSeconds)}
            </div>
          </div>
        </div>

        {/* Task timer */}
        {timerRunning && (
          <div className="flex items-center gap-4">
            <div className="text-2xl">⏱️</div>
            <div>
              <div className="text-xs text-white/70">Current Task</div>
              <div className="text-2xl font-mono font-semibold text-emerald-200">
                {formatDuration(taskElapsedSeconds)}
              </div>
            </div>
          </div>
        )}

        {/* Break/Meeting sub-timers */}
        <div className="flex gap-4">
          {activeBreak && (
            <div className="text-center">
              <div className="text-xs text-white/70">Break</div>
              <div className="text-lg font-mono text-amber-200">{formatDuration(breakElapsedSeconds)}</div>
            </div>
          )}
          {activeMeeting && (
            <div className="text-center">
              <div className="text-xs text-white/70">Meeting</div>
              <div className="text-lg font-mono text-blue-200">{formatDuration(meetingElapsedSeconds)}</div>
            </div>
          )}
          <div className="text-center">
            <div className="text-xs text-white/70">Breaks</div>
            <div className="text-sm font-mono">{formatDuration(currentSession.total_break_seconds)}</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-white/70">Meetings</div>
            <div className="text-sm font-mono">{formatDuration(currentSession.total_meeting_seconds)}</div>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {!isOnBreakOrMeeting && (
            <>
              <BreakControls />
              <MeetingControls />
            </>
          )}
          {activeBreak && <BreakControls />}
          {activeMeeting && <MeetingControls />}

          <button
            onClick={handleClockOut}
            disabled={isLoading}
            className={cn(
              'px-4 py-2 rounded-lg font-semibold text-sm transition-all',
              'bg-white/20 hover:bg-white/30 text-white border border-white/30',
              isLoading && 'opacity-50 cursor-not-allowed'
            )}
          >
            {isLoading ? 'Loading...' : '🏠 Clock Out'}
          </button>
        </div>
      </div>
    </Card>
  );
}
