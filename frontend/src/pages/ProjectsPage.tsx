// ============================================
// TIME TRACKER - PROJECTS PAGE
// ============================================
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardHeader, Button, Input, Modal, LoadingOverlay } from '../components/common';
import { projectsApi, teamsApi } from '../api/client';
import { formatDate, cn, generateRandomColor } from '../utils/helpers';
import { useAuth } from '../hooks/useAuth';
import { useNotifications } from '../hooks/useNotifications';
import { useFeatureEnabled } from '../hooks/useAIFeatures';
import ProjectHealthCard from '../components/ai/ProjectHealthCard';
import type { Project, ProjectCreate, Team } from '../types';

export function ProjectsPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { addNotification } = useNotifications();
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  const { data: projectHealthEnabled } = useFeatureEnabled('project_health');
  const [selectedProjectForHealth, setSelectedProjectForHealth] = useState<Project | null>(null);

  const [showModal, setShowModal] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{ type: 'archive' | 'restore' | 'delete'; project: Project } | null>(null);

  // Fetch projects
  // Fetch projects - always include archived so we can filter client-side
  const { data: projectsData, isLoading } = useQuery({
    queryKey: ['projects', 'all'],
    queryFn: () => projectsApi.getAll({ include_archived: true }),
  });

  // Fetch teams for dropdown
  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsApi.getAll(),
  });

  // Filter projects based on showArchived toggle
  const allProjects = projectsData?.items || [];
  const projects = showArchived 
    ? allProjects.filter(p => p.is_archived)
    : allProjects.filter(p => !p.is_archived);
  const teams = teamsData?.items || [];

  // Create mutation (admin only)
  const createMutation = useMutation({
    mutationFn: (data: ProjectCreate) => projectsApi.create(data),
    onSuccess: (newProject) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setShowModal(false);
      addNotification({
        type: 'success',
        title: 'Project Created',
        message: `"${newProject.name}" has been created successfully`,
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: 'Failed to Create Project',
        message: 'Please try again',
      });
    },
  });

  // Update mutation (admin only)
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Project> }) =>
      projectsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setShowModal(false);
      setEditingProject(null);
      addNotification({
        type: 'success',
        title: 'Project Updated',
        message: 'Changes have been saved',
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: 'Failed to Update Project',
        message: 'Please try again',
      });
    },
  });

  // Archive mutation (admin only)
  const archiveMutation = useMutation({
    mutationFn: (id: number) => projectsApi.update(id, { is_archived: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      addNotification({
        type: 'info',
        title: 'Project Archived',
        message: 'The project has been archived',
      });
    },
  });

  // Restore mutation (admin only)
  const restoreMutation = useMutation({
    mutationFn: (id: number) => projectsApi.restore(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      addNotification({
        type: 'success',
        title: 'Project Restored',
        message: 'The project is now active',
      });
    },
  });

  // Delete mutation (admin only)
  const deleteMutation = useMutation({
    mutationFn: (id: number) => projectsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      addNotification({
        type: 'success',
        title: 'Project Deleted',
        message: 'The project has been permanently deleted',
      });
    },
    onError: () => {
      addNotification({
        type: 'error',
        title: 'Failed to Delete',
        message: 'Could not delete the project. It may have time entries.',
      });
    },
  });

  const handleEdit = (project: Project) => {
    if (!isAdmin) return;
    setEditingProject(project);
    setShowModal(true);
  };

  const handleConfirmAction = () => {
    if (!confirmAction) return;
    if (confirmAction.type === 'archive') {
      archiveMutation.mutate(confirmAction.project.id);
    } else if (confirmAction.type === 'restore') {
      restoreMutation.mutate(confirmAction.project.id);
    } else if (confirmAction.type === 'delete') {
      deleteMutation.mutate(confirmAction.project.id);
    }
    setConfirmAction(null);
  };

  if (isLoading) {
    return <LoadingOverlay message="Loading projects..." />;
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="text-gray-500">
            {isAdmin ? 'Manage your projects and organize your work' : 'View available projects'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={showArchived ? 'primary' : 'secondary'}
            onClick={() => setShowArchived(!showArchived)}
          >
            {showArchived ? 'Show Active' : 'Show Archived'}
          </Button>
          {isAdmin && (
            <Button onClick={() => setShowModal(true)}>
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Project
            </Button>
          )}
        </div>
      </div>

      {/* Projects grid */}
      {projects.length === 0 ? (
        <Card className="text-center py-12">
          <svg className="mx-auto w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-gray-900">No projects yet</h3>
          <p className="mt-2 text-gray-500">
            {isAdmin ? 'Create your first project to start tracking time.' : 'No projects available. Contact your admin.'}
          </p>
          {isAdmin && (
            <Button className="mt-4" onClick={() => setShowModal(true)}>
              Create Project
            </Button>
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project: Project) => (
            <ProjectCard
              key={project.id}
              project={project}
              isAdmin={isAdmin}
              showHealthButton={projectHealthEnabled}
              onViewHealth={() => setSelectedProjectForHealth(project)}
              onEdit={() => handleEdit(project)}
              onArchive={() => setConfirmAction({ type: 'archive', project })}
              onRestore={() => setConfirmAction({ type: 'restore', project })}
              onDelete={() => setConfirmAction({ type: 'delete', project })}
            />
          ))}
        </div>
      )}

      {/* AI Project Health Panel */}
      {projectHealthEnabled && selectedProjectForHealth && (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              AI Health Analysis: {selectedProjectForHealth.name}
            </h2>
            <button 
              onClick={() => setSelectedProjectForHealth(null)}
              className="text-gray-400 hover:text-gray-600 p-1"
              aria-label="Close health panel"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <ProjectHealthCard 
            projectId={selectedProjectForHealth.id} 
            projectName={selectedProjectForHealth.name}
            includeTeamMetrics={isAdmin}
          />
        </div>
      )}

      {/* Confirmation Modal */}
      <Modal
        isOpen={!!confirmAction}
        onClose={() => setConfirmAction(null)}
        title={
          confirmAction?.type === 'archive' ? 'Archive Project' : 
          confirmAction?.type === 'restore' ? 'Restore Project' : 
          'Delete Project'
        }
      >
        <div className="space-y-4">
          <p className="text-gray-600">
            {confirmAction?.type === 'archive' 
              ? `Are you sure you want to archive "${confirmAction?.project.name}"? Archived projects won't appear in active project lists.`
              : confirmAction?.type === 'restore'
              ? `Are you sure you want to restore "${confirmAction?.project.name}"? It will become active again.`
              : `Are you sure you want to permanently delete "${confirmAction?.project.name}"? This action cannot be undone.`
            }
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirmAction(null)}>
              Cancel
            </Button>
            <Button 
              variant={confirmAction?.type === 'restore' ? 'primary' : 'danger'}
              onClick={handleConfirmAction}
              isLoading={archiveMutation.isPending || restoreMutation.isPending || deleteMutation.isPending}
            >
              {confirmAction?.type === 'archive' ? 'Archive' : confirmAction?.type === 'restore' ? 'Restore' : 'Delete'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Create/Edit Modal - Admin only */}
      {isAdmin && (
        <ProjectModal
          isOpen={showModal}
          onClose={() => {
            setShowModal(false);
            setEditingProject(null);
          }}
          project={editingProject}
          teams={teams}
          onSubmit={(data) => {
            if (editingProject) {
              updateMutation.mutate({ id: editingProject.id, data });
            } else {
              createMutation.mutate(data as ProjectCreate);
            }
          }}
          isLoading={createMutation.isPending || updateMutation.isPending}
        />
      )}
    </div>
  );
}

