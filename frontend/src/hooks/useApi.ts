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
import type {
  ProjectCreate,
  ProjectUpdate,
  ProjectFilters,
  TaskCreate,
  TaskUpdate,
  TaskFilters,
  TimeEntryCreate,
  TimeEntryUpdate,
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
    },
  });
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

export function useUpdateTimeEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TimeEntryUpdate }) =>
      timeEntriesApi.update(id, data),
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
  });
}

// ============================================
// TEAM HOOKS
// ============================================
export function useTeams() {
  return useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsApi.getAll(),
  });
}

export function useTeam(id: number) {
  return useQuery({
    queryKey: ['teams', id],
    queryFn: () => teamsApi.getById(id),
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

export function useDeleteTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => teamsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
    },
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
