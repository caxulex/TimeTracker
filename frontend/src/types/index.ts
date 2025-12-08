// ============================================
// TIME TRACKER - TYPE DEFINITIONS
// ============================================

// User Types
export interface User {
  id: number;
  email: string;
  name: string;
  role: 'super_admin' | 'admin' | 'regular_user' | 'member';
  is_active: boolean;
  created_at: string;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface UserRegister {
  email: string;
  password: string;
  name: string;
}

export interface UserCreate extends UserRegister {
  role?: string;
}

// Auth Types
export interface AuthToken {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// Team Types
export interface Team {
  id: number;
  name: string;
  owner_id: number;
  created_at: string;
  member_count?: number;
}

export interface TeamMember {
  user_id: number;
  team_id: number;
  role: 'admin' | 'member';
  joined_at: string;
  user?: User;
}

export interface TeamCreate {
  name: string;
}

export interface TeamUpdate {
  name?: string;
}

// Project Types
export interface Project {
  id: number;
  team_id: number;
  name: string;
  description: string | null;
  color: string;
  is_archived: boolean;
  created_at: string;
  team?: Team;
}

export interface ProjectCreate {
  team_id: number;
  name: string;
  description?: string;
  color?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string | null;
  color?: string;
  is_archived?: boolean;
}

// Task Types
export type TaskStatus = 'TODO' | 'IN_PROGRESS' | 'DONE';

export interface Task {
  id: number;
  project_id: number;
  name: string;
  description: string | null;
  status: TaskStatus;
  created_at: string;
  project?: Project;
}

export interface TaskCreate {
  project_id: number;
  name: string;
  description?: string;
  status?: TaskStatus;
}

export interface TaskUpdate {
  name?: string;
  description?: string | null;
  status?: TaskStatus;
}

// Time Entry Types
export interface TimeEntry {
  id: number;
  user_id: number;
  project_id: number | null;
  task_id: number | null;
  start_time: string;
  end_time: string | null;
  duration_seconds: number;
  description: string | null;
  is_running: boolean;
  is_manual?: boolean;
  created_at: string;
  project?: Project;
  task?: Task;
}

export interface TimeEntryCreate {
  project_id?: number;
  task_id?: number;
  start_time?: string;
  end_time?: string | null;
  description?: string;
  is_manual?: boolean;
}

export interface TimeEntryUpdate {
  project_id?: number | null;
  task_id?: number | null;
  start_time?: string;
  end_time?: string | null;
  description?: string | null;
}

export interface TimerStart {
  project_id?: number;
  task_id?: number;
  description?: string;
  is_manual?: boolean;
}

export interface TimerStatus {
  is_running: boolean;
  is_manual?: boolean;
  entry?: TimeEntry;
}

// Dashboard Types
export interface DashboardStats {
  today_seconds: number;
  week_seconds: number;
  month_seconds: number;
  active_projects: number;
  running_timer?: TimeEntry;
}

export interface DailySummary {
  date: string;
  total_seconds: number;
  entry_count: number;
}

export interface WeeklySummary {
  week_start: string;
  week_end: string;
  total_seconds: number;
  total_hours: number;
  daily_breakdown: DailySummary[];
}

export interface ProjectSummary {
  project_id: number;
  project_name: string;
  total_seconds: number;
  percentage: number;
}

// Pagination Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// API Error Types
export interface APIError {
  detail: string | ValidationError[];
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

// Filter Types
export interface TimeEntryFilters {
  project_id?: number;
  task_id?: number;
  start_date?: string;
  end_date?: string;
  page?: number;
  size?: number;
}

export interface ProjectFilters {
  team_id?: number;
  is_archived?: boolean;
  page?: number;
  size?: number;
}

export interface TaskFilters {
  project_id?: number;
  status?: TaskStatus;
  page?: number;
  size?: number;
}

// Export payroll types
export * from './payroll';
