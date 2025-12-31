// ============================================
// TIME TRACKER - TIME ENTRIES PAGE
// With Manual Entry Creation (TASK-026)
// With AI Suggestions Integration
// With NLP Chat Interface
// ============================================
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Button, Modal, LoadingOverlay, Input } from '../components/common';
import { TimerWidget } from '../components/time/TimerWidget';
import { SuggestionDropdown, ChatInterface } from '../components/ai';
import { timeEntriesApi, projectsApi, tasksApi } from '../api/client';
import { formatDuration, formatDate, formatTimeOnly, cn } from '../utils/helpers';
import { useAuth } from '../hooks/useAuth';
import { useNotifications } from '../hooks/useNotifications';
import { useFeatureEnabled } from '../hooks/useAIFeatures';
import type { TimeEntry, TimeEntryCreate, Project, Task } from '../types';

export function TimePage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { addNotification } = useNotifications();
  const [showModal, setShowModal] = useState(false);
  const [showManualModal, setShowManualModal] = useState(false);
  const [editingEntry, setEditingEntry] = useState<TimeEntry | null>(null);
  const [filterProject, setFilterProject] = useState<number | ''>('');
  const [showChatInterface, setShowChatInterface] = useState(false);

  // AI Feature flags
  const { data: nlpEnabled } = useFeatureEnabled('nlp_time_entry');

  // Fetch time entries
  const { data: entriesData, isLoading } = useQuery({
    queryKey: ['time-entries', filterProject],
    queryFn: () =>
      timeEntriesApi.getAll({
        project_id: filterProject || undefined,
        size: 50,
      }),
  });

  // Fetch projects for filter
  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.getAll({ include_archived: false }),
  });

  const entries = entriesData?.items || [];
  const projects = projectsData?.items || [];

  // Create mutation for manual entries
  const createMutation = useMutation({
    mutationFn: (data: TimeEntryCreate) => timeEntriesApi.create(data),
    onSuccess: (entry) => {
      queryClient.invalidateQueries({ queryKey: ['time-entries'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setShowManualModal(false);
      addNotification({
        type: 'success',
        title: 'Entry Created',
        message: `${formatDuration(entry.duration_seconds)} logged successfully`,
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: 'Failed to Create Entry',
        message: 'Please try again',
      });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => timeEntriesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['time-entries'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      addNotification({
        type: 'info',
        title: 'Entry Deleted',
        message: 'Time entry has been removed',
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: 'Failed to Delete',
        message: 'Could not delete the entry',
      });
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<TimeEntry> }) =>
      timeEntriesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['time-entries'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setShowModal(false);
      setEditingEntry(null);
      addNotification({
        type: 'success',
        title: 'Entry Updated',
        message: 'Changes have been saved',
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: 'Failed to Update',
        message: 'Could not save changes',
      });
    },
  });

  // Group entries by date
  const entriesByDate = entries.reduce(
    (acc: Record<string, TimeEntry[]>, entry: TimeEntry) => {
      const date = formatDate(entry.start_time);
      if (!acc[date]) acc[date] = [];
      acc[date].push(entry);
      return acc;
    },
    {}
  );

  const handleEdit = (entry: TimeEntry) => {
    setEditingEntry(entry);
    setShowModal(true);
  };

  if (isLoading) {
    return <LoadingOverlay message="Loading time entries..." />;
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Time Tracker</h1>
          <p className="text-gray-500">Track your work and view your time entries</p>
        </div>
        <Button onClick={() => setShowManualModal(true)}>
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Manual Entry
        </Button>
      </div>

      {/* Timer widget */}
      <TimerWidget />

      {/* NLP Chat Interface */}
      {nlpEnabled && (
        <Card className="bg-gradient-to-r from-purple-50 to-blue-50 border-purple-200">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">✨</span>
              <h3 className="font-semibold text-gray-800">Quick Entry with AI</h3>
            </div>
            <button
              onClick={() => setShowChatInterface(!showChatInterface)}
              className="text-sm text-purple-600 hover:text-purple-800"
            >
              {showChatInterface ? 'Hide' : 'Show'}
            </button>
          </div>
          {showChatInterface ? (
            <ChatInterface 
              placeholder='Try: "2 hours yesterday on Project Alpha fixing bugs"'
              onEntryCreated={() => {
                queryClient.invalidateQueries({ queryKey: ['time-entries'] });
                queryClient.invalidateQueries({ queryKey: ['dashboard'] });
                addNotification({
                  type: 'success',
                  title: 'Entry Created',
                  message: 'Time entry created via AI assistant',
                });
              }}
            />
          ) : (
            <p className="text-sm text-gray-600">
              Type naturally to create time entries, e.g., "3 hours on marketing yesterday"
            </p>
          )}
        </Card>
      )}

      {/* Filters */}
      <Card padding="sm">
        <div className="flex flex-wrap gap-4">
          <select
            value={filterProject}
            onChange={(e) => setFilterProject(e.target.value ? Number(e.target.value) : '')}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Projects</option>
            {projects.map((project: Project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>
      </Card>

      {/* Time entries list */}
      {Object.keys(entriesByDate).length === 0 ? (
        <Card className="text-center py-12">
          <svg className="mx-auto w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-gray-900">No time entries yet</h3>
          <p className="mt-2 text-gray-500">Start the timer or add a manual entry to begin tracking.</p>
          <Button className="mt-4" onClick={() => setShowManualModal(true)}>
            Add Manual Entry
          </Button>
        </Card>
      ) : (
        <div className="space-y-6">
          {Object.entries(entriesByDate).map(([date, dateEntries]) => {
            const totalSeconds = dateEntries.reduce(
              (acc: number, entry: TimeEntry) => acc + entry.duration_seconds,
              0
            );

            return (
              <div key={date}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-gray-900">{date}</h3>
                  <span className="text-sm text-gray-500">
                    Total: {formatDuration(totalSeconds)}
                  </span>
                </div>
                <div className="space-y-2">
                  {dateEntries.map((entry: TimeEntry) => (
                    <TimeEntryCard
                      key={entry.id}
                      entry={entry}
                      projects={projects}
                      onEdit={() => handleEdit(entry)}
                      onDelete={() => deleteMutation.mutate(entry.id)}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit Modal */}
      <TimeEntryModal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setEditingEntry(null);
        }}
        entry={editingEntry}
        projects={projects}
        onSubmit={(data) => {
          if (editingEntry) {
            updateMutation.mutate({ id: editingEntry.id, data });
          }
        }}
        isLoading={updateMutation.isPending}
      />

      {/* Manual Entry Modal */}
      <ManualEntryModal
        isOpen={showManualModal}
        onClose={() => setShowManualModal(false)}
        projects={projects}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
      />
    </div>
  );
}

// Time Entry Card Component
interface TimeEntryCardProps {
  entry: TimeEntry;
  projects: Project[];
  onEdit: () => void;
  onDelete: () => void;
}

function TimeEntryCard({ entry, projects, onEdit, onDelete }: TimeEntryCardProps) {
  const project = projects.find((p) => p.id === entry.project_id);

  return (
    <Card padding="sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 flex-1 min-w-0">
          {/* Project color indicator */}
          <div
            className="w-1 h-12 rounded-full flex-shrink-0"
            style={{ backgroundColor: project?.color || '#9CA3AF' }}
          />

          {/* Entry details */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="font-medium text-gray-900 truncate">
                {entry.description || 'No description'}
              </p>
              {entry.is_running && (
                <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded-full animate-pulse">
                  Running
                </span>
              )}
              {entry.is_manual && (
                <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                  Manual
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
              {project && (
                <span className="flex items-center gap-1">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                  {project.name}
                </span>
              )}
              <span>
                {formatTimeOnly(entry.start_time)}
                {entry.end_time && ' - ' + formatTimeOnly(entry.end_time)}
              </span>
            </div>
          </div>
        </div>

        {/* Duration and actions */}
        <div className="flex items-center gap-4">
          <span className="font-mono font-semibold text-gray-900">
            {formatDuration(entry.duration_seconds)}
          </span>
          <div className="flex gap-1">
            <button
              onClick={onEdit}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            </button>
            <button
              onClick={onDelete}
              className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </Card>
  );
}

// Time Entry Modal Component (for editing)
interface TimeEntryModalProps {
  isOpen: boolean;
  onClose: () => void;
  entry: TimeEntry | null;
  projects: Project[];
  onSubmit: (data: Partial<TimeEntryCreate>) => void;
  isLoading: boolean;
}

function TimeEntryModal({ isOpen, onClose, entry, projects, onSubmit, isLoading }: TimeEntryModalProps) {
  const [description, setDescription] = useState('');
  const [projectId, setProjectId] = useState<number | ''>('');

  // Fetch tasks for selected project
  const { data: tasksData } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => tasksApi.getAll({ project_id: projectId as number }),
    enabled: !!projectId,
  });

  const tasks = tasksData?.items || [];
  const [taskId, setTaskId] = useState<number | ''>('');

  // Reset form when modal opens or entry changes
  React.useEffect(() => {
    if (entry) {
      setDescription(entry.description || '');
      setProjectId(entry.project_id || '');
      setTaskId(entry.task_id || '');
    } else {
      setDescription('');
      setProjectId('');
      setTaskId('');
    }
  }, [entry, isOpen]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      description: description || undefined,
      project_id: projectId || undefined,
      task_id: taskId || undefined,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Edit Time Entry">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What were you working on?"
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Project
          </label>
          <select
            value={projectId}
            onChange={(e) => {
              setProjectId(e.target.value ? Number(e.target.value) : '');
              setTaskId('');
            }}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">No project</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>

        {projectId && tasks.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Task
            </label>
            <select
              value={taskId}
              onChange={(e) => setTaskId(e.target.value ? Number(e.target.value) : '')}
              className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">No task</option>
              {tasks.map((task: Task) => (
                <option key={task.id} value={task.id}>
                  {task.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isLoading}>
            Save Changes
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// Manual Entry Modal Component (TASK-026)
interface ManualEntryModalProps {
  isOpen: boolean;
  onClose: () => void;
  projects: Project[];
  onSubmit: (data: TimeEntryCreate) => void;
  isLoading: boolean;
}

function ManualEntryModal({ isOpen, onClose, projects, onSubmit, isLoading }: ManualEntryModalProps) {
  const [description, setDescription] = useState('');
  const [projectId, setProjectId] = useState<number | ''>('');
  const [taskId, setTaskId] = useState<number | ''>('');
  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('17:00');
  const [error, setError] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Check if AI suggestions are enabled
  const { data: suggestionsEnabled } = useFeatureEnabled('ai_suggestions');

  // Fetch tasks for selected project
  const { data: tasksData } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => tasksApi.getAll({ project_id: projectId as number }),
    enabled: !!projectId,
  });

  const tasks = tasksData?.items || [];

  // Reset form when modal closes
  React.useEffect(() => {
    if (!isOpen) {
      setDescription('');
      setProjectId('');
      setTaskId('');
      setDate(new Date().toISOString().split('T')[0]);
      setStartTime('09:00');
      setEndTime('17:00');
      setError('');
      setShowSuggestions(false);
    } else if (suggestionsEnabled) {
      // Show suggestions when modal opens if enabled
      setShowSuggestions(true);
    }
  }, [isOpen, suggestionsEnabled]);

  // Handle suggestion selection
  const handleSuggestionSelect = (suggestion: {
    projectId: number;
    projectName: string;
    taskId?: number | null;
    taskName?: string | null;
    description?: string;
  }) => {
    setProjectId(suggestion.projectId);
    if (suggestion.taskId) {
      setTaskId(suggestion.taskId);
    }
    if (suggestion.description) {
      setDescription(suggestion.description);
    }
    setShowSuggestions(false);
  };

  // Reset form when modal closes
  React.useEffect(() => {
    if (!isOpen) {
      setDescription('');
      setProjectId('');
      setTaskId('');
      setDate(new Date().toISOString().split('T')[0]);
      setStartTime('09:00');
      setEndTime('17:00');
      setError('');
    }
  }, [isOpen]);

  const calculateDuration = () => {
    const start = new Date(date + 'T' + startTime);
    const end = new Date(date + 'T' + endTime);
    const diffMs = end.getTime() - start.getTime();
    return Math.max(0, Math.floor(diffMs / 1000));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const startDateTime = new Date(date + 'T' + startTime);
    const endDateTime = new Date(date + 'T' + endTime);

    if (endDateTime <= startDateTime) {
      setError('End time must be after start time');
      return;
    }

    if (!projectId) {
      setError('Please select a project');
      return;
    }

    onSubmit({
      description: description || 'Manual entry',
      project_id: projectId as number,
      task_id: taskId ? (taskId as number) : undefined,
      start_time: startDateTime.toISOString(),
      end_time: endDateTime.toISOString(),
      is_manual: true,
    });
  };

  const durationSeconds = calculateDuration();

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Manual Time Entry" size="md">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* AI Suggestions Panel */}
        {suggestionsEnabled && showSuggestions && !projectId && (
          <div className="relative">
            <SuggestionDropdown
              onSelect={handleSuggestionSelect}
              partialDescription={description}
              isOpen={showSuggestions}
              onClose={() => setShowSuggestions(false)}
              autoFetch={true}
              className="relative static shadow-none border-blue-200 bg-blue-50"
            />
          </div>
        )}

        {/* Toggle suggestions button if hidden */}
        {suggestionsEnabled && !showSuggestions && !projectId && (
          <button
            type="button"
            onClick={() => setShowSuggestions(true)}
            className="w-full p-2 text-sm text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors flex items-center justify-center gap-2"
          >
            <span>✨</span> Show AI Suggestions
          </button>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onFocus={() => suggestionsEnabled && !projectId && setShowSuggestions(true)}
            placeholder="What did you work on?"
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Project <span className="text-red-500">*</span>
          </label>
          <select
            value={projectId}
            onChange={(e) => {
              setProjectId(e.target.value ? Number(e.target.value) : '');
              setTaskId('');
              setShowSuggestions(false);
            }}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            required
          >
            <option value="">Select a project</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>

        {projectId && tasks.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Task
            </label>
            <select
              value={taskId}
              onChange={(e) => setTaskId(e.target.value ? Number(e.target.value) : '')}
              className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">No task</option>
              {tasks.map((task: Task) => (
                <option key={task.id} value={task.id}>
                  {task.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Date <span className="text-red-500">*</span>
          </label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Start Time <span className="text-red-500">*</span>
            </label>
            <input
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              End Time <span className="text-red-500">*</span>
            </label>
            <input
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            />
          </div>
        </div>

        {durationSeconds > 0 && (
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-700">
              Duration: <span className="font-semibold">{formatDuration(durationSeconds)}</span>
            </p>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isLoading}>
            Add Entry
          </Button>
        </div>
      </form>
    </Modal>
  );
}
