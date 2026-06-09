// ============================================
// TIME TRACKER - API HOOKS
// ============================================
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  projectsApi,
  tasksApi,
  timeEntriesApi,
  teamsApi,
  reportsApi,
} from '../api/client';
import { isNoRunningTimerError } from '../utils/timerErrors';
import { useDebounce } from './useDebounce';
import type {
  ProjectCreate,
  ProjectUpdate,
  ProjectFilters,
  SimilarProjectMatch,
  TeamProject,
  TaskCreate,
  TaskUpdate,
  TaskFilters,
  TimeEntryCreate,
  TimeEntryFilters,
  TeamCreate,
  TeamUpdate,
  TimerStart,
} from '../types';

// ============================================
// PROJECT HOOKS
// ============================================
export function useProjects(filters?: ProjectFilters) {
  return useQuery({
    queryKey: ['projects', filters],
    queryFn: () => projectsApi.getAll(filters),
  });
}

export function useProject(id: number) {
  return useQuery({
    queryKey: ['projects', id],
    queryFn: () => projectsApi.getById(id),
    enabled: !!id,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectCreate) => projectsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['projects', 'similar'] });
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProjectUpdate }) =>
      projectsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['projects', 'similar'] });
    },
  });
}

export function useSimilarProjects(name: string, excludeId?: number, debounceMs = 300): {
  matches: SimilarProjectMatch[];
  isLoading: boolean;
} {
  const debouncedName = useDebounce(name, debounceMs);
  const normalized = debouncedName.trim();

  const query = useQuery({
    queryKey: ['projects', 'similar', normalized, excludeId ?? null],
    queryFn: () => projectsApi.getSimilar(normalized, excludeId),
    enabled: normalized.length > 0,
  });

  return {
    matches: query.data?.matches ?? [],
    isLoading: query.isLoading || query.isFetching,
  };
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => projectsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useArchiveProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isArchived }: { id: number; isArchived: boolean }) =>
      projectsApi.archive(id, isArchived),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useMergeProjects() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceId, targetProjectId }: { sourceId: number; targetProjectId: number }) =>
      projectsApi.merge(sourceId, { target_project_id: targetProjectId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useAddTeamToProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, teamId }: { projectId: number; teamId: number }) =>
      projectsApi.addTeam(projectId, teamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useRemoveTeamFromProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, teamId }: { projectId: number; teamId: number }) =>
      projectsApi.removeTeam(projectId, teamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useTeamProjects(teamId: number | null, includeArchived = false) {
  return useQuery({
    queryKey: ['teamProjects', teamId, includeArchived],
    queryFn: () => teamsApi.getProjects(teamId as number, includeArchived),
    enabled: teamId !== null,
  });
}

export function useAddProjectToTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, teamId }: { projectId: number; teamId: number }) =>
      projectsApi.addTeam(projectId, teamId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['teamProjects'] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useRemoveProjectFromTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, teamId }: { projectId: number; teamId: number }) =>
      projectsApi.removeTeam(projectId, teamId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['teamProjects'] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useProjectTeams(projectId: number) {
  return useQuery({
    queryKey: ['projectTeams', projectId],
    queryFn: () => projectsApi.listTeams(projectId),
    enabled: !!projectId,
  });
}

// ============================================
// TASK HOOKS
// ============================================
export function useTasks(filters?: TaskFilters) {
  return useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => tasksApi.getAll(filters),
  });
}

export function useTask(id: number) {
  return useQuery({
    queryKey: ['tasks', id],
    queryFn: () => tasksApi.getById(id),
    enabled: !!id,
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TaskCreate) => tasksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useUpdateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TaskUpdate }) =>
      tasksApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useDeleteTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => tasksApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

// ============================================
// TIME ENTRY HOOKS
// ============================================
export function useTimeEntries(filters?: TimeEntryFilters) {
  return useQuery({
    queryKey: ['timeEntries', filters],
    queryFn: () => timeEntriesApi.getAll(filters),
  });
}

export function useTimeEntry(id: number) {
  return useQuery({
    queryKey: ['timeEntries', id],
    queryFn: () => timeEntriesApi.getById(id),
    enabled: !!id,
  });
}

export function useCreateTimeEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TimeEntryCreate) => timeEntriesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeEntries'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useDeleteTimeEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => timeEntriesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeEntries'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

// ============================================
// TIMER HOOKS
// ============================================
export function useTimerStatus() {
  return useQuery({
    queryKey: ['timer', 'status'],
    queryFn: () => timeEntriesApi.getTimer(),
    refetchInterval: 30000, // Refetch every 30 seconds
  });
}

export function useStartTimer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data?: TimerStart) => timeEntriesApi.startTimer(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timer'] });
    },
  });
}

export function useStopTimer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => timeEntriesApi.stopTimer(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timer'] });
      queryClient.invalidateQueries({ queryKey: ['timeEntries'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (error) => {
      if (isNoRunningTimerError(error)) {
        queryClient.setQueryData(['timer', 'status'], {
          is_running: false,
          current_entry: null,
          elapsed_seconds: 0,
        });
        queryClient.invalidateQueries({ queryKey: ['timer'] });
      }
    },
  });
}

// ============================================
// TEAM HOOKS
// ============================================
export function useTeams(includeDeleted = false) {
  return useQuery({
    queryKey: ['teams', { includeDeleted }],
    queryFn: () => teamsApi.getAll({ include_deleted: includeDeleted }),
  });
}

export function useTeam(id: number, includeDeleted = false) {
  return useQuery({
    queryKey: ['teams', id, { includeDeleted }],
    queryFn: () => teamsApi.getById(id, includeDeleted),
    enabled: !!id,
  });
}

export function useCreateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TeamCreate) => teamsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
    },
  });
}

export function useUpdateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TeamUpdate }) =>
      teamsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
    },
  });
}

export function useUpdateTeamColor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, color }: { id: number; color: string }) =>
      teamsApi.update(id, { color }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useDeleteTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: number | { id: number; reason?: string }) =>
      typeof input === 'number'
        ? teamsApi.delete(input)
        : teamsApi.delete(input.id, input.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      queryClient.invalidateQueries({ queryKey: ['deletedTeams'] });
    },
  });
}

export function useRestoreTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => teamsApi.restore(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      queryClient.invalidateQueries({ queryKey: ['deletedTeams'] });
    },
  });
}

export function useDeletedTeams(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ['deletedTeams', page, pageSize],
    queryFn: () => teamsApi.listDeleted({ page, page_size: pageSize }),
  });
}

export function useAddTeamMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ teamId, userId, role }: { teamId: number; userId: number; role?: string }) =>
      teamsApi.addMember(teamId, userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
    },
  });
}

export function useRemoveTeamMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ teamId, userId }: { teamId: number; userId: number }) =>
      teamsApi.removeMember(teamId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
    },
  });
}

// ============================================
// REPORT HOOKS
// ============================================
export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: () => reportsApi.getDashboard(),
  });
}

export function useWeeklySummary(startDate?: string) {
  return useQuery({
    queryKey: ['reports', 'weekly', startDate],
    queryFn: () => reportsApi.getWeekly(startDate),
  });
}

export function useProjectReport(startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: ['reports', 'project', startDate, endDate],
    queryFn: () => reportsApi.getByProject(startDate, endDate),
  });
}

export function useTeamReport(teamId: number, startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: ['reports', 'team', teamId, startDate, endDate],
    queryFn: () => reportsApi.getTeamReport(teamId, startDate, endDate),
    enabled: !!teamId,
  });
}
