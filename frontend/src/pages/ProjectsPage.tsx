// ============================================
// TIME TRACKER - PROJECTS PAGE
// ============================================
import React, { useState } from 'react';
import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Card, CardHeader, Button, Input, Modal, LoadingOverlay } from '../components/common';
import { projectsApi, teamsApi } from '../api/client';
import { formatDate, cn, generateRandomColor, isAdminUser } from '../utils/helpers';
import { useAuth } from '../hooks/useAuth';
import {
  useAddTeamToProject,
  useArchiveProject,
  useDeleteProject,
  useMergeProjects,
  useSimilarProjects,
  useUpdateProject,
} from '../hooks/useApi';
import { useNotifications } from '../hooks/useNotifications';
import { useFeatureEnabled } from '../hooks/useAIFeatures';
import { useDebounce } from '../hooks/useDebounce';
import ProjectHealthCard from '../components/ai/ProjectHealthCard';
import { TeamSelect } from '../components/teams/TeamSelect';
import { DeleteProjectModal } from '../components/projects/DeleteProjectModal';
import { EditProjectModal } from '../components/projects/EditProjectModal';
import { MergeProjectModal } from '../components/projects/MergeProjectModal';
import { ProjectKebabMenu } from '../components/projects/ProjectKebabMenu';
import { SimilarProjectsWarning } from '../components/projects/SimilarProjectsWarning';
import type { Project, ProjectCreate, ProjectDeletePreview, ProjectUpdate, SimilarProjectMatch, Team } from '../types';

