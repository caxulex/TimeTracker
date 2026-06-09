import React, { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button, Input, Modal } from '../common';
import { projectsApi } from '../../api/client';
import { useDebounce } from '../../hooks/useDebounce';
import { useAddProjectToTeam, useRemoveProjectFromTeam, useTeamProjects } from '../../hooks/useApi';
import { useStaffNotifications } from '../../hooks/useStaffNotifications';
import { cn } from '../../utils/helpers';
import type { Project, TeamProject } from '../../types';

interface TeamProjectsSectionProps {
  teamId: number;
  teamName: string;
  isArchivedTeam?: boolean;
}

export function TeamProjectsSection({ teamId, teamName, isArchivedTeam = false }: TeamProjectsSectionProps) {
  const notifications = useStaffNotifications();
  const { data: teamProjectsData, isLoading, error } = useTeamProjects(teamId);
  const addProjectMutation = useAddProjectToTeam();
  const removeProjectMutation = useRemoveProjectFromTeam();

  const [isAddOpen, setIsAddOpen] = useState(false);
  const [projectSearch, setProjectSearch] = useState('');
  const [search, setSearch] = useState('');
  const [pendingProject, setPendingProject] = useState<Project | null>(null);
  const [pendingRemoval, setPendingRemoval] = useState<TeamProject | null>(null);
  const [projects, setProjects] = useState<TeamProject[]>([]);

  useEffect(() => {
    setProjects(teamProjectsData ?? []);
  }, [teamProjectsData]);

  useEffect(() => {
    setProjectSearch('');
  }, [teamId]);

  const debouncedProjectSearch = useDebounce(projectSearch, 250).trim();
  const debouncedSearch = useDebounce(search, 250).trim();
  const isProjectSearchActive = debouncedProjectSearch.length > 0;
  const associatedIds = useMemo(() => new Set(projects.map((project) => project.id)), [projects]);
  const visibleProjects = useMemo(() => {
    if (!isProjectSearchActive) return projects;
    const query = debouncedProjectSearch.toLowerCase();
    return projects.filter((project) => project.name.toLowerCase().includes(query));
  }, [projects, debouncedProjectSearch, isProjectSearchActive]);

  const { data: projectResults, isFetching: isSearching } = useQuery({
    queryKey: ['projects', 'team-assignment-search', teamId, debouncedSearch],
    queryFn: () => projectsApi.getAll({ include_archived: false, page: 1, page_size: 100, search: debouncedSearch || undefined }),
    enabled: isAddOpen,
    staleTime: 15_000,
  });

  const availableProjects = (projectResults?.items ?? []).filter((project) => !associatedIds.has(project.id));

  const teamProjects = projects;
  const projectCountLabel = isProjectSearchActive
    ? `Projects (${visibleProjects.length} of ${teamProjects.length})`
    : `Projects (${teamProjects.length})`;

  const openAddModal = () => {
    setSearch('');
    setPendingProject(null);
    setIsAddOpen(true);
  };

  const closeAddModal = () => {
    setIsAddOpen(false);
    setSearch('');
    setPendingProject(null);
  };

  const handleConfirmAdd = () => {
    if (!pendingProject) return;
    addProjectMutation.mutate(
      { projectId: pendingProject.id, teamId },
      {
        onSuccess: () => {
          const optimisticProject: TeamProject = {
            id: pendingProject.id,
            name: pendingProject.name,
            color: pendingProject.color,
            is_archived: pendingProject.is_archived,
            primary_team_id: teamId,
            primary_team_name: teamName,
            association_type: 'additional',
          };
          setProjects((current) =>
            current.some((project) => project.id === pendingProject.id)
              ? current
              : [...current, optimisticProject]
          );
          notifications.notifySuccess('Project Added', `"${pendingProject.name}" is now available to ${teamName}.`);
          closeAddModal();
        },
        onError: (error: unknown) => {
          const message = error instanceof Error ? error.message : 'Failed to add project';
          notifications.notifyError('Add Project Failed', message);
        },
      }
    );
  };

  const handleConfirmRemove = () => {
    if (!pendingRemoval) return;
    removeProjectMutation.mutate(
      { projectId: pendingRemoval.id, teamId },
      {
        onSuccess: () => {
          setProjects((current) => current.filter((project) => project.id !== pendingRemoval.id));
          notifications.notifySuccess('Project Removed', `"${pendingRemoval.name}" was removed from ${teamName}.`);
          setPendingRemoval(null);
        },
        onError: (error: unknown) => {
          const message = error instanceof Error ? error.message : 'Failed to remove project';
          notifications.notifyError('Remove Project Failed', message);
        },
      }
    );
  };

  const removeButtonDisabled = isArchivedTeam || removeProjectMutation.isPending;

  if (error) {
    return (
      <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        Failed to load projects for this team.
      </div>
    );
  }

  return (
    <div className="mt-6 rounded-2xl border border-gray-200 bg-white/90 p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold text-gray-900">{projectCountLabel}</h3>
        {!isArchivedTeam && (
          <Button size="sm" variant="secondary" onClick={openAddModal}>
            + Add Project
          </Button>
        )}
      </div>

      <div className="mt-3 flex items-start gap-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
        <svg className="mt-0.5 h-4 w-4 shrink-0 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M12 20a8 8 0 100-16 8 8 0 000 16z" />
        </svg>
        <p>Changes here affect all team members, not just you.</p>
      </div>

      <div className="mt-4">
        <Input
          label="Search projects"
          value={projectSearch}
          onChange={(event) => setProjectSearch(event.target.value)}
          placeholder="Search by project name"
          data-testid="team-projects-search-input"
        />
      </div>

      <div className="mt-4 space-y-2">
        {isLoading ? (
          <div className="py-6 text-sm text-gray-500">Loading projects...</div>
        ) : teamProjects.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-sm text-gray-600">
            {isProjectSearchActive ? 'No projects match' : 'No projects yet. Click + Add Project to get started.'}
          </div>
        ) : visibleProjects.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-sm text-gray-600">
            No projects match
          </div>
        ) : (
          visibleProjects.map((project) => (
            <div key={project.id} className="flex items-start justify-between gap-3 rounded-lg border border-gray-200 bg-white px-3 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full border border-gray-300" style={{ backgroundColor: project.color }} />
                  <span className="truncate font-medium text-gray-900">{project.name}</span>
                </div>
                {project.primary_team_id !== teamId && (
                  <p className="mt-1 text-xs text-gray-500">
                    Primary: {project.primary_team_name || 'Unknown'}
                  </p>
                )}
              </div>
              {!isArchivedTeam && (
                <button
                  type="button"
                  onClick={() => setPendingRemoval(project)}
                  className={cn('rounded px-2 py-1 text-sm text-gray-500 hover:text-red-600', removeButtonDisabled ? 'opacity-50' : '')}
                  aria-label={`Remove ${project.name} from team`}
                  disabled={removeButtonDisabled}
                >
                  X
                </button>
              )}
            </div>
          ))
        )}
      </div>

      <Modal isOpen={isAddOpen} onClose={closeAddModal} title={`Add Project to ${teamName}`} size="lg">
        {pendingProject ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700">
              Add <strong>{pendingProject.name}</strong> to <strong>{teamName}</strong>? All members will be able to log time on this project.
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setPendingProject(null)}>
                Cancel
              </Button>
              <Button type="button" onClick={handleConfirmAdd} isLoading={addProjectMutation.isPending}>
                Add
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Input
              label="Search projects"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search projects..."
              autoFocus
            />
            <div className="max-h-80 overflow-y-auto rounded-lg border border-gray-200">
              {isSearching ? (
                <div className="p-4 text-sm text-gray-500">Searching...</div>
              ) : availableProjects.length === 0 ? (
                <div className="p-4 text-sm text-gray-500">No projects found.</div>
              ) : (
                availableProjects.map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    onClick={() => setPendingProject(project)}
                    className="flex w-full items-center gap-3 border-b border-gray-100 px-4 py-3 text-left hover:bg-gray-50 last:border-b-0"
                  >
                    <span className="h-2.5 w-2.5 rounded-full border border-gray-300" style={{ backgroundColor: project.color }} />
                    <div className="min-w-0">
                      <p className="truncate font-medium text-gray-900">{project.name}</p>
                      {project.is_archived && <p className="text-xs text-gray-500">Archived</p>}
                    </div>
                  </button>
                ))
              )}
            </div>
            <div className="flex justify-end">
              <Button type="button" variant="secondary" onClick={closeAddModal}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={pendingRemoval !== null}
        onClose={() => setPendingRemoval(null)}
        title="Remove project from team?"
      >
        {pendingRemoval && (
          <div className="space-y-4">
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              Remove <strong>{pendingRemoval.name}</strong> from <strong>{teamName}</strong>? Members may lose access if they&apos;re not on the project&apos;s primary team. This action is logged.
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setPendingRemoval(null)}>
                Cancel
              </Button>
              <Button type="button" variant="danger" onClick={handleConfirmRemove} isLoading={removeProjectMutation.isPending}>
                Remove
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
