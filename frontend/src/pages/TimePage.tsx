// ============================================
// TIME TRACKER - TIME ENTRIES PAGE
// With Manual Entry Creation (TASK-026)
// With AI Suggestions Integration
// With NLP Chat Interface
// ============================================
import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card, Button, Modal, LoadingOverlay, Input } from '../components/common';
import { TimerWidget } from '../components/time/TimerWidget';
import { LongTimerBanner } from '../components/time/LongTimerBanner';
import { EditEntryModal } from '../components/time/EditEntryModal';
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
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const [showModal, setShowModal] = useState(false);
  const [showManualModal, setShowManualModal] = useState(false);
  const [editingEntry, setEditingEntry] = useState<TimeEntry | null>(null);
  const [filterProject, setFilterProject] = useState<number | ''>('');
  const [showChatInterface, setShowChatInterface] = useState(false);
  const [filterDateRange, setFilterDateRange] = useState<string>('all');
  const [customStartDate, setCustomStartDate] = useState<string>('');
  const [customEndDate, setCustomEndDate] = useState<string>('');

  // Calculate date range for filtering
  // Helper to format date as YYYY-MM-DD in local timezone (not UTC)
  const formatLocalDate = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const getDateRange = (): { start_date?: string; end_date?: string } => {
    const today = new Date();
    
    switch (filterDateRange) {
      case 'today':
        return { 
          start_date: formatLocalDate(today),
          end_date: formatLocalDate(today)
        };
      case 'week': {
        const weekAgo = new Date(today);
        weekAgo.setDate(today.getDate() - 7);
        return { 
          start_date: formatLocalDate(weekAgo),
          end_date: formatLocalDate(today)
        };
      }
      case 'month': {
        const monthAgo = new Date(today);
        monthAgo.setMonth(today.getMonth() - 1);
        return { 
          start_date: formatLocalDate(monthAgo),
          end_date: formatLocalDate(today)
        };
      }
      case 'custom':
        return {
          start_date: customStartDate || undefined,
          end_date: customEndDate || undefined
        };
      default:
        return {};
    }
  };

  // AI Feature flags
  const { data: nlpEnabled } = useFeatureEnabled('ai_nlp_entry');
  
  // Auto-show chat interface when navigating with ?ai=chat parameter
  useEffect(() => {
    if (searchParams.get('ai') === 'chat' && nlpEnabled) {
      setShowChatInterface(true);
    }
  }, [searchParams, nlpEnabled]);

  // Fetch time entries
  const dateRange = getDateRange();
  const { data: entriesData, isLoading } = useQuery({
    queryKey: ['time-entries', filterProject, filterDateRange, customStartDate, customEndDate],
    queryFn: () =>
      timeEntriesApi.getAll({
        project_id: filterProject || undefined,
        start_date: dateRange.start_date,
        end_date: dateRange.end_date,
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
        title: t('time.entryCreated'),
        message: t('time.entryCreatedMsg', { duration: formatDuration(entry.duration_seconds) }),
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: t('time.failedToCreate'),
        message: t('common.tryAgain'),
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
        title: t('time.entryDeleted'),
        message: t('time.entryDeletedMsg'),
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: t('time.failedToDelete'),
        message: t('time.couldNotDelete'),
      });
    },
  });

  // Edit-modal save handler (PATCH /api/time/entries/{id} via EditEntryModal).
  const handleEditSaved = () => {
    queryClient.invalidateQueries({ queryKey: ['time-entries'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    addNotification({
      type: 'success',
      title: t('time.entryUpdated'),
      message: t('time.entryUpdatedMsg'),
    });
  };

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
    return <LoadingOverlay message={t('time.loadingEntries')} />;
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('time.title')}</h1>
          <p className="text-gray-500">{t('time.subtitle')}</p>
        </div>
        <Button onClick={() => setShowManualModal(true)}>
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          {t('time.addManualEntry')}
        </Button>
      </div>

      {/* Timer widget */}
      <LongTimerBanner />
      <TimerWidget />

      {/* NLP Chat Interface */}
      {nlpEnabled && (
        <Card className="bg-gradient-to-r from-purple-50 to-blue-50 border-purple-200">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">✨</span>
              <h3 className="font-semibold text-gray-800">{t('time.quickEntryWithAI')}</h3>
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
              placeholder={t('time.nlpPlaceholder')}
              onEntryCreated={() => {
                queryClient.invalidateQueries({ queryKey: ['time-entries'] });
                queryClient.invalidateQueries({ queryKey: ['dashboard'] });
                addNotification({
                  type: 'success',
                title: t('time.entryCreated'),
                message: t('time.entryCreatedViaAI'),
                });
              }}
            />
          ) : (
            <p className="text-sm text-gray-600">
              {t('time.nlpHint')}
            </p>
          )}
        </Card>
      )}

      {/* Filters */}
      <Card padding="sm">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('time.filterProject')}</label>
            <select
              value={filterProject}
              onChange={(e) => setFilterProject(e.target.value ? Number(e.target.value) : '')}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">{t('time.allProjects')}</option>
              {projects.map((project: Project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('time.filterDateRange')}</label>
            <select
              value={filterDateRange}
              onChange={(e) => setFilterDateRange(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">{t('time.allTime')}</option>
              <option value="today">{t('time.todayFilter')}</option>
              <option value="week">{t('time.last7Days')}</option>
              <option value="month">{t('time.last30Days')}</option>
              <option value="custom">{t('time.customRange')}</option>
            </select>
          </div>

          {filterDateRange === 'custom' && (
            <>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t('time.startDate')}</label>
                <input
                  type="date"
                  value={customStartDate}
                  onChange={(e) => setCustomStartDate(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t('time.endDate')}</label>
                <input
                  type="date"
                  value={customEndDate}
                  onChange={(e) => setCustomEndDate(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </>
          )}
        </div>
      </Card>

      {/* Time entries list */}
      {Object.keys(entriesByDate).length === 0 ? (
        <Card className="text-center py-12">
          <svg className="mx-auto w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-gray-900">{t('time.noEntries')}</h3>
          <p className="mt-2 text-gray-500">{t('time.noEntriesHint')}</p>
          <Button className="mt-4" onClick={() => setShowManualModal(true)}>
            {t('time.addManualEntry')}
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
                    {t('time.total')}: {formatDuration(totalSeconds)}
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

      {/* Edit Modal — PATCH /api/time/entries/{id} */}
      <EditEntryModal
        isOpen={showModal}
        entry={editingEntry}
        onClose={() => {
          setShowModal(false);
          setEditingEntry(null);
        }}
        onSaved={handleEditSaved}
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
  const { t } = useTranslation();
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
                {entry.description || t('time.noDescription')}
              </p>
              {entry.is_running && (
                <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded-full animate-pulse">
                  {t('time.running')}
                </span>
              )}
              {entry.is_manual && (
                <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                  {t('time.manual')}
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

// Manual Entry Modal Component (TASK-026)
interface ManualEntryModalProps {
  isOpen: boolean;
  onClose: () => void;
  projects: Project[];
  onSubmit: (data: TimeEntryCreate) => void;
  isLoading: boolean;
}

function ManualEntryModal({ isOpen, onClose, projects, onSubmit, isLoading }: ManualEntryModalProps) {
  const { t } = useTranslation();
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
      setError(t('time.endAfterStart'));
      return;
    }

    if (!projectId) {
      setError(t('time.selectProjectError'));
      return;
    }

    onSubmit({
      description: description || t('time.manualEntryDefault'),
      project_id: projectId as number,
      task_id: taskId ? (taskId as number) : undefined,
      start_time: startDateTime.toISOString(),
      end_time: endDateTime.toISOString(),
      is_manual: true,
    });
  };

  const durationSeconds = calculateDuration();

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={t('time.addManualTimeEntry')} size="md">
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
            <span>✨</span> {t('time.showAISuggestions')}
          </button>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('time.descriptionLabel')}
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onFocus={() => suggestionsEnabled && !projectId && setShowSuggestions(true)}
            placeholder={t('time.manualDescPlaceholder')}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('time.projectLabel')} <span className="text-red-500">*</span>
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
            <option value="">{t('time.selectProject')}</option>
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
              {t('time.taskLabel')}
            </label>
            <select
              value={taskId}
              onChange={(e) => setTaskId(e.target.value ? Number(e.target.value) : '')}
              className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">{t('time.noTask')}</option>
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
            {t('time.dateLabel')} <span className="text-red-500">*</span>
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
              {t('time.startTimeLabel')} <span className="text-red-500">*</span>
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
              {t('time.endTimeLabel')} <span className="text-red-500">*</span>
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
              {t('time.durationLabel')} <span className="font-semibold">{formatDuration(durationSeconds)}</span>
            </p>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" isLoading={isLoading}>
            {t('time.addEntry')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
