// ============================================
// TIME TRACKER - TASKS PAGE
// ============================================
import React, { useState } from 'react';
import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  keepPreviousData,
} from '@tanstack/react-query';
import { Card, Button, Input, Modal, LoadingOverlay } from '../components/common';
import { TaskEstimationCard } from '../components/ai';
import { ProjectSelect } from '../components/projects/ProjectSelect';
import { TeamChip } from '../components/teams/TeamChip';
import { TeamMultiSelect } from '../components/teams/TeamMultiSelect';
import { TaskTeamWarning } from '../components/tasks/TaskTeamWarning';
import { tasksApi, projectsApi, teamsApi } from '../api/client';
import { formatDate, cn } from '../utils/helpers';
import { useFeatureEnabled } from '../hooks/useAIFeatures';
import type { Task, TaskCreate, TaskUpdate, TaskStatus, Project } from '../types';

const STATUS_OPTIONS = [
  { value: 'TODO', label: 'To Do' },
  { value: 'IN_PROGRESS', label: 'In Progress' },
  { value: 'DONE', label: 'Done' },
];

const STATUS_COLORS: Record<TaskStatus, string> = {
  TODO: 'bg-gray-100 text-gray-800',
  IN_PROGRESS: 'bg-blue-100 text-blue-800',
  DONE: 'bg-green-100 text-green-800',
};

