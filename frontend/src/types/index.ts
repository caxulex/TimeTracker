// ============================================
// TIME TRACKER - TYPE DEFINITIONS
// ============================================

// User Types
export interface User {
  id: number;
  email: string;
  name: string;
  role: 'super_admin' | 'admin' | 'company_admin' | 'regular_user' | 'member';
  is_active: boolean;
  created_at: string;
  
  // Contact Information
  phone?: string;
  address?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  
  // Employment Details
  job_title?: string;
  department?: string;
  employment_type?: 'full_time' | 'part_time' | 'contractor';
  start_date?: string;
  expected_hours_per_week?: number;
  manager_id?: number;
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
  // Contact Information
  phone?: string;
  address?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  
  // Employment Details
  job_title?: string;
  department?: string;
  employment_type?: 'full_time' | 'part_time' | 'contractor';
  start_date?: string;
  expected_hours_per_week?: number;
  manager_id?: number;
  
  // Payroll
  pay_rate?: number;
  pay_rate_type?: 'hourly' | 'daily' | 'monthly' | 'project_based';
  overtime_multiplier?: number;
  currency?: string;
  
  // Team assignment
  team_ids?: number[];
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
  // Budget fields (admin only)
  budget_amount?: number | null;
  deadline?: string | null;
}

export interface ProjectCreate {
  team_id: number;
  name: string;
  description?: string;
  color?: string;
  // Budget fields (admin only)
  budget_amount?: number | null;
  deadline?: string | null;
}

export interface ProjectUpdate {
  name?: string;
  description?: string | null;
  color?: string;
  is_archived?: boolean;
  // Budget fields (admin only)
  budget_amount?: number | null;
  deadline?: string | null;
  budget_change_reason?: string;
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
  // Basecamp-sourced disambiguation metadata (null for native tasks).
  basecamp_due_on?: string | null;
  basecamp_todo_created_at?: string | null;
  basecamp_todo_position?: number | null;
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
  project_name?: string | null;
  project_color?: string | null;
  task_id: number | null;
  start_time: string;
  end_time: string | null;
  duration_seconds: number;
  description: string | null;
  is_running: boolean;
  is_manual?: boolean;
  // Pause tracking for breaks/meetings
  is_paused?: boolean;
  paused_at?: string | null;
  pause_seconds?: number;
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
  current_entry?: TimeEntry;
  elapsed_seconds?: number;
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

// Team Timesheet Types
export interface TeamTimesheetUserEntry {
  date: string;
  seconds: number;
  formatted: string;
}

export interface TeamTimesheetUser {
  user_id: number;
  user_name: string;
  role: string;
  daily_hours: TeamTimesheetUserEntry[];
  total_seconds: number;
  total_formatted: string;
}

export interface TeamTimesheetDayTotal {
  date: string;
  seconds: number;
  formatted: string;
}

export interface TeamTimesheetReport {
  start_date: string;
  end_date: string;
  dates: string[];
  users: TeamTimesheetUser[];
  daily_totals: TeamTimesheetDayTotal[];
  grand_total_seconds: number;
  grand_total_formatted: string;
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
  user_id?: number;
  project_id?: number;
  task_id?: number;
  start_date?: string;
  end_date?: string;
  page?: number;
  // Backend (`GET /api/time`) declares the query param as `page_size`.
  // `size` is kept for back-compat with other paginated endpoints but is
  // ignored by the time-entries endpoint — pass `page_size` for that one.
  page_size?: number;
  size?: number;
}

export interface ProjectFilters {
  team_id?: number;
  include_archived?: boolean;
  search?: string;
  page?: number;
  size?: number;
  // Backend's actual query-param name (see app/routers/projects.py). The
  // `size` field above is kept for any legacy callsites but the server
  // only honors `page_size`. PR fix/entry-project-label-from-response.
  page_size?: number;
}

export interface TaskFilters {
  project_id?: number;
  status?: TaskStatus;
  page?: number;
  /** @deprecated Use `page_size`. Backend (app/routers/tasks.py) only honors `page_size`. */
  size?: number;
  page_size?: number;
}

// ============================================
// MICRO-TASK SESSION TYPES
// ============================================

export type SessionStatus = 'active' | 'break' | 'meeting' | 'completed';
export type BreakType = 'short' | 'lunch' | 'other';
export type MeetingType = 'internal' | 'external' | 'client';

export interface SessionBreak {
  id: number;
  work_session_id: number;
  break_type: BreakType;
  start_time: string;
  end_time?: string;
  duration_seconds?: number;
}

export interface SessionMeeting {
  id: number;
  work_session_id: number;
  title?: string;
  meeting_type: MeetingType;
  start_time: string;
  end_time?: string;
  duration_seconds?: number;
}

export interface WorkSession {
  id: number;
  user_id: number;
  company_id?: number;
  start_time: string;
  end_time?: string;
  status: SessionStatus;
  total_work_seconds: number;
  total_break_seconds: number;
  total_meeting_seconds: number;
  created_at: string;
  updated_at: string;
  breaks?: SessionBreak[];
  meetings?: SessionMeeting[];
}

export interface SessionBreakCreate {
  break_type: BreakType;
}

export interface SessionMeetingCreate {
  title?: string;
  meeting_type: MeetingType;
}

export interface SessionStatusResponse {
  has_active_session: boolean;
  session?: WorkSession;  // Backend returns 'session' not 'current_session'
  current_status: string; // "working", "break", "meeting", "idle"
  global_timer_seconds: number;
  task_timer_seconds: number;
  current_break?: SessionBreak;  // Backend returns 'current_break'
  current_meeting?: SessionMeeting;  // Backend returns 'current_meeting'
}

// Export payroll types
export * from './payroll';

// Export API key types
export * from './apiKey';
