// ============================================
// TIME TRACKER - TIMER WIDGET COMPONENT
// ============================================
import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
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

  // Fetch projects
  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.getAll({ include_archived: false }),
  });

  // Fetch tasks for selected project
  const { data: tasksData, isPending: isTasksPending } = useQuery({
    queryKey: ['tasks', selectedProject],
    queryFn: () => tasksApi.getAll({ project_id: selectedProject }),
    enabled: !!selectedProject,
  });

  const projects = projectsData?.items || [];
  const tasks = useMemo(() => tasksData?.items || [], [tasksData]);

  // Detect tasks with duplicate names in the current dropdown so we
  // can suffix a Basecamp-sourced disambiguator (due date / created
  // / position). Unique names render as-is.
  const nameCounts = useMemo(() => {
    return tasks.reduce<Record<string, number>>((acc, t) => {
      acc[t.name] = (acc[t.name] || 0) + 1;
      return acc;
    }, {});
  }, [tasks]);

  // Sort tasks within each duplicate-name group chronologically
  // (due_on DESC, then created_at DESC, then position ASC). Tasks
  // missing all three sort to the end of their group. Unique-named
  // tasks keep their original position; each duplicate group is
  // emitted at the slot of the first occurrence in the original
  // order so the most-recent same-named task takes that slot.
  const sortedTasks = useMemo(() => {
    if (tasks.length === 0) return tasks;

    type Group = { firstIndex: number; items: Task[] };
    const groups = new Map<string, Group>();
    tasks.forEach((t, i) => {
      const existing = groups.get(t.name);
      if (existing) {
        existing.items.push(t);
      } else {
        groups.set(t.name, { firstIndex: i, items: [t] });
      }
    });

    const cmpStrDesc = (a: string | null | undefined, b: string | null | undefined): number => {
      const av = a || '';
      const bv = b || '';
      if (av && bv) {
        if (av === bv) return 0;
        return av < bv ? 1 : -1;
      }
      if (av) return -1;
      if (bv) return 1;
      return 0;
    };

    for (const g of groups.values()) {
      if (g.items.length <= 1) continue;
      g.items.sort((a, b) => {
        const dueCmp = cmpStrDesc(a.basecamp_due_on, b.basecamp_due_on);
        if (dueCmp !== 0) return dueCmp;
        const createdCmp = cmpStrDesc(a.basecamp_todo_created_at, b.basecamp_todo_created_at);
        if (createdCmp !== 0) return createdCmp;
        const aPos = a.basecamp_todo_position;
        const bPos = b.basecamp_todo_position;
        if (aPos != null && bPos != null) return aPos - bPos;
        if (aPos != null) return -1;
        if (bPos != null) return 1;
        return 0;
      });
    }

    return Array.from(groups.values())
      .sort((a, b) => a.firstIndex - b.firstIndex)
      .flatMap((g) => g.items);
  }, [tasks]);

  // Within each duplicate-name group, detect Mon D collisions across
  // different years so we can render the year only when needed.
  const collidingDueKeys = useMemo(() => {
    const counts = new Map<string, number>();
    tasks.forEach((t) => {
      if ((nameCounts[t.name] || 0) <= 1) return;
      if (!t.basecamp_due_on) return;
      const md = new Date(t.basecamp_due_on).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
      const key = `${t.name}|${md}`;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    const collisions = new Set<string>();
    counts.forEach((c, k) => {
      if (c > 1) collisions.add(k);
    });
    return collisions;
  }, [tasks, nameCounts]);

  const formatTaskLabel = (task: Task): string => {
    const isDuplicate = (nameCounts[task.name] || 0) > 1;
    if (!isDuplicate) return task.name;

    if (task.basecamp_due_on) {
      const d = new Date(task.basecamp_due_on);
      const md = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      const key = `${task.name}|${md}`;
      if (collidingDueKeys.has(key)) {
        const withYear = d.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        });
        return `${task.name} (Due ${withYear})`;
      }
      return `${task.name} (Due ${md})`;
    }
    if (task.basecamp_todo_created_at) {
      const d = new Date(task.basecamp_todo_created_at);
      const formatted = d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
      return `${task.name} (${formatted})`;
    }
    if (task.basecamp_todo_position != null) {
      return `${task.name} (#${task.basecamp_todo_position})`;
    }
    return task.name;
  };

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
          <select
            value={selectedProject || ''}
            onChange={(e) => {
              handleProjectChange(e.target.value ? Number(e.target.value) : undefined);
            }}
            disabled={controlsDisabled}
            className={cn(
              "px-3 py-2 bg-white/20 border rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-white/50",
              controlsDisabled && "opacity-50 cursor-not-allowed",
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
              onChange={(e) => {
                handleTaskChange(e.target.value ? Number(e.target.value) : undefined);
              }}
              disabled={controlsDisabled}
              className={cn(
                "px-3 py-2 bg-white/20 border border-white/30 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-white/50",
                controlsDisabled && "opacity-50 cursor-not-allowed"
              )}
            >
              <option value="">
                {isTasksPending
                  ? 'Loading tasks…'
                  : tasks.length === 0
                    ? 'No tasks for this project'
                    : 'No task'}
              </option>
              {sortedTasks.map((task: Task) => (
                <option key={task.id} value={task.id} className="text-gray-900">
                  {formatTaskLabel(task)}
                </option>
              ))}
            </select>
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