export function TasksPage() {
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [filterProject, setFilterProject] = useState<number | null>(null);
  const [filterStatus, setFilterStatus] = useState<TaskStatus | ''>('');

  // AI Feature flag
  const { data: taskEstimationEnabled } = useFeatureEnabled('ai_task_estimation');

  // Fetch tasks — paginated via Load More.
  //
  // Mirrors the pagination-shadow fix shipped for TimePage entries
  // (PR #30) and ProjectsPage (PR #35): the server defaults to
  // page_size=20 and silently caps the list, so any project with
  // more than 20 tasks lost everything past the cutoff from the
  // main render. useInfiniteQuery with page_size=50 + a
  // "Showing X of Y" indicator + Load More keeps the full list
  // reachable. Filters (project/status) are part of the query key,
  // so flipping a filter cleanly refetches page 1 — we don't try to
  // preserve loaded pages across filter changes.
  const TASKS_PAGE_SIZE = 50;
  const {
    data: tasksData,
    isLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['tasks', 'paginated', filterProject, filterStatus],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      tasksApi.getAll({
        project_id: filterProject ?? undefined,
        status: filterStatus || undefined,
        page: pageParam as number,
        page_size: TASKS_PAGE_SIZE,
      }),
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce(
        (acc, p) => acc + (p.items?.length || 0),
        0
      );
      const total = lastPage?.total ?? 0;
      if (loaded >= total) return undefined;
      return allPages.length + 1;
    },
    // While a filter change is fetching the new first page, keep
    // the previous result rendered so the page doesn't flash a
    // full-screen loading overlay over the (still-mounted) filter
    // controls — that lets the user keep interacting with the
    // ProjectSelect / status dropdown without losing focus.
    placeholderData: keepPreviousData,
  });

  const tasks: Task[] = (tasksData?.pages ?? []).flatMap(
    (p) => p.items || []
  );
  const totalTasks = tasksData?.pages?.[0]?.total ?? tasks.length;

  // Fetch projects for the TaskModal's required-project picker.
  // The page's project filter uses <ProjectSelect> directly (it
  // owns its own paginated fetch via the shared
  // ACTIVE_PROJECTS_QUERY_KEY cache), so this list only needs to
  // cover the modal's <select>. We bump page_size to 100 — same
  // ceiling the typeahead uses — so the modal isn't silently
  // capped at 20 either.
  const { data: projectsData } = useQuery({
    queryKey: ['projects', 'active'],
    queryFn: () =>
      projectsApi.getAll({ include_archived: false, page_size: 100 }),
  });

  const projects = projectsData?.items || [];

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: TaskCreate) => tasksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setShowModal(false);
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: TaskUpdate }) =>
      tasksApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setShowModal(false);
      setEditingTask(null);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => tasksApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });

  // Status update mutation
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: TaskStatus }) =>
      tasksApi.update(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });

  const handleEdit = (task: Task) => {
    setEditingTask(task);
    setShowModal(true);
  };

  if (isLoading) {
    return <LoadingOverlay message="Loading tasks..." />;
  }

  // Group tasks by status
  const tasksByStatus = STATUS_OPTIONS.reduce(
    (acc, status) => {
      acc[status.value as TaskStatus] = tasks.filter(
        (task: Task) => task.status === status.value
      );
      return acc;
    },
    {} as Record<TaskStatus, Task[]>
  );

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tasks</h1>
          <p className="text-gray-500">Manage and track your tasks</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Task
        </Button>
      </div>

      {/* AI Task Estimation */}
      {taskEstimationEnabled && (
        <div className="bg-white rounded-xl shadow-sm border border-indigo-200 p-4 bg-gradient-to-r from-indigo-50 to-purple-50" role="region" aria-label="AI Task Time Estimation">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">🤖</span>
            <h3 className="font-semibold text-gray-800">AI Task Estimation</h3>
          </div>
          <p className="text-sm text-gray-600 mb-3">
            Get AI-powered time estimates for your tasks based on historical data and project patterns.
          </p>
          <TaskEstimationCard 
            projectId={filterProject ?? undefined}
            compact={false}
          />
        </div>
      )}

      {/* Filters */}
      <Card padding="sm">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="min-w-[14rem]">
            <ProjectSelect
              value={filterProject}
              onChange={setFilterProject}
              clearable
              clearLabel="All projects"
              placeholder="All projects"
              ariaLabel="Filter by project"
            />
          </div>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as TaskStatus | '')}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Filter by status"
          >
            <option value="">All Statuses</option>
            {STATUS_OPTIONS.map((status) => (
              <option key={status.value} value={status.value}>
                {status.label}
              </option>
            ))}
          </select>
        </div>
      </Card>

      {/* "Showing X of Y tasks" indicator. X is the number of tasks
          currently loaded across all fetched pages; Y is the
          server-reported total for the current filter set. The
          Load More button below advances to the next page until
          everything is loaded. */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500" data-testid="tasks-count">
          Showing {tasks.length} of {totalTasks} tasks
        </p>
      </div>

      {/* Kanban board */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {STATUS_OPTIONS.map((status) => (
          <div key={status.value} className="bg-gray-50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-700">{status.label}</h3>
              <span className="px-2 py-0.5 bg-gray-200 text-gray-600 rounded-full text-xs">
                {tasksByStatus[status.value as TaskStatus]?.length || 0}
              </span>
            </div>
            <div className="space-y-3">
              {tasksByStatus[status.value as TaskStatus]?.map((task: Task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  projects={projects}
                  onEdit={() => handleEdit(task)}
                  onDelete={() => deleteMutation.mutate(task.id)}
                  onStatusChange={(newStatus) =>
                    statusMutation.mutate({ id: task.id, status: newStatus })
                  }
                />
              ))}
              {(tasksByStatus[status.value as TaskStatus]?.length || 0) === 0 && (
                <p className="text-center text-sm text-gray-400 py-4">
                  No tasks
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Load More \u2014 server-side pagination via useInfiniteQuery.
          Hidden once everything is loaded; disabled while the next
          page is in flight. */}
      {hasNextPage && (
        <div className="flex justify-center pt-2">
          <Button
            variant="secondary"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
            data-testid="tasks-load-more"
          >
            {isFetchingNextPage ? 'Loading\u2026' : 'Load More'}
          </Button>
        </div>
      )}

      {/* Create/Edit Modal */}
      <TaskModal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setEditingTask(null);
        }}
        task={editingTask}
        projects={projects}
        onSubmit={(data) => {
          if (editingTask) {
            updateMutation.mutate({ id: editingTask.id, data });
          } else {
            createMutation.mutate(data as TaskCreate);
          }
        }}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />
    </div>
  );
}

// Task Card Component
interface TaskCardProps {
  task: Task;
  projects: Project[];
  onEdit: () => void;
  onDelete: () => void;
  onStatusChange: (status: TaskStatus) => void;
}

function TaskCard({ task, projects, onEdit, onDelete, onStatusChange }: TaskCardProps) {
  const project = projects.find((p) => p.id === task.project_id);

  return (
    <Card padding="sm" className="cursor-pointer hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <h4 className="font-medium text-gray-900 text-sm">{task.name}</h4>
        <div className="flex gap-1">
          <button
            onClick={onEdit}
            aria-label={`Edit task ${task.name}`}
            className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
            </svg>
          </button>
          <button
            onClick={onDelete}
            aria-label={`Delete task ${task.name}`}
            className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

      {!!task.teams?.length && (
        <div className="mt-2 flex flex-wrap gap-1">
          {task.teams.map((team) => (
            <TeamChip key={team.id} team={team} size="sm" />
          ))}
        </div>
      )}

      {task.description && (
        <p className="mt-2 text-xs text-gray-500 line-clamp-2">{task.description}</p>
      )}

      <div className="mt-3 flex items-center justify-between">
        {project && (
          <span className="inline-flex items-center gap-1 text-xs text-gray-500">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: project.color }}
            />
            {project.name}
          </span>
        )}

        <select
          value={task.status}
          onChange={(e) => onStatusChange(e.target.value as TaskStatus)}
          onClick={(e) => e.stopPropagation()}
          className={cn(
            'text-xs px-2 py-0.5 rounded-full border-0 cursor-pointer focus:ring-2 focus:ring-blue-500',
            STATUS_COLORS[task.status]
          )}
        >
          {STATUS_OPTIONS.map((status) => (
            <option key={status.value} value={status.value}>
              {status.label}
            </option>
          ))}
        </select>
      </div>
    </Card>
  );
}

