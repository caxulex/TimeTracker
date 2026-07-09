// ============================================
// TIME TRACKER - API CLIENT
// ============================================
import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import type {
  AuthToken,
  User,
  UserLogin,
  UserRegister,
  UserCreate,
  Team,
  TeamCreate,
  TeamUpdate,
  TeamMember,
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectTeamAssociation,
  TeamProject,
  ProjectDeletePreview,
  ProjectDeleteResult,
  ProjectMergeRequest,
  ProjectMergeResult,
  ProjectMergePreview,
  SimilarProjectsResponse,
  ProjectFilters,
  Task,
  TaskCreate,
  TaskUpdate,
  TaskFilters,
  TimeEntry,
  TimeEntryCreate,
  TimeEntryUpdate,
  TimeEntryFilters,
  TimerStart,
  TimerStatus,
  DashboardStats,
  WeeklySummary,
  PaginatedResponse,
} from '../types';
import type { PayRateCreate, PayRateUpdate } from '../types/payroll';

function normalizeApiBaseUrl(input: string): string {
  const trimmed = (input ?? '').trim();
  if (!trimmed) return '';

  // Remove trailing slashes
  const withoutTrailingSlash = trimmed.replace(/\/+$/g, '');

  // Avoid "/api/api/*" when callers already prefix routes with "/api/..."
  if (withoutTrailingSlash.endsWith('/api')) {
    return withoutTrailingSlash.slice(0, -4);
  }

  return withoutTrailingSlash;
}

const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_URL || '');

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // TODO(B17, XSS-risk): localStorage-stored tokens expose the SPA to total
    // account takeover on any XSS. Migration plan: refresh token in
    // httpOnly+Secure+SameSite=Strict cookie, access token in a module-level
    // variable here (getAccessToken/setAccessToken accessors). See
    // POST_LAUNCH_TODO.md » "B17 token storage migration plan".
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Redirect loop detection - prevents infinite redirect between dashboard and login
let authRedirectCount = 0;
const MAX_AUTH_REDIRECTS = 3;
const AUTH_REDIRECT_RESET_MS = 5000;
let authRedirectResetTimer: ReturnType<typeof setTimeout> | null = null;

// Helper to clear all auth state and redirect (used to break redirect loops)
const forceLogoutAndRedirect = () => {
  console.warn('[Auth] Forcing logout and redirect to login');
  // TODO(B17, XSS-risk): replace with cookie clear + in-memory token reset
  // post-migration. See POST_LAUNCH_TODO.md » B17.
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  // Clear the persisted Zustand auth state to prevent redirect loops
  const authStorage = localStorage.getItem('auth-storage');
  if (authStorage) {
    try {
      const parsed = JSON.parse(authStorage);
      parsed.state = { ...parsed.state, isAuthenticated: false, user: null };
      localStorage.setItem('auth-storage', JSON.stringify(parsed));
    } catch (e) {
      // If parsing fails, just remove it entirely
      localStorage.removeItem('auth-storage');
    }
  }
  
  // Determine correct login page from CURRENT URL path (not stale localStorage)
  // This ensures redirect matches where user actually is
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  const potentialSlug = pathParts[0];
  
  // Check if first path segment looks like a company slug (not a known route)
  const knownRoutes = ['login', 'register', 'dashboard', 'projects', 'tasks', 'time', 
                       'teams', 'reports', 'settings', 'admin', 'staff', 'users',
                       'forgot-password', 'reset-password', 'request-account'];
  
  if (potentialSlug && !knownRoutes.includes(potentialSlug)) {
    // First segment is likely a company slug
    localStorage.setItem('tt_company_slug', potentialSlug);
    window.location.href = `/${potentialSlug}/login`;
  } else {
    // Main site - clear any stale company slug
    localStorage.removeItem('tt_company_slug');
    window.location.href = '/login';
  }
};

// Token refresh mutex to prevent multiple simultaneous refresh attempts
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

// Subscribe to token refresh
function subscribeTokenRefresh(callback: (token: string) => void) {
  refreshSubscribers.push(callback);
}

// Notify all subscribers when token is refreshed
function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach(callback => callback(token));
  refreshSubscribers = [];
}

