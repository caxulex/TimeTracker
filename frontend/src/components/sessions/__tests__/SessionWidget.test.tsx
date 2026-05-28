// ============================================
// TIME TRACKER - SESSION WIDGET TESTS
// Covers the clock-in flow with the ProjectSelect
// typeahead and TaskSelect auto-clear behavior.
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SessionWidget } from '../SessionWidget';
import type { Project, Task } from '../../../types';

const mockAddNotification = vi.fn();
const mockFetchCurrentSession = vi.fn();
const mockStartSession = vi.fn();
const mockEndSession = vi.fn();
const mockUpdateElapsedTimes = vi.fn();
const mockClearSessionError = vi.fn();
const mockFetchTimer = vi.fn();
const mockStartTimer = vi.fn();
const mockStopTimer = vi.fn();
const mockUpdateElapsed = vi.fn();
const mockClearTimerError = vi.fn();

vi.mock('../../../hooks/useNotifications', () => ({
  useNotifications: () => ({
    addNotification: mockAddNotification,
  }),
}));

vi.mock('../../../stores/sessionStore', async () => {
  const actual = await vi.importActual<typeof import('../../../stores/sessionStore')>(
    '../../../stores/sessionStore'
  );
  return {
    ...actual,
    useSessionStore: vi.fn(),
  };
});

vi.mock('../../../stores/timerStore', async () => {
  const actual = await vi.importActual<typeof import('../../../stores/timerStore')>(
    '../../../stores/timerStore'
  );
  return {
    ...actual,
    useTimerStore: vi.fn(),
  };
});

vi.mock('../../../api/client', () => ({
  projectsApi: {
    getAll: vi.fn(),
  },
  tasksApi: {
    getAll: vi.fn(),
  },
}));

import { projectsApi, tasksApi } from '../../../api/client';
import { useSessionStore } from '../../../stores/sessionStore';
import { useTimerStore } from '../../../stores/timerStore';

const makeProject = (overrides: Partial<Project>): Project => ({
  id: 1,
  name: 'Project',
  description: null,
  team_id: 1,
  team_name: 'Team',
  color: '#3B82F6',
  is_archived: false,
  created_at: new Date().toISOString(),
  updated_at: null,
  task_count: 0,
  ...overrides,
} as Project);

const projects: Project[] = [
  makeProject({ id: 1, name: 'Alpha' }),
  makeProject({ id: 2, name: 'Bravo' }),
  makeProject({ id: 3, name: 'Development' }),
  makeProject({ id: 4, name: 'Other thing' }),
];

const makeTask = (overrides: Partial<Task>): Task => ({
  id: 10,
  project_id: 1,
  name: 'Task',
  description: null,
  status: 'TODO',
  created_at: new Date().toISOString(),
  basecamp_due_on: null,
  basecamp_todo_created_at: null,
  basecamp_todo_position: null,
  ...overrides,
} as Task);

const tasks: Task[] = [
  makeTask({ id: 10, project_id: 1, name: 'Design mockups' }),
  makeTask({ id: 11, project_id: 1, name: 'Implement login' }),
  makeTask({ id: 12, project_id: 1, name: 'Write docs' }),
];

const activeSession = {
  id: 99,
  user_id: 1,
  company_id: 1,
  start_time: new Date().toISOString(),
  end_time: null,
  status: 'active' as const,
  total_break_seconds: 0,
  total_meeting_seconds: 0,
  created_at: new Date().toISOString(),
  updated_at: null,
};

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
}

function renderWidget() {
  const queryClient = makeClient();
  render(
    <QueryClientProvider client={queryClient}>
      <SessionWidget />
    </QueryClientProvider>
  );
  return { queryClient };
}