// Task Modal Component
interface TaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  task: Task | null;
  projects: Project[];
  onSubmit: (data: Partial<TaskCreate>) => void;
  isLoading: boolean;
}

function TaskModal({ isOpen, onClose, task, projects, onSubmit, isLoading }: TaskModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [projectId, setProjectId] = useState<number | ''>('');
  const [status, setStatus] = useState<TaskStatus>('TODO');
  const [teamIds, setTeamIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { data: teamsData } = useQuery({
    queryKey: ['teams', 'task-modal'],
    queryFn: () => teamsApi.getAll({ page: 1, page_size: 100 }),
    enabled: isOpen,
  });

  const allTeams = teamsData?.items ?? [];

  // Reset form when modal opens/closes or task changes
  React.useEffect(() => {
    if (task) {
      setName(task.name);
      setDescription(task.description || '');
      setProjectId(task.project_id);
      setStatus(task.status);
      setTeamIds(task.teams?.map((team) => team.id) ?? []);
    } else {
      setName('');
      setDescription('');
      setProjectId(projects[0]?.id || '');
      setStatus('TODO');
      setTeamIds([]);
    }
    setError(null);
  }, [task, isOpen, projects]);

  const selectedProject =
    projectId === '' ? null : projects.find((project) => project.id === projectId) ?? null;
  const projectTeamIds = selectedProject
    ? new Set<number>([
        selectedProject.team_id,
        ...(selectedProject.team_associations || []).map((association) => association.team_id),
      ])
    : new Set<number>();

  const offProjectTeamNames = teamIds
    .filter((id) => !projectTeamIds.has(id))
    .map((id) => allTeams.find((team) => team.id === id)?.name)
    .filter((name): name is string => Boolean(name));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!projectId) {
      setError('Please select a project');
      return;
    }
    
    onSubmit({
      name,
      description: description || undefined,
      project_id: projectId as number,
      status,
      team_ids: teamIds,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={task ? 'Edit Task' : 'New Task'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}
        
        <Input
          label="Task Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="What needs to be done?"
          required
        />

        <div>
          <label htmlFor="task-project-select" className="block text-sm font-medium text-gray-700 mb-1">
            Project <span className="text-red-500">*</span>
          </label>
          <ProjectSelect
            id="task-project-select"
            value={projectId === '' ? null : projectId}
            onChange={(value) => setProjectId(value ?? '')}
            projects={projects}
            placeholder="Select a project"
            ariaLabel="Project"
            required
            inputClassName="block w-full border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Status
          </label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as TaskStatus)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Task description..."
            rows={3}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Teams</label>
          <TeamMultiSelect selectedIds={teamIds} onChange={setTeamIds} />
          <div className="mt-2">
            <TaskTeamWarning offProjectTeamNames={offProjectTeamNames} />
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isLoading}>
            {task ? 'Save Changes' : 'Create Task'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