// Response interceptor for error handling and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Handle network errors (disconnection) - don't redirect, let UI show error
    if (!error.response) {
      console.error('Network error - no response received');
      return Promise.reject(error);
    }

    const status = error.response?.status;

    // Handle 401 (Unauthorized) - redirect to login
    if (status === 401 && !originalRequest._retry) {
      // Skip if this is a login/refresh request to avoid infinite loops
      const isAuthEndpoint = originalRequest.url?.includes('/auth/login') || 
                             originalRequest.url?.includes('/auth/refresh');
      
      if (isAuthEndpoint) {
        forceLogoutAndRedirect();
        return Promise.reject(error);
      }

      // Detect redirect loop - if we've redirected too many times, force a clean logout
      authRedirectCount++;
      if (authRedirectCount >= MAX_AUTH_REDIRECTS) {
        console.error('[Auth] Redirect loop detected - forcing clean logout');
        authRedirectCount = 0;
        if (authRedirectResetTimer) clearTimeout(authRedirectResetTimer);
        forceLogoutAndRedirect();
        return Promise.reject(error);
      }
      
      // Reset redirect counter after timeout
      if (authRedirectResetTimer) clearTimeout(authRedirectResetTimer);
      authRedirectResetTimer = setTimeout(() => {
        authRedirectCount = 0;
      }, AUTH_REDIRECT_RESET_MS);

      originalRequest._retry = true;

      // Try to refresh the token first (only for 401)
      if (status === 401) {
        // If already refreshing, wait for the refresh to complete
        if (isRefreshing) {
          return new Promise((resolve) => {
            subscribeTokenRefresh((newToken: string) => {
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${newToken}`;
              }
              resolve(api(originalRequest));
            });
          });
        }

        isRefreshing = true;

        try {
          // TODO(B17, XSS-risk): post-migration the refresh token will be sent
          // automatically as an httpOnly cookie via { credentials: 'include' };
          // remove this localStorage read and the request body field once the
          // backend dual-source acceptance window closes (see POST_LAUNCH_TODO
          // » B17 token storage migration plan).
          const refreshToken = localStorage.getItem('refresh_token');
          if (refreshToken) {
            const response = await axios.post<AuthToken>(`${API_BASE_URL}/api/auth/refresh`, {
              refresh_token: refreshToken,
            });

            const { access_token, refresh_token } = response.data;
            // TODO(B17, XSS-risk): swap for setAccessToken(access_token); the
            // refresh token will not be returned in the body post-migration.
            localStorage.setItem('access_token', access_token);
            localStorage.setItem('refresh_token', refresh_token);
            
            // Reset redirect counter on successful refresh
            authRedirectCount = 0;
            isRefreshing = false;

            // Notify all waiting requests
            onTokenRefreshed(access_token);

            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${access_token}`;
            }
            return api(originalRequest);
          }
        } catch (refreshError) {
          // Refresh failed, clear tokens and redirect to login
          console.error('Token refresh failed:', refreshError);
          isRefreshing = false;
          refreshSubscribers = [];
        }
      }

      // Clear tokens AND Zustand auth state, then redirect to login
      forceLogoutAndRedirect();
      return Promise.reject(error);
    }

    // 403 Forbidden: authenticated but not authorized for this specific resource.
    // Let the caller handle the error - do NOT logout or redirect.
    if (status === 403) {
      return Promise.reject(error);
    }

    return Promise.reject(error);
  }
);