export function ProjectsPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const { addNotification } = useNotifications();
  const isAdmin = isAdminUser(user);
  const { data: projectHealthEnabled } = useFeatureEnabled('ai_report_summaries');
  const [selectedProjectForHealth, setSelectedProjectForHealth] = useState<Project | null>(null);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [mergeSourceProject, setMergeSourceProject] = useState<Project | null>(null);
  const [deleteProjectTarget, setDeleteProjectTarget] = useState<Project | null>(null);
  const [deletePreview, setDeletePreview] = useState<ProjectDeletePreview | null>(null);
  const [isLoadingDeletePreview, setIsLoadingDeletePreview] = useState(false);
  const [archiveConfirmationProject, setArchiveConfirmationProject] = useState<Project | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [highlightedProjectId, setHighlightedProjectId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState(() => searchParams.get('q') || '');
  const debouncedSearch = useDebounce(searchQuery, 250);
  const activeSearchQuery = debouncedSearch.trim();
  const isSearchActive = activeSearchQuery.length > 0;

  React.useEffect(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      const normalized = searchQuery.trim();
      if (normalized) {
        next.set('q', normalized);
      } else {
        next.delete('q');
      }
      return next;
    }, { replace: true });
  }, [searchQuery, setSearchParams]);

  // Fetch projects — paginated via Load More.
  //
  // Same pagination-shadow problem as TimePage entries (PR #30) and
  // the project selectors (this PR's Part 1): the server defaults to
  // page_size=20 and silently caps the list. We use
  // useInfiniteQuery with page_size=50 and surface a "Showing X of
  // Y" indicator + Load More button so the list is always reachable
  // regardless of how many projects a team accumulates.
  //
  // We fetch with include_archived: true (regardless of the
  // showArchived toggle) so that flipping the toggle is instant and
  // doesn't re-fetch — the toggle is a pure client-side filter on
  // the loaded pages. (At ~hundreds of projects this is fine; if a
  // tenant ever reaches thousands the right fix is to push the
  // archived filter to the server.)
  const PROJECTS_PAGE_SIZE = 50;
  const {
    data: projectsData,
    isLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['projects', 'all', 'paginated', debouncedSearch || ''],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      projectsApi.getAll({
        include_archived: true,
        page: pageParam as number,
        page_size: PROJECTS_PAGE_SIZE,
        search: activeSearchQuery || undefined,
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
  });

  // Fetch teams for dropdown
  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsApi.getAll(1, 100),
  });

  // Filter projects based on showArchived toggle
  const allProjects = (projectsData?.pages ?? []).flatMap((p) => p.items || []);
  const totalProjects = projectsData?.pages?.[0]?.total ?? allProjects.length;
  const projects = showArchived
    ? allProjects.filter((p) => p.is_archived)
    : allProjects.filter((p) => !p.is_archived);
  const teams = teamsData?.items || [];

  React.useEffect(() => {
    if (!highlightedProjectId) return;

    const timeoutId = window.setTimeout(() => {
      const card = document.querySelector(`[data-testid=\"project-card-${highlightedProjectId}\"]`) as HTMLElement | null;
      if (!card) return;

      card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      const addButton = card.querySelector(`[data-testid=\"project-add-team-${highlightedProjectId}\"]`) as HTMLElement | null;
      addButton?.focus();
    }, 300);

    return () => window.clearTimeout(timeoutId);
  }, [highlightedProjectId, allProjects.length]);

  // Create mutation (admin only)
  const createMutation = useMutation({
    mutationFn: (data: ProjectCreate) => projectsApi.create(data),
    onSuccess: (newProject) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['projects', 'similar'] });
      setShowCreateModal(false);
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

  const updateProjectMutation = useUpdateProject();
  const archiveProjectMutation = useArchiveProject();
  const deleteProjectMutation = useDeleteProject();
  const mergeProjectsMutation = useMergeProjects();

  const addTeamToProjectMutation = useAddTeamToProject();

  const handleAddProjectToTeam = (project: Project, team: Team) => {
    addTeamToProjectMutation.mutate(
      { projectId: project.id, teamId: team.id },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['projects'] });
          queryClient.invalidateQueries({ queryKey: ['projectTeams', project.id] });
          addNotification({
            type: 'success',
            title: 'Project Shared With Team',
            message: `${project.name} is now available to ${team.name}`,
          });
        },
        onError: () => {
          addNotification({
            type: 'error',
            title: 'Failed to Share Project',
            message: 'Please try again',
          });
        },
      }
    );
  };

  const handleEdit = (project: Project) => {
    setEditingProject(project);
  };

  const handleSaveEdit = async (data: {
    name: string;
    description?: string | null;
    color: string;
    force?: boolean;
    similar_project_ids?: number[];
  }) => {
    if (!editingProject) return;

    try {
      await updateProjectMutation.mutateAsync({ id: editingProject.id, data: data as ProjectUpdate });
      setEditingProject(null);
      addNotification({ type: 'success', title: 'Project Updated', message: 'Changes have been saved' });
    } catch (_error) {
      addNotification({ type: 'error', title: 'Failed to Update Project', message: 'Please try again' });
    }
  };

  const focusExistingProject = (project: SimilarProjectMatch) => {
    setShowCreateModal(false);
    setEditingProject(null);
    setShowArchived(false);
    setSearchQuery(project.name);
    setHighlightedProjectId(project.id);
  };

  const handleArchiveToggle = (project: Project) => {
    setArchiveConfirmationProject(project);
  };

  const confirmArchiveToggle = () => {
    if (!archiveConfirmationProject) return;
    const shouldArchive = !archiveConfirmationProject.is_archived;
    archiveProjectMutation.mutate(
      { id: archiveConfirmationProject.id, isArchived: shouldArchive },
      {
        onSuccess: () => {
          addNotification({
            type: shouldArchive ? 'info' : 'success',
            title: shouldArchive ? 'Project Archived' : 'Project Restored',
            message: shouldArchive ? 'The project has been archived' : 'The project is now active',
          });
          setArchiveConfirmationProject(null);
        },
      }
    );
  };

  const handleOpenDelete = async (project: Project) => {
    setDeleteProjectTarget(project);
    setDeletePreview(null);
    setIsLoadingDeletePreview(true);
    try {
      const preview = await projectsApi.deletePreview(project.id);
      setDeletePreview(preview);
    } catch (_error) {
      addNotification({ type: 'error', title: 'Failed to Load Delete Details', message: 'Please try again.' });
    } finally {
      setIsLoadingDeletePreview(false);
    }
  };

  const handleConfirmDelete = () => {
    if (!deleteProjectTarget) return;
    deleteProjectMutation.mutate(deleteProjectTarget.id, {
      onSuccess: () => {
        setDeleteProjectTarget(null);
        setDeletePreview(null);
        addNotification({ type: 'success', title: 'Project Deleted', message: 'The project has been permanently deleted' });
      },
      onError: () => {
        addNotification({ type: 'error', title: 'Failed to Delete', message: 'Could not delete the project.' });
      },
    });
  };

  const handleConfirmMerge = (targetProjectId: number) => {
    if (!mergeSourceProject) return;
    mergeProjectsMutation.mutate(
      { sourceId: mergeSourceProject.id, targetProjectId },
      {
        onSuccess: () => {
          addNotification({ type: 'success', title: 'Project Merged', message: 'The source project was merged and archived.' });
          setMergeSourceProject(null);
        },
        onError: () => {
          addNotification({ type: 'error', title: 'Failed to Merge', message: 'Please try again.' });
        },
      }
    );
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
          {user && (
            <Button onClick={() => setShowCreateModal(true)}>
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Project
            </Button>
          )}
        </div>
      </div>

      <div className="w-full sm:max-w-md">
        <div className="relative">
          <Input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search projects by name"
            aria-label="Search projects"
            data-testid="projects-search-input"
            className={cn(searchQuery ? 'pr-10' : undefined)}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              aria-label="Clear search"
              data-testid="projects-search-clear"
            >
              <span aria-hidden="true">×</span>
            </button>
          )}
        </div>
      </div>

      {/* Projects grid */}
      {projects.length === 0 ? (
        <Card className="text-center py-12">
          <svg className="mx-auto w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          {isSearchActive ? (
            <>
              <h3 className="mt-4 text-lg font-medium text-gray-900">
                No projects matching &quot;{activeSearchQuery}&quot;
              </h3>
              <p className="mt-2 text-gray-500">
                Try a different project name or clear your search.
              </p>
              <Button className="mt-4" variant="secondary" onClick={() => setSearchQuery('')}>
                Clear search
              </Button>
            </>
          ) : (
            <>
              <h3 className="mt-4 text-lg font-medium text-gray-900">No projects yet</h3>
              <p className="mt-2 text-gray-500">
                {user ? 'Create your first project to start tracking time.' : 'No projects available. Contact your admin.'}
              </p>
              {user && (
                <Button className="mt-4" onClick={() => setShowCreateModal(true)}>
                  Create Project
                </Button>
              )}
            </>
          )}
        </Card>
      ) : (
        <>
          {/* "Showing X of Y projects" indicator. We show the count of
              the currently-visible (toggle-filtered) projects against
              the loaded total across all pages so the user can tell
              when more pages remain to be fetched. */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500" data-testid="projects-count">
              {isSearchActive
                ? `Showing ${projects.length} projects matching "${activeSearchQuery}"`
                : `Showing ${projects.length} of ${totalProjects} projects`}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project: Project) => (
              <ProjectCard
                key={project.id}
                project={project}
                canManage={!!user}
                showBudgetInfo={isAdmin}
                userTeams={teams}
                showHealthButton={projectHealthEnabled}
                onViewHealth={() => setSelectedProjectForHealth(project)}
                onAddToTeam={(team) => handleAddProjectToTeam(project, team)}
                onEdit={() => handleEdit(project)}
                onArchiveToggle={() => handleArchiveToggle(project)}
                onDelete={() => handleOpenDelete(project)}
                onMerge={() => setMergeSourceProject(project)}
              />
            ))}
          </div>

          {/* Load More — server-side pagination via useInfiniteQuery.
              Hidden once everything is loaded; disabled while the
              next page is in flight. */}
          {hasNextPage && (
            <div className="flex justify-center pt-2">
              <Button
                variant="secondary"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                data-testid="projects-load-more"
              >
                {isFetchingNextPage ? 'Loading…' : 'Load More'}
              </Button>
            </div>
          )}
        </>
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

      <Modal
        isOpen={!!archiveConfirmationProject}
        onClose={() => setArchiveConfirmationProject(null)}
        title={archiveConfirmationProject?.is_archived ? 'Unarchive Project' : 'Archive Project'}
      >
        <div className="space-y-4">
          <p className="text-gray-600">
            {archiveConfirmationProject?.is_archived
              ? `Unarchive "${archiveConfirmationProject.name}"? It will appear in active project lists.`
              : `Archive "${archiveConfirmationProject?.name}"? It will be hidden from default lists but data is preserved.`}
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setArchiveConfirmationProject(null)}>
              Cancel
            </Button>
            <Button onClick={confirmArchiveToggle} isLoading={archiveProjectMutation.isPending}>
              {archiveConfirmationProject?.is_archived ? 'Unarchive' : 'Archive'}
            </Button>
          </div>
        </div>
      </Modal>

      {user && (
        <ProjectModal
          isOpen={showCreateModal}
          onClose={() => {
            setShowCreateModal(false);
          }}
          project={null}
          teams={teams}
          onSubmit={(data) => createMutation.mutate(data as ProjectCreate)}
          isLoading={createMutation.isPending}
          isAdmin={isAdmin}
          onUseExistingProject={focusExistingProject}
        />
      )}

      <EditProjectModal
        isOpen={!!editingProject}
        project={editingProject}
        isSaving={updateProjectMutation.isPending}
        onClose={() => setEditingProject(null)}
        onSave={handleSaveEdit}
        onViewExisting={focusExistingProject}
      />

      <DeleteProjectModal
        isOpen={!!deleteProjectTarget}
        project={deleteProjectTarget}
        preview={deletePreview}
        isLoadingPreview={isLoadingDeletePreview}
        isDeleting={deleteProjectMutation.isPending}
        onClose={() => {
          setDeleteProjectTarget(null);
          setDeletePreview(null);
        }}
        onConfirm={handleConfirmDelete}
      />

      <MergeProjectModal
        isOpen={!!mergeSourceProject}
        sourceProject={mergeSourceProject}
        projects={allProjects}
        isMerging={mergeProjectsMutation.isPending}
        onClose={() => setMergeSourceProject(null)}
        onConfirm={handleConfirmMerge}
      />
    </div>
  );
}