// Project Card Component
interface ProjectCardProps {
  project: Project;
  isAdmin: boolean;
  showHealthButton?: boolean;
  onViewHealth?: () => void;
  onEdit: () => void;
  onArchive: () => void;
  onRestore: () => void;
  onDelete: () => void;
}

function ProjectCard({ project, isAdmin, showHealthButton, onViewHealth, onEdit, onArchive, onRestore, onDelete }: ProjectCardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-4 h-4 rounded-full"
            style={{ backgroundColor: project.color }}
          />
          <div>
            <h3 className="font-semibold text-gray-900">{project.name}</h3>
            {project.description && (
              <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                {project.description}
              </p>
            )}
          </div>
        </div>
        {isAdmin && (
          <div className="flex gap-1">
            <button
              onClick={onEdit}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100"
              title="Edit project"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            </button>
            {project.is_archived ? (
              <button
                onClick={onRestore}
                className="p-1.5 rounded-lg text-green-400 hover:text-green-600 hover:bg-green-50"
                title="Restore project"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            ) : (
              <button
                onClick={onArchive}
                className="p-1.5 rounded-lg text-gray-400 hover:text-orange-600 hover:bg-orange-50"
                title="Archive project"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                </svg>
              </button>
            )}
            <button
              onClick={onDelete}
              className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50"
              title="Delete project"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        )}
      </div>
      <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between text-sm text-gray-500">
        <span>Created {formatDate(project.created_at)}</span>
        <div className="flex items-center gap-2">
          {showHealthButton && (
            <button
              onClick={onViewHealth}
              className="px-2 py-1 text-xs bg-purple-50 text-purple-600 hover:bg-purple-100 rounded-md flex items-center gap-1 transition-colors"
              title="View AI health analysis"
              aria-label={`View AI health analysis for ${project.name}`}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              AI Health
            </button>
          )}
          {project.is_archived && (
            <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">
              Archived
            </span>
          )}
        </div>
      </div>
    </Card>
  );
}

// Project Modal Component
interface ProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  project: Project | null;
  teams: Team[];
  onSubmit: (data: Partial<ProjectCreate>) => void;
  isLoading: boolean;
}

function ProjectModal({ isOpen, onClose, project, teams, onSubmit, isLoading }: ProjectModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [teamId, setTeamId] = useState<number | ''>('');
  const [color, setColor] = useState('#3B82F6');

  // Reset form when modal opens/closes or project changes
  React.useEffect(() => {
    if (project) {
      setName(project.name);
      setDescription(project.description || '');
      setTeamId(project.team_id);
      setColor(project.color);
    } else {
      setName('');
      setDescription('');
      setTeamId(teams[0]?.id || '');
      setColor(generateRandomColor());
    }
  }, [project, isOpen, teams]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      name,
      description: description || undefined,
      team_id: teamId as number,
      color,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={project ? 'Edit Project' : 'New Project'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Project Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="My Project"
          required
        />

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Team
          </label>
          <select
            value={teamId}
            onChange={(e) => setTeamId(Number(e.target.value))}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            required
          >
            <option value="">Select a team</option>
            {teams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name}
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
            placeholder="Project description..."
            rows={3}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Color
          </label>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              className="w-10 h-10 rounded cursor-pointer border border-gray-300"
            />
            <input
              type="text"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isLoading}>
            {project ? 'Save Changes' : 'Create Project'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