// ============================================
// AUTH API
// ============================================
export const authApi = {
  login: async (credentials: UserLogin): Promise<AuthToken> => {
    const response = await api.post<AuthToken>('/api/auth/login', credentials);
    return response.data;
  },

  register: async (data: UserRegister): Promise<User> => {
    const response = await api.post<User>('/api/auth/register', data);
    return response.data;
  },

  logout: async (): Promise<void> => {
    // B15: Send the refresh token so the backend can revoke it. If the
    // token is missing from storage, the backend still revokes the
    // access token and logs a warning.
    const refreshToken = localStorage.getItem('refresh_token');
    await api.post('/api/auth/logout', refreshToken ? { refresh_token: refreshToken } : {});
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },

  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/api/auth/me');
    return response.data;
  },

  updateMe: async (data: Partial<User>): Promise<User> => {
    const response = await api.put<User>('/api/auth/me', data);
    return response.data;
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await api.put('/api/auth/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },
};

// ============================================
// USERS API (Admin)
// ============================================
export const usersApi = {
  getAll: async (
    pageOrParams: number | { page?: number; page_size?: number; search?: string } = 1,
    size = 20
  ): Promise<PaginatedResponse<User>> => {
    // Backend's actual query-param names are `page_size` and `search`
    // (see app/routers/users.py). Keep `(page, size)` for back-compat.
    const params =
      typeof pageOrParams === 'number'
        ? { page: pageOrParams, page_size: size }
        : {
            page: pageOrParams.page ?? 1,
            page_size: pageOrParams.page_size ?? 20,
            search: pageOrParams.search,
          };
    const response = await api.get<PaginatedResponse<User>>('/api/users', {
      params,
    });
    return response.data;
  },

  getById: async (id: number): Promise<User> => {
    const response = await api.get<User>(`/api/users/${id}`);
    return response.data;
  },

  create: async (data: UserCreate): Promise<User> => {
    const response = await api.post<User>('/api/users', data);
    return response.data;
  },

  update: async (id: number, data: Partial<User>): Promise<User> => {
    const response = await api.put<User>(`/api/users/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/users/${id}`);
  },

  permanentDelete: async (id: number): Promise<{ message: string }> => {
    const response = await api.delete<{ message: string }>(`/api/users/${id}/permanent`);
    return response.data;
  },

  updateRole: async (id: number, role: string): Promise<User> => {
    const response = await api.put<User>(`/api/users/${id}/role`, { role });
    return response.data;
  },
};

// ============================================
// TEAMS API
// ============================================
export const teamsApi = {
  getAll: async (
    pageOrParams: number | { page?: number; page_size?: number; search?: string; include_deleted?: boolean } = 1,
    size = 20
  ): Promise<PaginatedResponse<Team>> => {
    // Backend's actual query-param names are `page_size` and `search`
    // (see app/routers/teams.py). Keep `(page, size)` for back-compat.
    const params =
      typeof pageOrParams === 'number'
        ? { page: pageOrParams, page_size: size }
        : {
            page: pageOrParams.page ?? 1,
            page_size: pageOrParams.page_size ?? 20,
            search: pageOrParams.search,
            include_deleted: pageOrParams.include_deleted ?? false,
          };
    const response = await api.get<PaginatedResponse<Team>>('/api/teams', {
      params,
    });
    return response.data;
  },

  getById: async (id: number, includeDeleted = false): Promise<Team & { members: TeamMember[] }> => {
    const response = await api.get<Team & { members: TeamMember[] }>(`/api/teams/${id}`, {
      params: { include_deleted: includeDeleted },
    });
    return response.data;
  },

  getProjects: async (teamId: number, includeArchived = false): Promise<TeamProject[]> => {
    const response = await api.get<TeamProject[]>(`/api/teams/${teamId}/projects`, {
      params: { include_archived: includeArchived },
    });
    return response.data;
  },

  create: async (data: TeamCreate): Promise<Team> => {
    const response = await api.post<Team>('/api/teams', data);
    return response.data;
  },

  update: async (id: number, data: TeamUpdate): Promise<Team> => {
    const response = await api.put<Team>(`/api/teams/${id}`, data);
    return response.data;
  },

  delete: async (id: number, reason?: string): Promise<void> => {
    await api.delete(`/api/teams/${id}`, {
      data: reason ? { reason } : undefined,
    });
  },

  restore: async (id: number): Promise<Team> => {
    const response = await api.post<Team>(`/api/teams/${id}/restore`);
    return response.data;
  },

  listDeleted: async (
    params: { page?: number; page_size?: number } = {}
  ): Promise<PaginatedResponse<Team>> => {
    const response = await api.get<PaginatedResponse<Team>>('/api/teams/deleted', {
      params,
    });
    return response.data;
  },

  addMember: async (teamId: number, userId: number, role = 'member'): Promise<TeamMember> => {
    const response = await api.post<TeamMember>(`/api/teams/${teamId}/members`, {
      user_id: userId,
      role,
    });
    return response.data;
  },

  updateMember: async (teamId: number, userId: number, role: string): Promise<TeamMember> => {
    const response = await api.put<TeamMember>(`/api/teams/${teamId}/members/${userId}`, {
      role,
    });
    return response.data;
  },

  removeMember: async (teamId: number, userId: number): Promise<void> => {
    await api.delete(`/api/teams/${teamId}/members/${userId}`);
  },
};

// ============================================
// PROJECTS API
// ============================================
export const projectsApi = {
  getAll: async (filters?: ProjectFilters): Promise<PaginatedResponse<Project>> => {
    const response = await api.get<PaginatedResponse<Project>>('/api/projects', {
      params: filters,
    });
    return response.data;
  },

  getById: async (id: number): Promise<Project> => {
    const response = await api.get<Project>(`/api/projects/${id}`);
    return response.data;
  },

  create: async (data: ProjectCreate): Promise<Project> => {
    const response = await api.post<Project>('/api/projects', data);
    return response.data;
  },

  getSimilar: async (
    name: string,
    excludeId?: number,
    includeArchived = false
  ): Promise<SimilarProjectsResponse> => {
    const response = await api.get<SimilarProjectsResponse>('/api/projects/similar', {
      params: {
        name,
        exclude_id: excludeId,
        include_archived: includeArchived,
      },
    });
    return response.data;
  },

  update: async (id: number, data: ProjectUpdate): Promise<Project> => {
    const response = await api.put<Project>(`/api/projects/${id}`, data);
    return response.data;
  },

  archive: async (id: number, isArchived: boolean): Promise<Project> => {
    const response = await api.patch<Project>(`/api/projects/${id}/archive`, {
      is_archived: isArchived,
    });
    return response.data;
  },

  deletePreview: async (id: number): Promise<ProjectDeletePreview> => {
    const response = await api.get<ProjectDeletePreview>(`/api/projects/${id}/delete-preview`);
    return response.data;
  },

  delete: async (id: number): Promise<ProjectDeleteResult> => {
    const response = await api.delete<ProjectDeleteResult>(`/api/projects/${id}`);
    return response.data;
  },

  restore: async (id: number): Promise<Project> => {
    const response = await api.post<Project>(`/api/projects/${id}/restore`);
    return response.data;
  },

  merge: async (sourceId: number, data: ProjectMergeRequest): Promise<ProjectMergeResult> => {
    const response = await api.post<ProjectMergeResult>(`/api/projects/${sourceId}/merge`, data);
    return response.data;
  },

  mergePreview: async (sourceId: number, data: ProjectMergeRequest): Promise<ProjectMergePreview> => {
    const response = await api.post<ProjectMergePreview>(`/api/projects/${sourceId}/merge/preview`, data);
    return response.data;
  },

  addTeam: async (projectId: number, teamId: number): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>(`/api/projects/${projectId}/teams`, {
      team_id: teamId,
    });
    return response.data;
  },

  removeTeam: async (projectId: number, teamId: number): Promise<void> => {
    await api.delete(`/api/projects/${projectId}/teams/${teamId}`);
  },

  listTeams: async (projectId: number): Promise<ProjectTeamAssociation[]> => {
    const response = await api.get<ProjectTeamAssociation[]>(`/api/projects/${projectId}/teams`);
    return response.data;
  },
};

