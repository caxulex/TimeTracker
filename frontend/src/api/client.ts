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
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If 401 and we haven't retried yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post<AuthToken>(`${API_BASE_URL}/api/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token } = response.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', refresh_token);

          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${access_token}`;
          }
          return api(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, clear tokens and redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
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
    await api.post('/api/auth/logout');
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
  getAll: async (page = 1, size = 20): Promise<PaginatedResponse<User>> => {
    const response = await api.get<PaginatedResponse<User>>('/api/users', {
      params: { page, size },
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

  updateRole: async (id: number, role: string): Promise<User> => {
    const response = await api.put<User>(`/api/users/${id}/role`, { role });
    return response.data;
  },
};

// ============================================
// TEAMS API
// ============================================
export const teamsApi = {
  getAll: async (page = 1, size = 20): Promise<PaginatedResponse<Team>> => {
    const response = await api.get<PaginatedResponse<Team>>('/api/teams', {
      params: { page, size },
    });
    return response.data;
  },

  getById: async (id: number): Promise<Team & { members: TeamMember[] }> => {
    const response = await api.get<Team & { members: TeamMember[] }>(`/api/teams/${id}`);
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

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/teams/${id}`);
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

  update: async (id: number, data: ProjectUpdate): Promise<Project> => {
    const response = await api.put<Project>(`/api/projects/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/projects/${id}`);
  },

  restore: async (id: number): Promise<Project> => {
    const response = await api.post<Project>(`/api/projects/${id}/restore`);
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

  getActiveTimers: async (): Promise<any[]> => {
    const response = await api.get<any[]>('/api/time/active');
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

  getWeekly: async (startDate?: string): Promise<WeeklySummary> => {
    const response = await api.get<WeeklySummary>('/api/reports/weekly', {
      params: startDate ? { start_date: startDate } : undefined,
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

  getAdminDashboard: async () => {
    const response = await api.get('/api/reports/admin/dashboard');
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
    const response = await api.get('/api/export/excel', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },

  downloadPdf: async (params?: {
    start_date?: string;
    end_date?: string;
    project_id?: number;
    user_id?: number;
  }): Promise<Blob> => {
    const response = await api.get('/api/export/pdf', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },

  downloadCsv: async (params?: {
    start_date?: string;
    end_date?: string;
    project_id?: number;
    user_id?: number;
  }): Promise<Blob> => {
    const response = await api.get('/api/export/csv', {
      params,
      responseType: 'blob',
    });
    return response.data;
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

  getAll: async (page = 1, limit = 100, activeOnly = true) => {
    const response = await api.get('/api/pay-rates', {
      params: { skip: (page - 1) * limit, limit, active_only: activeOnly },
    });
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/api/pay-rates', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
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

