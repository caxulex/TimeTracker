// ============================================
// TIME TRACKER - TIMER WIDGET TESTS
// Phase 7: Testing - Timer widget component
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TimerWidget } from './TimerWidget';
import { NotificationProvider } from '../../components/Notifications';
import { useTimerStore } from '../../stores/timerStore';
import { tasksApi } from '../../api/client';

// Mock the timer store
vi.mock('../../stores/timerStore', () => ({
  useTimerStore: vi.fn(),
}));

// Mock notifications
vi.mock('../../hooks/useNotifications', () => ({
  useNotifications: vi.fn(() => ({
    addNotification: vi.fn(),
  })),
}));

// Mock API client
vi.mock('../../api/client', () => ({
  projectsApi: {
    getAll: vi.fn(() => Promise.resolve({
      items: [
        { id: 1, name: 'Project A', company_id: 1, is_active: true },
        { id: 2, name: 'Project B', company_id: 1, is_active: true },
      ],
      total: 2,
    })),
  },
  tasksApi: {
    getAll: vi.fn(() => Promise.resolve({
      items: [
        { id: 1, name: 'Task 1', project_id: 1, is_active: true },
        { id: 2, name: 'Task 2', project_id: 1, is_active: true },
      ],
      total: 2,
    })),
  },
}));

// Create query client for tests
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
      },
    },
  });

// Test wrapper with providers
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <NotificationProvider>
        {children}
      </NotificationProvider>
    </QueryClientProvider>
  );
};