// ============================================
// TASKS API
// ============================================
export const tasksApi = {
  getAll: async (filters?: TaskFilters): Promise<PaginatedResponse<Task>> => {
    const response = await api.get<PaginatedResponse<Task>>('/api/tasks', {
      params: filters,
    });
    return response.data;
  },

  getById: async (id: number): Promise<Task> => {
    const response = await api.get<Task>(`/api/tasks/${id}`);
    return response.data;
  },

  create: async (data: TaskCreate): Promise<Task> => {
    const response = await api.post<Task>('/api/tasks', data);
    return response.data;
  },

  update: async (id: number, data: TaskUpdate): Promise<Task> => {
    const response = await api.put<Task>(`/api/tasks/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/tasks/${id}`);
  },
};

// ============================================
// TIME ENTRIES API
// ============================================
export const timeEntriesApi = {
  getAll: async (filters?: TimeEntryFilters): Promise<PaginatedResponse<TimeEntry>> => {
    const response = await api.get<PaginatedResponse<TimeEntry>>('/api/time', {
      params: filters,
    });
    return response.data;
  },

  getById: async (id: number): Promise<TimeEntry> => {
    const response = await api.get<TimeEntry>(`/api/time/${id}`);
    return response.data;
  },

  create: async (data: TimeEntryCreate): Promise<TimeEntry> => {
    const response = await api.post<TimeEntry>('/api/time', data);
    return response.data;
  },

  update: async (id: number, data: TimeEntryUpdate): Promise<TimeEntry> => {
    const response = await api.put<TimeEntry>(`/api/time/${id}`, data);
    return response.data;
  },

  updateEntry: async (entryId: number, updates: TimeEntryUpdate): Promise<TimeEntry> => {
    const response = await api.patch<TimeEntry>(`/api/time/entries/${entryId}`, updates);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/time/${id}`);
  },

  // Timer operations
  getTimer: async (): Promise<TimerStatus> => {
    const response = await api.get<TimerStatus>('/api/time/timer');
    return response.data;
  },

  startTimer: async (data?: TimerStart): Promise<TimeEntry> => {
    const response = await api.post<TimeEntry>('/api/time/start', data || {});
    return response.data;
  },

  stopTimer: async (): Promise<TimeEntry> => {
    const response = await api.post<TimeEntry>('/api/time/stop');
    return response.data;
  },

  switchTimer: async (data: { project_id: number; task_id?: number; description?: string }): Promise<TimeEntry> => {
    const response = await api.post<TimeEntry>('/api/time/switch', data);
    return response.data;
  },

  getActiveTimers: async (): Promise<TimeEntry[]> => {
    const response = await api.get<TimeEntry[]>('/api/time/active');
    return response.data;
  },
};

// ============================================
// REPORTS API
// ============================================
export const reportsApi = {
  getDashboard: async (): Promise<DashboardStats> => {
    const response = await api.get<DashboardStats>('/api/reports/dashboard');
    return response.data;
  },

  getWeekly: async (startDate?: string, endDate?: string): Promise<WeeklySummary> => {
    const params: Record<string, string> = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    const response = await api.get<WeeklySummary>('/api/reports/weekly', {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return response.data;
  },

  getByProject: async (startDate?: string, endDate?: string) => {
    const response = await api.get('/api/reports/by-project', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  },

  getByTask: async (projectId?: number, startDate?: string, endDate?: string) => {
    const response = await api.get('/api/reports/by-task', {
      params: { project_id: projectId, start_date: startDate, end_date: endDate },
    });
    return response.data;
  },

  getTeamReport: async (teamId: number, startDate?: string, endDate?: string) => {
    const response = await api.get('/api/reports/team', {
      params: { team_id: teamId, start_date: startDate, end_date: endDate },
    });
    return response.data;
  },

  getTeamTimesheet: async (startDate: string, endDate: string, teamId?: number) => {
    const response = await api.get('/api/reports/team-timesheet', {
      params: { start_date: startDate, end_date: endDate, team_id: teamId },
    });
    return response.data;
  },

  exportTeamTimesheetCsv: async (startDate: string, endDate: string, teamId?: number): Promise<Blob> => {
    const response = await api.get('/api/reports/team-timesheet/export/csv', {
      params: { start_date: startDate, end_date: endDate, team_id: teamId },
      responseType: 'blob',
    });
    return response.data;
  },

  exportTeamTimesheetExcel: async (startDate: string, endDate: string, teamId?: number): Promise<Blob> => {
    const response = await api.get('/api/reports/team-timesheet/export/excel', {
      params: { start_date: startDate, end_date: endDate, team_id: teamId },
      responseType: 'blob',
    });
    return response.data;
  },

  exportTeamTimesheetPdf: async (startDate: string, endDate: string, teamId?: number): Promise<Blob> => {
    const response = await api.get('/api/reports/team-timesheet/export/pdf', {
      params: { start_date: startDate, end_date: endDate, team_id: teamId },
      responseType: 'blob',
    });
    return response.data;
  },

  getAdminDashboard: async () => {
    const response = await api.get('/api/reports/admin/dashboard');
    return response.data;
  },

  getAdminUserDetail: async (userId: number): Promise<{
    user_id: number;
    user_name: string;
    user_email: string;
    role: string;
    teams: string[];
    today_seconds: number;
    today_hours: number;
    week_seconds: number;
    week_hours: number;
    month_seconds: number;
    month_hours: number;
    total_entries: number;
    active_days_this_month: number;
    avg_hours_per_day: number;
    avg_denominator_days?: number;
    avg_denominator_type?: 'working_days_completed' | 'working_days_all' | 'days_with_entries' | 'calendar_days';
    avg_includes_today?: boolean;
    avg_working_days_source?: 'user' | 'company' | 'default';
    avg_working_days_used?: number[];
    current_timer_running: boolean;
    projects: Array<{
      project_id: number;
      project_name: string;
      total_seconds: number;
      total_hours: number;
      entry_count: number;
    }>;
    last_activity: string | null;
  }> => {
    const response = await api.get(`/api/reports/admin/users/${userId}`);
    return response.data;
  },

  getAdminUserAnalytics: async (
    userId: number,
    startDate: string,
    endDate: string,
  ): Promise<{
    user_id: number;
    user_name: string;
    start_date: string;
    end_date: string;
    total_seconds: number;
    total_hours: number;
    total_entries: number;
    days_worked: number;
    project_count: number;
    avg_hours_per_entry: number;
    projects: Array<{
      project_id: number;
      project_name: string;
      total_seconds: number;
      total_hours: number;
      entry_count: number;
    }>;
  }> => {
    const response = await api.get(
      `/api/reports/admin/users/${userId}/analytics`,
      { params: { start_date: startDate, end_date: endDate } },
    );
    return response.data;
  },

  getAdminTimeEntries: async (params: {
    start_date: string;
    end_date: string;
    user_id?: number;
    team_id?: number;
    project_id?: number;
  }) => {
    const response = await api.get('/api/admin/time-entries', { params });
    return response.data;
  },

  exportReport: async (format: 'csv' | 'json', startDate?: string, endDate?: string) => {
    const response = await api.get('/api/reports/export', {
      params: { format, start_date: startDate, end_date: endDate },
      responseType: format === 'csv' ? 'blob' : 'json',
    });
    return response.data;
  },
};

export default api;



// ============================================
// EXPORT API (TASK-029)
// ============================================
export const exportApi = {
  downloadExcel: async (params?: {
    start_date?: string;
    end_date?: string;
    project_id?: number;
    user_id?: number;
  }): Promise<Blob> => {
    try {
      const response = await api.get('/api/export/excel', {
        params,
        responseType: 'blob',
      });
      return response.data;
    } catch (error: unknown) {
      // If error response is a blob, try to read it as text
      if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
        const text = await error.response.data.text();
        try {
          const json = JSON.parse(text);
          throw new Error(json.detail || 'Export failed');
        } catch {
          throw new Error(text || 'Export failed');
        }
      }
      throw error;
    }
  },

  downloadPdf: async (params?: {
    start_date?: string;
    end_date?: string;
    project_id?: number;
    user_id?: number;
  }): Promise<Blob> => {
    try {
      const response = await api.get('/api/export/pdf', {
        params,
        responseType: 'blob',
      });
      return response.data;
    } catch (error: unknown) {
      // If error response is a blob, try to read it as text
      if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
        const text = await error.response.data.text();
        try {
          const json = JSON.parse(text);
          throw new Error(json.detail || 'Export failed');
        } catch {
          throw new Error(text || 'Export failed');
        }
      }
      throw error;
    }
  },

  downloadCsv: async (params?: {
    start_date?: string;
    end_date?: string;
    project_id?: number;
    user_id?: number;
  }): Promise<Blob> => {
    try {
      const response = await api.get('/api/export/csv', {
        params,
        responseType: 'blob',
      });
      return response.data;
    } catch (error: unknown) {
      // If error response is a blob, try to read it as text
      if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
        const text = await error.response.data.text();
        try {
          const json = JSON.parse(text);
          throw new Error(json.detail || 'Export failed');
        } catch {
          throw new Error(text || 'Export failed');
        }
      }
      throw error;
    }
  },
};

// ============================================
// PAY RATES API
// ============================================
export const payRatesApi = {
  getUserCurrentRate: async (userId: number) => {
    const response = await api.get(`/api/pay-rates/user/${userId}/current`);
    return response.data;
  },

  getUserPayRates: async (userId: number, includeInactive = false) => {
    const response = await api.get(`/api/pay-rates/user/${userId}`, {
      params: { include_inactive: includeInactive },
    });
    return response.data;
  },

  getAll: async (page = 1, pageSize = 100, activeOnly = true) => {
    const response = await api.get('/api/pay-rates', {
      params: { skip: (page - 1) * pageSize, page_size: pageSize, active_only: activeOnly },
    });
    return response.data;
  },

  create: async (data: PayRateCreate) => {
    const response = await api.post('/api/pay-rates', data);
    return response.data;
  },

  update: async (id: number, data: PayRateUpdate) => {
    const response = await api.put(`/api/pay-rates/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/api/pay-rates/${id}`);
  },

  getHistory: async (payRateId: number) => {
    const response = await api.get(`/api/pay-rates/${payRateId}/history`);
    return response.data;
  },
};

// ============================================
// COMPANIES API
// ============================================
export interface Company {
  id: number;
  name: string;
  slug: string;
  email: string;
  phone: string | null;
  timezone: string;
  subscription_tier: string;
  status: string;
  trial_ends_at: string | null;
  max_users: number;
  max_projects: number;
  created_at: string;
}

export interface CompanyUpdate {
  name?: string;
  phone?: string;
  timezone?: string;
}

export interface BillingStatus {
  worker_count: number;
  free_limit: number;
  seats_over_free: number;
  per_seat_monthly_cost_dollars: number;
  should_recommend_unlimited: boolean;
  subscription_tier: 'free' | 'standard' | 'unlimited';
  has_subscription: boolean;
  is_at_or_over_free_limit: boolean;
  would_block_next_add: boolean;
}

interface CompanyBillingActionResponseBase {
  success: boolean;
  status: string;
  company_id: number;
  subscription_tier: 'free' | 'standard' | 'unlimited';
  stripe_subscription_id?: string | null;
  requires_payment_action?: boolean;
  message?: string | null;
}

export interface CompanyBillingUpgradeResponse extends CompanyBillingActionResponseBase {
  stripe_customer_id?: string | null;
}

export interface CompanyBillingSwitchResponse extends CompanyBillingActionResponseBase {}

// Email Settings Types
export interface EmailSettings {
  email_enabled: boolean;
  smtp_server: string | null;
  smtp_port: number;
  smtp_username: string | null;
  smtp_from_email: string | null;
  smtp_from_name: string | null;
  smtp_use_tls: boolean;
  smtp_password_set: boolean;
}

export interface EmailSettingsUpdate {
  email_enabled?: boolean;
  smtp_server?: string;
  smtp_port?: number;
  smtp_username?: string;
  smtp_password?: string;
  smtp_from_email?: string;
  smtp_from_name?: string;
  smtp_use_tls?: boolean;
}

export interface TestEmailRequest {
  recipient: string;
}

export interface TestEmailResponse {
  success: boolean;
  message: string;
}

// Welcome Credentials Email Types
export interface WelcomeCredentialsRequest {
  recipient_email: string;
  recipient_name: string;
  temporary_password: string;
  job_title?: string;
  department?: string;
}

export interface WelcomeCredentialsResponse {
  success: boolean;
  message: string;
  latency_ms?: number;
}

// Email Report Types
export interface EmailReportRequest {
  report_type: 'time_report' | 'team_timesheet';
  start_date: string;
  end_date: string;
  recipients: string[];
  format: 'pdf' | 'excel' | 'csv';
  custom_message?: string;
}

export interface EmailReportResponse {
  success: boolean;
  message: string;
  recipients_sent: number;
  recipients_failed: number;
}

export const companiesApi = {
  getMyCompany: async (): Promise<Company> => {
    const response = await api.get('/api/companies/my-company');
    return response.data;
  },

  getBillingStatus: async (): Promise<BillingStatus> => {
    const response = await api.get('/api/companies/my-company/billing/status');
    return response.data;
  },

  upgradeBilling: async (): Promise<CompanyBillingUpgradeResponse> => {
    const response = await api.post('/api/companies/my-company/billing/upgrade');
    return response.data;
  },

  switchToUnlimited: async (): Promise<CompanyBillingSwitchResponse> => {
    const response = await api.post('/api/companies/my-company/billing/switch-to-unlimited');
    return response.data;
  },

  updateMyCompany: async (data: CompanyUpdate): Promise<Company> => {
    const response = await api.put('/api/companies/my-company', data);
    return response.data;

  },

  // Email Settings API
  getEmailSettings: async (): Promise<EmailSettings> => {
    const response = await api.get('/api/companies/my-company/email-settings');
    return response.data;
  },

  updateEmailSettings: async (data: EmailSettingsUpdate): Promise<EmailSettings> => {
    const response = await api.put('/api/companies/my-company/email-settings', data);
    return response.data;
  },

  sendTestEmail: async (data: TestEmailRequest): Promise<TestEmailResponse> => {
    const response = await api.post('/api/companies/my-company/email-settings/test', data);
    return response.data;
  },

  sendWelcomeCredentials: async (data: WelcomeCredentialsRequest): Promise<WelcomeCredentialsResponse> => {
    const response = await api.post('/api/companies/my-company/email-settings/send-welcome-credentials', data);
    return response.data;
  },
};

// ============================================
// REPORTS EMAIL API
// ============================================
export const reportsEmailApi = {
  sendReport: async (data: EmailReportRequest): Promise<EmailReportResponse> => {
    const response = await api.post('/api/reports/email', data);
    return response.data;
  },
};

// ============================================
// ADMIN API (TASK-009, TASK-010, TASK-022)
// ============================================
export const adminApi = {
  getTimeEntries: async (params: {
    start_date: string;
    end_date: string;
    user_id?: number;
    team_id?: number;
    project_id?: number;
  }) => {
    const response = await api.get('/api/admin/time-entries', { params });
    return response.data;
  },

  getWorkersReport: async (params?: {
    start_date?: string;
    end_date?: string;
    team_id?: number;
  }) => {
    const response = await api.get('/api/admin/workers-report', { params });
    return response.data;
  },

  getActivityAlerts: async () => {
    const response = await api.get('/api/admin/activity-alerts');
    return response.data;
  },
};

// ============================================
// WORK SESSIONS API (Micro-Task Management)
// ============================================
import type {
  WorkSession,
  SessionBreak,
  SessionMeeting,
  SessionBreakCreate,
  SessionMeetingCreate,
  SessionStatusResponse,
} from '../types';

export const sessionsApi = {
  // Get current session status
  getCurrentSession: async (): Promise<SessionStatusResponse> => {
    const response = await api.get<SessionStatusResponse>('/api/work-sessions/current');
    return response.data;
  },

  // Start a new work session (clock in)
  startSession: async (): Promise<WorkSession> => {
    const response = await api.post<WorkSession>('/api/work-sessions/start');
    return response.data;
  },

  // End current work session (clock out)
  endSession: async (): Promise<WorkSession> => {
    const response = await api.post<WorkSession>('/api/work-sessions/end');
    return response.data;
  },

  // Get session details by ID
  getSession: async (sessionId: number): Promise<WorkSession> => {
    const response = await api.get<WorkSession>(`/api/work-sessions/${sessionId}`);
    return response.data;
  },

  // Start a break
  startBreak: async (data: SessionBreakCreate): Promise<SessionBreak> => {
    const response = await api.post<SessionBreak>('/api/work-sessions/break/start', data);
    return response.data;
  },

  // End current break
  endBreak: async (): Promise<SessionBreak> => {
    const response = await api.post<SessionBreak>('/api/work-sessions/break/end');
    return response.data;
  },

  // Start a meeting
  startMeeting: async (data: SessionMeetingCreate): Promise<SessionMeeting> => {
    const response = await api.post<SessionMeeting>('/api/work-sessions/meeting/start', data);
    return response.data;
  },

  // End current meeting
  endMeeting: async (): Promise<SessionMeeting> => {
    const response = await api.post<SessionMeeting>('/api/work-sessions/meeting/end');
    return response.data;
  },
};

