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
    it('should call startTimer when start button is clicked', async () => {
      const user = userEvent.setup();
      mockStartTimer.mockResolvedValueOnce({});

      render(
        <TestWrapper>
          <TimerWidget />
        </TestWrapper>
      );

      await waitFor(async () => {
        const startButton = screen.getByRole('button', { name: /start/i });
        await user.click(startButton);
      });

      // Start timer should have been called
      await waitFor(() => {
        expect(mockStartTimer).toHaveBeenCalled();
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
});