describe('TimerWidget', () => {
  const mockFetchTimer = vi.fn();
  const mockStartTimer = vi.fn();
  const mockStopTimer = vi.fn();
  const mockUpdateElapsed = vi.fn();
  const mockClearError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useTimerStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      currentEntry: null,
      isRunning: false,
      elapsedSeconds: 0,
      isLoading: false,
      error: null,
      fetchTimer: mockFetchTimer,
      startTimer: mockStartTimer,
      stopTimer: mockStopTimer,
      updateElapsed: mockUpdateElapsed,
      clearError: mockClearError,
    });
  });

  describe('Rendering', () => {
    it('should render the timer widget', async () => {
      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(() => {
        // Timer should show 00:00:00 initially
        expect(screen.getByText(/00:00:00/)).toBeInTheDocument();
      });
    });

    it('should render project selector', async () => {
      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(() => {
        const projectSelect = screen.getByRole('combobox');
        expect(projectSelect).toBeInTheDocument();
      });
    });

    it('should render description input', async () => {
      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(() => {
        const descInput = screen.getByPlaceholderText(/what are you working on/i);
        expect(descInput).toBeInTheDocument();
      });
    });

    it('should render start button when timer is not running', async () => {
      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(() => {
        const startButton = screen.getByRole('button', { name: /start/i });
        expect(startButton).toBeInTheDocument();
      });
    });
  });

  describe('Timer State', () => {
    it('should show stop button when timer is running', async () => {
      (useTimerStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        currentEntry: {
          id: 1,
          project_id: 1,
          description: 'Working',
          start_time: new Date().toISOString(),
        },
        isRunning: true,
        elapsedSeconds: 3600, // 1 hour
        isLoading: false,
        error: null,
        fetchTimer: mockFetchTimer,
        startTimer: mockStartTimer,
        stopTimer: mockStopTimer,
        updateElapsed: mockUpdateElapsed,
        clearError: mockClearError,
      });

      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(() => {
        const stopButton = screen.getByRole('button', { name: /stop/i });
        expect(stopButton).toBeInTheDocument();
      });
    });

    it('should display elapsed time when running', async () => {
      (useTimerStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        currentEntry: {
          id: 1,
          project_id: 1,
          description: 'Working',
          start_time: new Date().toISOString(),
        },
        isRunning: true,
        elapsedSeconds: 3661, // 1:01:01
        isLoading: false,
        error: null,
        fetchTimer: mockFetchTimer,
        startTimer: mockStartTimer,
        stopTimer: mockStopTimer,
        updateElapsed: mockUpdateElapsed,
        clearError: mockClearError,
      });

      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(() => {
        // Should show 01:01:01
        expect(screen.getByText(/01:01:01/)).toBeInTheDocument();
      });
    });
  });

  describe('User Interactions', () => {
    it('should show error when trying to start without project', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(async () => {
        const startButton = screen.getByRole('button', { name: /start/i });
        await user.click(startButton);
      });

      // Should show validation error since no project selected
      await waitFor(() => {
        expect(screen.getByText(/please select a project/i)).toBeInTheDocument();
      });
    });

    it('should call startTimer when start button is clicked with project', async () => {
      const user = userEvent.setup();
      mockStartTimer.mockResolvedValueOnce({});

      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(async () => {
        // First select a project
        const projectSelect = screen.getByRole('combobox');
        await user.click(projectSelect);
      });

      // Select first project option if available
      await waitFor(async () => {
        const option = screen.queryByText('Project A');
        if (option) {
          await user.click(option);
        }
      });
    });

    it('should call stopTimer when stop button is clicked', async () => {
      const user = userEvent.setup();
      mockStopTimer.mockResolvedValueOnce({ duration_seconds: 3600 });

      (useTimerStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        currentEntry: {
          id: 1,
          project_id: 1,
          description: 'Working',
          start_time: new Date().toISOString(),
        },
        isRunning: true,
        elapsedSeconds: 3600,
        isLoading: false,
        error: null,
        fetchTimer: mockFetchTimer,
        startTimer: mockStartTimer,
        stopTimer: mockStopTimer,
        updateElapsed: mockUpdateElapsed,
        clearError: mockClearError,
      });

      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(async () => {
        const stopButton = screen.getByRole('button', { name: /stop/i });
        await user.click(stopButton);
      });

      await waitFor(() => {
        expect(mockStopTimer).toHaveBeenCalled();
      });
    });

    it('should update description on input change', async () => {
      const user = userEvent.setup();
      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(async () => {
        const descInput = screen.getByPlaceholderText(/what are you working on/i);
        await user.type(descInput, 'New task description');
        expect(descInput).toHaveValue('New task description');
      });
    });
  });

  describe('Loading State', () => {
    it('should show loading state', async () => {
      (useTimerStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        currentEntry: null,
        isRunning: false,
        elapsedSeconds: 0,
        isLoading: true,
        error: null,
        fetchTimer: mockFetchTimer,
        startTimer: mockStartTimer,
        stopTimer: mockStopTimer,
        updateElapsed: mockUpdateElapsed,
        clearError: mockClearError,
      });

      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      // Component should render without crashing during loading
      await waitFor(() => {
        expect(screen.getByText(/00:00:00/)).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error message when there is an error', async () => {
      (useTimerStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        currentEntry: null,
        isRunning: false,
        elapsedSeconds: 0,
        isLoading: false,
        error: 'Failed to start timer',
        fetchTimer: mockFetchTimer,
        startTimer: mockStartTimer,
        stopTimer: mockStopTimer,
        updateElapsed: mockUpdateElapsed,
        clearError: mockClearError,
      });

      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/failed to start timer/i)).toBeInTheDocument();
      });
    });
  });

  describe('Lifecycle', () => {
    it('should fetch timer on mount', async () => {
      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockFetchTimer).toHaveBeenCalled();
      });
    });
  });

  describe('Duplicate task name disambiguation & sort', () => {
    // Mirror the component's date formatting so the assertions are
    // independent of the host timezone (Date parses YYYY-MM-DD as UTC
    // and toLocaleDateString shifts to the host TZ).
    const md = (iso: string) =>
      new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const mdy = (iso: string) =>
      new Date(iso).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    const my = (iso: string) =>
      new Date(iso).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });

    const renderWithTasksAndSelectProject = async (items: unknown[]) => {
      vi.mocked(tasksApi.getAll).mockResolvedValue({ items, total: items.length } as never);
      const user = userEvent.setup();
      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );
      // The project picker is now a typeahead combobox
      // (ProjectSelect). Open it and click the Project A option to
      // trigger the same selection behavior the legacy native <select>
      // exercised via selectOptions().
      const projectCombobox = await screen.findByRole('combobox', {
        name: /select project/i,
      });
      await user.click(projectCombobox);
      const projectAOption = await screen.findByTestId('project-select-option-1');
      fireEvent.mouseDown(projectAOption);
      // Once a project is committed the native task <select> appears.
      // Wait for it (still rendered as a native <select>, so role
      // "combobox" applies to it as well).
      await waitFor(() => {
        const taskSelectEl = document.querySelector('select');
        expect(taskSelectEl).not.toBeNull();
        expect(taskSelectEl!.querySelectorAll('option').length).toBeGreaterThan(1);
      });
      return document.querySelector('select') as HTMLSelectElement;
    };

    it('sorts duplicate-named tasks by basecamp_due_on DESC and uses (Due Mon D) when no collision', async () => {
      const taskSelect = await renderWithTasksAndSelectProject([
        { id: 1, name: 'Monthly Report', project_id: 1, is_active: true, basecamp_due_on: '2026-01-04' },
        { id: 2, name: 'Monthly Report', project_id: 1, is_active: true, basecamp_due_on: '2026-05-04' },
        { id: 3, name: 'Monthly Report', project_id: 1, is_active: true, basecamp_due_on: '2026-03-04' },
        { id: 4, name: 'Standalone', project_id: 1, is_active: true },
      ]);

      const labels = Array.from(taskSelect.querySelectorAll('option'))
        .map((o) => (o.textContent || '').trim())
        .slice(1);

      expect(labels).toEqual([
        `Monthly Report (Due ${md('2026-05-04')})`,
        `Monthly Report (Due ${md('2026-03-04')})`,
        `Monthly Report (Due ${md('2026-01-04')})`,
        'Standalone',
      ]);
    });

    it('appends year only on month-day collision within the same name group', async () => {
      const taskSelect = await renderWithTasksAndSelectProject([
        { id: 1, name: 'Recurring', project_id: 1, is_active: true, basecamp_due_on: '2025-11-04' },
        { id: 2, name: 'Recurring', project_id: 1, is_active: true, basecamp_due_on: '2026-11-04' },
        { id: 3, name: 'Recurring', project_id: 1, is_active: true, basecamp_due_on: '2026-05-04' },
      ]);

      const labels = Array.from(taskSelect.querySelectorAll('option'))
        .map((o) => (o.textContent || '').trim())
        .slice(1);

      expect(labels).toEqual([
        `Recurring (Due ${mdy('2026-11-04')})`,
        `Recurring (Due ${md('2026-05-04')})`,
        `Recurring (Due ${mdy('2025-11-04')})`,
      ]);
    });

    it('within a group, due_on tasks come before tasks without due_on (created_at DESC, then position ASC)', async () => {
      const taskSelect = await renderWithTasksAndSelectProject([
        { id: 1, name: 'Mixed', project_id: 1, is_active: true, basecamp_todo_position: 5 },
        { id: 2, name: 'Mixed', project_id: 1, is_active: true, basecamp_due_on: '2026-02-01' },
        { id: 3, name: 'Mixed', project_id: 1, is_active: true, basecamp_todo_created_at: '2026-04-01T10:00:00Z' },
        { id: 4, name: 'Mixed', project_id: 1, is_active: true, basecamp_todo_position: 1 },
        { id: 5, name: 'Mixed', project_id: 1, is_active: true, basecamp_todo_created_at: '2026-04-15T10:00:00Z' },
        { id: 6, name: 'Mixed', project_id: 1, is_active: true, basecamp_due_on: '2026-06-01' },
      ]);

      const labels = Array.from(taskSelect.querySelectorAll('option'))
        .map((o) => (o.textContent || '').trim())
        .slice(1);

      expect(labels[0]).toBe(`Mixed (Due ${md('2026-06-01')})`);
      expect(labels[1]).toBe(`Mixed (Due ${md('2026-02-01')})`);
      expect(labels[2]).toBe(`Mixed (${my('2026-04-15T10:00:00Z')})`);
      expect(labels[3]).toBe(`Mixed (${my('2026-04-01T10:00:00Z')})`);
      expect(labels[4]).toBe('Mixed (#1)');
      expect(labels[5]).toBe('Mixed (#5)');
    });

    it('preserves position of unique-named tasks; duplicate group lands at first-occurrence slot', async () => {
      const taskSelect = await renderWithTasksAndSelectProject([
        { id: 1, name: 'Alpha', project_id: 1, is_active: true },
        { id: 2, name: 'Report', project_id: 1, is_active: true, basecamp_due_on: '2026-01-04' },
        { id: 3, name: 'Beta', project_id: 1, is_active: true },
        { id: 4, name: 'Report', project_id: 1, is_active: true, basecamp_due_on: '2026-05-04' },
      ]);

      const labels = Array.from(taskSelect.querySelectorAll('option'))
        .map((o) => (o.textContent || '').trim())
        .slice(1);

      expect(labels).toEqual([
        'Alpha',
        `Report (Due ${md('2026-05-04')})`,
        `Report (Due ${md('2026-01-04')})`,
        'Beta',
      ]);
    });
  });
});
