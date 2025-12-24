// ============================================
// TIME TRACKER - TIMER WIDGET COMPONENT
// ============================================
import { useEffect, useState, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from '../common';
import { useTimerStore } from '../../stores/timerStore';
import { projectsApi, tasksApi } from '../../api/client';
import { formatTime, formatDuration, cn } from '../../utils/helpers';
import { useNotifications } from '../../hooks/useNotifications';
import type { Project, Task } from '../../types';

export function TimerWidget() {
  const {
    currentEntry,
    isRunning,
    elapsedSeconds,
    isLoading,
    error,
    fetchTimer,
    startTimer,
    stopTimer,
    updateElapsed,
    clearError,
  } = useTimerStore();

  const { addNotification } = useNotifications();

  const [description, setDescription] = useState('');
  const [selectedProject, setSelectedProject] = useState<number | undefined>();
  const [selectedTask, setSelectedTask] = useState<number | undefined>();
  const [localError, setLocalError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  // Fetch timer status on mount AND when component becomes visible
  useEffect(() => {
    console.log('[TimerWidget] Component mounted, fetching timer...');
    fetchTimer();
    
    // Also fetch on window focus (in case user has multiple tabs)
    const handleFocus = () => {
      console.log('[TimerWidget] Window focused, refreshing timer...');
      fetchTimer();
    };
    window.addEventListener('focus', handleFocus);
    
    return () => {
      window.removeEventListener('focus', handleFocus);
    };
  }, [fetchTimer]);

  // Update elapsed time every second when timer is running
  useEffect(() => {
    if (isRunning) {
      intervalRef.current = setInterval(() => {
        updateElapsed();
      }, 1000);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isRunning, updateElapsed]);

  // Sync description from current entry
  useEffect(() => {
    if (currentEntry) {
      setDescription(currentEntry.description || '');
      setSelectedProject(currentEntry.project_id || undefined);
      setSelectedTask(currentEntry.task_id || undefined);
    }
  }, [currentEntry]);

  const handleStartStop = async () => {
    setLocalError(null);

    if (isRunning) {
      const stoppedEntry = await stopTimer();
      if (stoppedEntry) {
        const projectName = projects.find((p: Project) => p.id === stoppedEntry.project_id)?.name || 'Unknown';
        addNotification({
          type: 'success',
          title: 'Timer Stopped',
          message: `${formatDuration(stoppedEntry.duration_seconds || elapsedSeconds)} logged to ${projectName}`,
        });
      }
      setDescription('');
      setSelectedProject(undefined);
      setSelectedTask(undefined);
    } else {
      // Validate project is selected
      if (!selectedProject) {
        setLocalError('Please select a project before starting the timer');
        return;
      }

      try {
        await startTimer({
          description: description || undefined,
          project_id: selectedProject,
          task_id: selectedTask,
        });
        const projectName = projects.find((p: Project) => p.id === selectedProject)?.name || 'Unknown';
        addNotification({
          type: 'info',
          title: 'Timer Started',
          message: `Tracking time for ${projectName}`,
          duration: 3000,
        });
      } catch (err) {
        addNotification({
          type: 'error',
          title: 'Failed to Start Timer',
          message: 'Please try again',
        });
      }
    }
  };

  const displayError = localError || error;

  return (
    <Card className="bg-gradient-to-r from-blue-600 to-blue-700 text-white">
      {displayError && (
        <div className="mb-4 bg-red-500/20 border border-red-300/50 text-white px-4 py-2 rounded-lg text-sm flex items-center justify-between">
          <span>{displayError}</span>
          <button
            onClick={() => {
              setLocalError(null);
              clearError();
            }}
            className="ml-2 hover:text-red-200"
          >
            ×
          </button>
        </div>
      )}

      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        {/* Timer display */}
        <div className="flex items-center gap-4">
          <div
            className={cn(
              'w-4 h-4 rounded-full',
              isRunning ? 'bg-green-400 animate-pulse' : 'bg-gray-400'
            )}
          />
          <span className="text-4xl font-mono font-bold tracking-wider">
            {formatTime(elapsedSeconds)}
          </span>
        </div>

        {/* Description input */}
        <div className="flex-1 max-w-md">
          <input
            type="text"
            placeholder="What are you working on?"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isRunning}
            className="w-full px-4 py-2 bg-white/20 border border-white/30 rounded-lg text-white placeholder-white/60 focus:outline-none focus:ring-2 focus:ring-white/50 disabled:opacity-50"
          />
        </div>

        {/* Project/Task selectors */}
        <div className="flex gap-2">
          <select
            value={selectedProject || ''}
            onChange={(e) => {
              setSelectedProject(e.target.value ? Number(e.target.value) : undefined);
              setSelectedTask(undefined);
              setLocalError(null);
            }}
            disabled={isRunning}
            className={cn(
              "px-3 py-2 bg-white/20 border rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-white/50 disabled:opacity-50",
              !selectedProject && !isRunning ? "border-yellow-300/70" : "border-white/30"
            )}
          >
            <option value="">Select project *</option>
            {projects.map((project: Project) => (
              <option key={project.id} value={project.id} className="text-gray-900">
                {project.name}
              </option>
            ))}
          </select>

          {selectedProject && (
            <select
              value={selectedTask || ''}
              onChange={(e) => setSelectedTask(e.target.value ? Number(e.target.value) : undefined)}
              disabled={isRunning}
              className="px-3 py-2 bg-white/20 border border-white/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-white/50 disabled:opacity-50"
            >
              <option value="">No task</option>
              {tasks.map((task: Task) => (
                <option key={task.id} value={task.id} className="text-gray-900">
                  {task.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Start/Stop button */}
        <button
          onClick={handleStartStop}
          disabled={isLoading}
          className={cn(
            'px-6 py-3 rounded-lg font-semibold text-sm transition-all',
            isRunning
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-white hover:bg-gray-100 text-blue-600',
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
          ) : isRunning ? (
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="4" width="4" height="16" rx="1" />
                <rect x="14" y="4" width="4" height="16" rx="1" />
              </svg>
              Stop
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
              Start
            </span>
          )}
        </button>
      </div>
    </Card>
  );
}
