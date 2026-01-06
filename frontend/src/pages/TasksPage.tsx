// ============================================
// TIME TRACKER - TASKS PAGE
// ============================================
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, Button, Input, Modal, LoadingOverlay, Select } from '../components/common';
import { TaskEstimationCard } from '../components/ai';
import { tasksApi, projectsApi } from '../api/client';
import { formatDate, cn } from '../utils/helpers';
import { useFeatureEnabled } from '../hooks/useAIFeatures';
import type { Task, TaskCreate, TaskStatus, Project } from '../types';

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
  const [filterProject, setFilterProject] = useState<number | ''>('');
  const [filterStatus, setFilterStatus] = useState<TaskStatus | ''>('');

  // AI Feature flag
  const { data: taskEstimationEnabled } = useFeatureEnabled('ai_task_estimation');

  // Fetch tasks
  const { data: tasksData, isLoading } = useQuery({
    queryKey: ['tasks', filterProject, filterStatus],
    queryFn: () =>
      tasksApi.getAll({
        project_id: filterProject || undefined,
        status: filterStatus || undefined,
      }),
  });

  // Fetch projects for filter
  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.getAll({ include_archived: false }),
  });

  const tasks = tasksData?.items || [];
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
    mutationFn: ({ id, data }: { id: number; data: Partial<Task> }) =>
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
            projectId={filterProject || undefined}
            compact={false}
          />
        </div>
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

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as TaskStatus | '')}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
            className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
            </svg>
          </button>
          <button
            onClick={onDelete}
            className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

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
  const [error, setError] = useState<string | null>(null);

  // Reset form when modal opens/closes or task changes
  React.useEffect(() => {
    if (task) {
      setName(task.name);
      setDescription(task.description || '');
      setProjectId(task.project_id);
      setStatus(task.status);
    } else {
      setName('');
      setDescription('');
      setProjectId(projects[0]?.id || '');
      setStatus('TODO');
    }
    setError(null);
  }, [task, isOpen, projects]);

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
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Project <span className="text-red-500">*</span>
          </label>
          <select
            value={projectId}
            onChange={(e) => setProjectId(Number(e.target.value))}
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