describe('SessionWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useSessionStore).mockReturnValue({
      currentSession: null,
      activeBreak: null,
      activeMeeting: null,
      isLoading: false,
      error: null,
      lastSyncTime: null,
      sessionElapsedSeconds: 0,
      breakElapsedSeconds: 0,
      meetingElapsedSeconds: 0,
      fetchCurrentSession: mockFetchCurrentSession,
      startSession: mockStartSession,
      endSession: mockEndSession,
      startBreak: vi.fn(),
      endBreak: vi.fn(),
      startMeeting: vi.fn(),
      endMeeting: vi.fn(),
      updateElapsedTimes: mockUpdateElapsedTimes,
      clearError: mockClearSessionError,
      handleSessionStarted: vi.fn(),
      handleSessionEnded: vi.fn(),
      handleBreakStarted: vi.fn(),
      handleBreakEnded: vi.fn(),
      handleMeetingStarted: vi.fn(),
      handleMeetingEnded: vi.fn(),
    });

    vi.mocked(useTimerStore).mockReturnValue({
      currentEntry: null,
      isRunning: false,
      isPaused: false,
      elapsedSeconds: 0,
      isLoading: false,
      error: null,
      lastSyncTime: null,
      fetchTimer: mockFetchTimer,
      startTimer: mockStartTimer,
      stopTimer: mockStopTimer,
      switchTimer: vi.fn(),
      updateElapsed: mockUpdateElapsed,
      clearError: mockClearTimerError,
      syncWithBackend: vi.fn(),
    });

    vi.mocked(projectsApi.getAll).mockResolvedValue({
      items: projects,
      total: projects.length,
      page: 1,
      size: 100,
      pages: 1,
    });

    vi.mocked(tasksApi.getAll).mockResolvedValue({
      items: tasks,
      total: tasks.length,
      page: 1,
      size: 100,
      pages: 1,
    });
  });

  it('renders the ProjectSelect typeahead and filters projects as the user types', async () => {
    const user = userEvent.setup();
    renderWidget();

    await user.click(screen.getByRole('button', { name: /clock in/i }));

    await waitFor(() => {
      expect(projectsApi.getAll).toHaveBeenCalledWith({
        include_archived: false,
        page_size: 100,
      });
    });

    const projectInput = await screen.findByLabelText(/project/i);
    await user.click(projectInput);
    await user.type(projectInput, 'dev');

    expect(screen.getByTestId('project-select-option-3')).toBeInTheDocument();
    expect(screen.queryByTestId('project-select-option-1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('project-select-option-2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('project-select-option-4')).not.toBeInTheDocument();
  });

  it('clears the selected task when the project changes via typeahead', async () => {
    const user = userEvent.setup();
    renderWidget();

    await user.click(screen.getByRole('button', { name: /clock in/i }));

    const projectInput = await screen.findByLabelText(/project/i);
    await user.click(projectInput);
    await user.type(projectInput, 'alpha');
    fireEvent.mouseDown(await screen.findByTestId('project-select-option-1'));

    await waitFor(() => {
      expect(tasksApi.getAll).toHaveBeenCalledWith({ project_id: 1, page_size: 100 });
    });

    const taskInput = await screen.findByLabelText(/task/i);
    fireEvent.focus(taskInput);
    fireEvent.mouseDown(await screen.findByTestId('task-select-option-11'));
    expect(taskInput).toHaveValue('Implement login');

    await user.click(projectInput);
    await user.clear(projectInput);
    await user.type(projectInput, 'development');
    fireEvent.mouseDown(await screen.findByTestId('project-select-option-3'));

    await waitFor(() => {
      expect(tasksApi.getAll).toHaveBeenCalledWith({ project_id: 3, page_size: 100 });
    });

    await waitFor(() => {
      expect(taskInput).toHaveValue('');
    });
  });

  it('starts the session with the project selected through typeahead', async () => {
    const user = userEvent.setup();
    mockStartSession.mockResolvedValueOnce(undefined);
    mockStartTimer.mockResolvedValueOnce(undefined);

    renderWidget();

    await user.click(screen.getByRole('button', { name: /clock in/i }));

    const projectInput = await screen.findByLabelText(/project/i);
    await user.click(projectInput);
    await user.type(projectInput, 'development');
    fireEvent.mouseDown(await screen.findByTestId('project-select-option-3'));

    const startButton = screen.getByRole('button', { name: /start working/i });
    await user.click(startButton);

    await waitFor(() => {
      expect(mockStartSession).toHaveBeenCalledTimes(1);
      expect(mockStartTimer).toHaveBeenCalledWith({
        description: undefined,
        project_id: 3,
        task_id: undefined,
      });
    });
  });

  it('clock out continues when stopTimer returns 404 no-running and still ends session', async () => {
    const user = userEvent.setup();
    const stop404 = {
      isAxiosError: true,
      response: {
        status: 404,
        data: {
          detail: 'No running timer found',
        },
      },
    };

    vi.mocked(useSessionStore).mockReturnValue({
      currentSession: activeSession,
      activeBreak: null,
      activeMeeting: null,
      isLoading: false,
      error: null,
      lastSyncTime: null,
      sessionElapsedSeconds: 3600,
      breakElapsedSeconds: 0,
      meetingElapsedSeconds: 0,
      fetchCurrentSession: mockFetchCurrentSession,
      startSession: mockStartSession,
      endSession: mockEndSession,
      startBreak: vi.fn(),
      endBreak: vi.fn(),
      startMeeting: vi.fn(),
      endMeeting: vi.fn(),
      updateElapsedTimes: mockUpdateElapsedTimes,
      clearError: mockClearSessionError,
      handleSessionStarted: vi.fn(),
      handleSessionEnded: vi.fn(),
      handleBreakStarted: vi.fn(),
      handleBreakEnded: vi.fn(),
      handleMeetingStarted: vi.fn(),
      handleMeetingEnded: vi.fn(),
    });

    vi.mocked(useTimerStore).mockReturnValue({
      currentEntry: null,
      isRunning: true,
      isPaused: false,
      elapsedSeconds: 10,
      isLoading: false,
      error: null,
      lastSyncTime: null,
      fetchTimer: mockFetchTimer,
      startTimer: mockStartTimer,
      stopTimer: mockStopTimer,
      switchTimer: vi.fn(),
      updateElapsed: mockUpdateElapsed,
      clearError: mockClearTimerError,
      syncWithBackend: vi.fn(),
    });

    mockStopTimer.mockRejectedValueOnce(stop404);
    mockEndSession.mockResolvedValueOnce(undefined);
    mockFetchTimer.mockResolvedValue(undefined);

    renderWidget();
    mockFetchTimer.mockClear();
    mockFetchCurrentSession.mockClear();

    await user.click(screen.getByRole('button', { name: /clock out/i }));

    await waitFor(() => {
      expect(mockStopTimer).toHaveBeenCalledTimes(1);
      expect(mockEndSession).toHaveBeenCalledTimes(1);
      expect(mockFetchTimer).toHaveBeenCalledWith(true);
    });

    expect(mockAddNotification).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'success',
        title: 'Clocked Out!',
      })
    );
    expect(mockAddNotification).not.toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'error',
        title: 'Failed to Clock Out',
      })
    );
  });

  it('clock out fails on non-404 stopTimer error and does not end session', async () => {
    const user = userEvent.setup();

    vi.mocked(useSessionStore).mockReturnValue({
      currentSession: activeSession,
      activeBreak: null,
      activeMeeting: null,
      isLoading: false,
      error: null,
      lastSyncTime: null,
      sessionElapsedSeconds: 3600,
      breakElapsedSeconds: 0,
      meetingElapsedSeconds: 0,
      fetchCurrentSession: mockFetchCurrentSession,
      startSession: mockStartSession,
      endSession: mockEndSession,
      startBreak: vi.fn(),
      endBreak: vi.fn(),
      startMeeting: vi.fn(),
      endMeeting: vi.fn(),
      updateElapsedTimes: mockUpdateElapsedTimes,
      clearError: mockClearSessionError,
      handleSessionStarted: vi.fn(),
      handleSessionEnded: vi.fn(),
      handleBreakStarted: vi.fn(),
      handleBreakEnded: vi.fn(),
      handleMeetingStarted: vi.fn(),
      handleMeetingEnded: vi.fn(),
    });

    vi.mocked(useTimerStore).mockReturnValue({
      currentEntry: null,
      isRunning: true,
      isPaused: false,
      elapsedSeconds: 10,
      isLoading: false,
      error: null,
      lastSyncTime: null,
      fetchTimer: mockFetchTimer,
      startTimer: mockStartTimer,
      stopTimer: mockStopTimer,
      switchTimer: vi.fn(),
      updateElapsed: mockUpdateElapsed,
      clearError: mockClearTimerError,
      syncWithBackend: vi.fn(),
    });

    mockStopTimer.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 500,
        data: {
          detail: 'Server error',
        },
      },
    });

    renderWidget();
    mockFetchTimer.mockClear();

    await user.click(screen.getByRole('button', { name: /clock out/i }));

    await waitFor(() => {
      expect(mockStopTimer).toHaveBeenCalledTimes(1);
      expect(mockEndSession).not.toHaveBeenCalled();
    });

    expect(mockAddNotification).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'error',
        title: 'Failed to Clock Out',
      })
    );
  });
});