// Project Card Component
interface ProjectCardProps {
  project: Project;
  canManage: boolean;
  showBudgetInfo: boolean;
  userTeams: Team[];
  showHealthButton?: boolean;
  onViewHealth?: () => void;
  onAddToTeam: (team: Team) => void;
  onEdit: () => void;
  onArchiveToggle: () => void;
  onMerge: () => void;
  onDelete: () => void;
}

function ProjectCard({
  project,
  canManage,
  showBudgetInfo,
  userTeams,
  showHealthButton,
  onViewHealth,
  onAddToTeam,
  onEdit,
  onArchiveToggle,
  onMerge,
  onDelete,
}: ProjectCardProps) {
  const projectTeams = project.team_associations ?? [];
  const [selectedTeamId, setSelectedTeamId] = useState<number | ''>('');

  const associatedTeamIds = new Set<number>(projectTeams.map((row) => row.team_id));
  const userTeamIds = new Set(userTeams.map((team) => team.id));
  const candidateTeams = userTeams.filter((team) => !associatedTeamIds.has(team.id));
  const userHasTeamAccess = [...userTeamIds].some((teamId) => associatedTeamIds.has(teamId));
  const showNotOnYourTeam = userTeams.length > 0 && !userHasTeamAccess;

  React.useEffect(() => {
    if (candidateTeams.length > 0) {
      setSelectedTeamId((prev) => {
        if (prev !== '' && candidateTeams.some((team) => team.id === prev)) {
          return prev;
        }
        return candidateTeams[0].id;
      });
    } else {
      setSelectedTeamId('');
    }
  }, [project.id, candidateTeams]);

  const teamNames = projectTeams.map((row) => row.team_name).join(', ');

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  return (
    <Card className="hover:shadow-md transition-shadow" data-testid={`project-card-${project.id}`}>
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
        {canManage && (
          <ProjectKebabMenu
            isArchived={project.is_archived}
            canMerge={!project.is_archived}
            onEdit={onEdit}
            onArchiveToggle={onArchiveToggle}
            onMerge={onMerge}
            onDelete={onDelete}
          />
        )}
      </div>

      {showNotOnYourTeam && (
        <div className="mt-2">
          <span
            className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600"
            title="You can see this project but can't track time. Click 'Add to my team' to start working on it."
          >
            Not on your team
          </span>
        </div>
      )}

      <div className="mt-3 text-xs text-gray-500" title={teamNames || undefined}>
        Teams: {teamNames || 'Unknown'}
      </div>

      <div className="mt-3 flex items-center gap-2">
        {userTeams.length === 0 ? (
          <Button size="sm" variant="secondary" disabled title="Join a team to add projects">
            Add to my team
          </Button>
        ) : userTeams.length === 1 ? (
          candidateTeams.length === 1 ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onAddToTeam(candidateTeams[0])}
              data-testid={`project-add-team-${project.id}`}
            >
              Add to {candidateTeams[0].name}
            </Button>
          ) : null
        ) : candidateTeams.length > 0 ? (
          <div className="flex items-center gap-2 w-full">
            <select
              aria-label={`Select team for ${project.name}`}
              className="h-9 flex-1 rounded-lg border border-gray-300 bg-white px-2 text-sm"
              value={selectedTeamId}
              onChange={(e) => setSelectedTeamId(Number(e.target.value))}
              data-testid={`project-team-select-${project.id}`}
            >
              {candidateTeams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                const selected = candidateTeams.find((team) => team.id === selectedTeamId);
                if (selected) onAddToTeam(selected);
              }}
              data-testid={`project-add-team-${project.id}`}
            >
              Add to team...
            </Button>
          </div>
        ) : null}
      </div>
      
      {/* Budget info - Admin only */}
      {showBudgetInfo && (project.budget_amount || project.deadline) && (
        <div className="mt-3 flex items-center gap-3 text-xs">
          {project.budget_amount && (
            <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 rounded-md">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {formatCurrency(project.budget_amount)}
            </span>
          )}
          {project.deadline && (
            <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 rounded-md">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              {new Date(project.deadline).toLocaleDateString()}
            </span>
          )}
        </div>
      )}
      
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
  isAdmin: boolean;
  onUseExistingProject?: (project: SimilarProjectMatch) => void;
}

