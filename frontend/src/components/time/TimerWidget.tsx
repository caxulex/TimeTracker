// ============================================
// TIME TRACKER - TIMER WIDGET COMPONENT
// ============================================
import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from '../common';
import { ProjectSelect } from '../projects/ProjectSelect';
import { TaskSelect, TASKS_QUERY_KEY } from '../tasks/TaskSelect';
import { useTimerStore } from '../../stores/timerStore';
import { projectsApi, tasksApi } from '../../api/client';
import { formatTime, formatDuration, cn } from '../../utils/helpers';
import { useNotifications } from '../../hooks/useNotifications';
import type { Project, Task } from '../../types';

export function TimerWidget() {
  const {
    currentEntry,
    isRunning,
    isPaused,
    elapsedSeconds,
    isLoading,
    error,
    fetchTimer,
    startTimer,
    stopTimer,
    switchTimer,
    updateElapsed,
    clearError,
  } = useTimerStore();

  // Controls are disabled during meeting/break (isPaused) to prevent state corruption
  const controlsDisabled = isLoading || isPaused;

  const { addNotification } = useNotifications();

  const [description, setDescription] = useState('');
  const [selectedProject, setSelectedProject] = useState<number | undefined>();
  const [selectedTask, setSelectedTask] = useState<number | undefined>();
  const [localError, setLocalError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch projects.
  //
  // page_size=100 caps at the backend's `le=100` ceiling. Without
  // this override the server's default (page_size=20) was kicking in
  // and silently dropping any project beyond the 20 most recent —
  // the same pagination-shadow bug that hit PR #30 (entry list) and
  // PR #33 (entry-card labels). The ProjectSelect typeahead below
  // makes the consequence less catastrophic — at the current ceiling
  // (~100 active projects/team) a missing project would now be a
  // hard cap, not just a silent disappearance.
  const { data: projectsData } = useQuery({
    queryKey: ['projects', 'active'],
    queryFn: () =>
      projectsApi.getAll({ include_archived: false, page_size: 100 }),
  });

  // Fetch tasks for selected project. Kept in sync with TaskSelect's
  // own query (same key, same page_size) so the two share the React
  // Query cache instead of double-fetching. The local copy is used
  // for notification labels on start/switch.
  const { data: tasksData } = useQuery({
    queryKey: TASKS_QUERY_KEY(selectedProject ?? null),
    queryFn: () =>
      tasksApi.getAll({ project_id: selectedProject as number, page_size: 100 }),
    enabled: !!selectedProject,
  });

  const projects = useMemo(() => projectsData?.items || [], [projectsData]);
  const tasks = useMemo(() => tasksData?.items || [], [tasksData]);

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

  // Handle task switch: called when project or task changes while timer is running
  const handleTaskSwitch = useCallback(async (newProjectId: number, newTaskId?: number, newDescription?: string) => {
    if (!isRunning || isLoading) return;
    
    try {
      await switchTimer({
        project_id: newProjectId,
        task_id: newTaskId,
        description: newDescription || description || undefined,
      });
      
      const projectName = projects.find((p: Project) => p.id === newProjectId)?.name || 'Unknown';
      const taskName = newTaskId ? tasks.find((t: Task) => t.id === newTaskId)?.name : null;
      addNotification({
        type: 'info',
        title: 'Switched Task',
        message: `Now tracking: ${projectName}${taskName ? ` → ${taskName}` : ''}`,
        duration: 3000,
      });
    } catch {
      addNotification({
        type: 'error',
        title: 'Failed to Switch Task',
        message: 'Please try again',
      });
    }
  }, [isRunning, isLoading, switchTimer, description, projects, tasks, addNotification]);

  const handleProjectChange = (newProjectId: number | undefined) => {
    setSelectedProject(newProjectId);
    setSelectedTask(undefined);
    setLocalError(null);

    // If timer is running and a valid project was selected, switch task
    if (isRunning && newProjectId) {
      handleTaskSwitch(newProjectId, undefined, description);
    }
  };

  const handleTaskChange = (newTaskId: number | undefined) => {
    setSelectedTask(newTaskId);

    // If timer is running, switch to the new task within the same project
    if (isRunning && selectedProject) {
      handleTaskSwitch(selectedProject, newTaskId, description);
    }
  };

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
      } catch {
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
              isPaused ? 'bg-yellow-400 animate-pulse' :
              isRunning ? 'bg-green-400 animate-pulse' : 'bg-gray-400'
            )}
          />
          <div className="flex flex-col">
            <span className="text-4xl font-mono font-bold tracking-wider">
              {formatTime(elapsedSeconds)}
            </span>
            {isPaused && (
              <span className="text-xs text-yellow-200 font-medium">
                ⏸ Paused — In meeting or break
              </span>
            )}
          </div>
        </div>

        {/* Description input */}
        <div className="flex-1 max-w-md">
          <input
            type="text"
            placeholder="What are you working on?"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-4 py-2 bg-white/20 border border-white/30 rounded-lg text-white placeholder-white/60 focus:outline-none focus:ring-2 focus:ring-white/50"
          />
        </div>

        {/* Project/Task selectors — disabled during meeting/break to prevent state corruption */}
        <div className="flex gap-2">
          <ProjectSelect
            value={selectedProject ?? null}
            onChange={(id) =>
              handleProjectChange(id === null ? undefined : id)
            }
            disabled={controlsDisabled}
            placeholder="Select project *"
            projects={projects}
            className="min-w-[12rem]"
            // The timer card is a dark blue gradient; recolor the
            // field so the typed text and the focus ring stay
            // legible. The dropdown panel itself stays on its own
            // white surface (kept inside ProjectSelect).
            inputClassName={cn(
              'bg-white/20 text-white placeholder-white/60 border focus:ring-white/50 focus:border-white/50',
              !selectedProject && !isRunning
                ? 'border-yellow-300/70'
                : 'border-white/30'
            )}
          />

          {selectedProject && (
            <TaskSelect
              projectId={selectedProject}
              value={selectedTask ?? null}
              onChange={(id) =>
                handleTaskChange(id === null ? undefined : id)
              }
              disabled={controlsDisabled}
              placeholder="Select task"
              className="min-w-[10rem]"
              inputClassName="bg-white/20 text-white placeholder-white/60 border border-white/30 focus:ring-white/50 focus:border-white/50"
            />
          )}
        </div>

        {/* Start/Stop button */}
        <button
          onClick={handleStartStop}
          disabled={controlsDisabled}
          className={cn(
            'px-6 py-3 rounded-lg font-semibold text-sm transition-all',
            isRunning
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-white hover:bg-gray-100 text-blue-600',
            controlsDisabled && 'opacity-50 cursor-not-allowed'
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