function ProjectModal({
  isOpen,
  onClose,
  project,
  teams,
  onSubmit,
  isLoading,
  isAdmin,
  onUseExistingProject,
}: ProjectModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [teamId, setTeamId] = useState<number | ''>('');
  const [color, setColor] = useState('#3B82F6');
  const [budgetAmount, setBudgetAmount] = useState<string>('');
  const [deadline, setDeadline] = useState<string>('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingSimilarMatches, setPendingSimilarMatches] = useState<SimilarProjectMatch[]>([]);
  const { matches } = useSimilarProjects(name);

  // Reset form when modal opens/closes or project changes
  React.useEffect(() => {
    if (project) {
      setName(project.name);
      setDescription(project.description || '');
      setTeamId(project.team_id);
      setColor(project.color);
      setBudgetAmount(project.budget_amount ? String(project.budget_amount) : '');
      setDeadline(project.deadline || '');
    } else {
      setName('');
      setDescription('');
      setTeamId(teams[0]?.id || '');
      setColor(generateRandomColor());
      setBudgetAmount('');
      setDeadline('');
    }

    setConfirmOpen(false);
    setPendingSimilarMatches([]);
  }, [project, isOpen, teams]);

  const submitPayload = (force = false) => {
    const ids = pendingSimilarMatches.map((item) => item.id);
    const data: Partial<ProjectCreate> = {
      name: name.trim(),
      description: description.trim() ? description.trim() : undefined,
      team_id: teamId as number,
      color,
      force,
      similar_project_ids: force && ids.length > 0 ? ids : undefined,
    };
    
    // Include budget fields only if admin
    if (isAdmin) {
      data.budget_amount = budgetAmount ? parseFloat(budgetAmount) : null;
      data.deadline = deadline || null;
    }

    onSubmit(data);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;

    const finalCheck = await projectsApi.getSimilar(trimmedName);
    if (finalCheck.matches.length > 0) {
      setPendingSimilarMatches(finalCheck.matches);
      setConfirmOpen(true);
      return;
    }

    submitPayload(false);
  };

  return (
    <>
    <Modal isOpen={isOpen} onClose={onClose} title={project ? 'Edit Project' : 'New Project'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Project Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="My Project"
          required
        />

        <SimilarProjectsWarning
          matches={matches}
          mode="create"
          onUseExisting={(match) => {
            onUseExistingProject?.(match);
            onClose();
          }}
        />

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Team
          </label>
          <TeamSelect
            value={teamId === '' ? null : teamId}
            onChange={(id) => setTeamId(id ?? '')}
            teams={teams}
            placeholder="Select a team"
            required
            ariaLabel="Team"
          />
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

        {/* Budget Fields - Admin Only */}
        {isAdmin && (
          <>
            <div className="border-t pt-4 mt-4">
              <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Budget Settings
              </h4>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Budget (USD)
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                    <input
                      type="number"
                      value={budgetAmount}
                      onChange={(e) => setBudgetAmount(e.target.value)}
                      placeholder="0.00"
                      min="0"
                      step="0.01"
                      className="block w-full pl-7 pr-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Deadline
                  </label>
                  <input
                    type="date"
                    value={deadline}
                    onChange={(e) => setDeadline(e.target.value)}
                    className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
              
              <p className="text-xs text-gray-500 mt-2">
                Budget and deadline are used for AI forecasting. Only admins can see and edit these fields.
              </p>
            </div>
          </>
        )}

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

    <Modal
      isOpen={confirmOpen}
      onClose={() => setConfirmOpen(false)}
      title="Similar projects found"
      size="sm"
    >
      <div className="space-y-4">
        <p className="text-sm text-gray-700">
          Similar projects exist. Are you sure you want to create &quot;{name.trim()}&quot;?
        </p>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => submitPayload(true)}
            isLoading={isLoading}
            data-testid="create-project-create-anyway"
          >
            Create anyway
          </Button>
        </div>
      </div>
    </Modal>
    </>
  );
}
