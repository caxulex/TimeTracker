// ============================================
// TIME TRACKER - TIMER WIDGET TESTS
// Phase 7: Testing - Timer component tests
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '../../test/utils';
import { TimerWidget } from './TimerWidget';

// Mock the stores and APIs
vi.mock('../../stores/timerStore', () => ({
  useTimerStore: vi.fn(() => ({
    currentEntry: null,
    isRunning: false,
    elapsedSeconds: 0,
    isLoading: false,
    error: null,
    fetchTimer: vi.fn(),
    startTimer: vi.fn(),
    stopTimer: vi.fn(),
    updateElapsed: vi.fn(),
    clearError: vi.fn(),
  })),
}));

vi.mock('../../hooks/useNotifications', () => ({
  useNotifications: () => ({
    addNotification: vi.fn(),
  }),
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(({ queryKey }) => {
    if (queryKey[0] === 'projects') {
      return {
        data: {
          items: [
            { id: 1, name: 'Project A', color: '#3B82F6' },
            { id: 2, name: 'Project B', color: '#10B981' },
          ],
        },
        isLoading: false,
      };
    }
    return { data: { items: [] }, isLoading: false };
  }),
}));

describe('TimerWidget Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders timer display', () => {
    render(<TimerWidget />);
    
    // Should show time display (00:00:00 format)
    expect(screen.getByText(/\d{2}:\d{2}:\d{2}/)).toBeInTheDocument();
  });

  it('renders project selector', () => {
    render(<TimerWidget />);
    
    // Should show project select
    const projectSelect = screen.getByRole('combobox');
    expect(projectSelect).toBeInTheDocument();
  });

  it('renders description input', () => {
    render(<TimerWidget />);
    
    const input = screen.getByPlaceholderText(/what are you working on/i);
    expect(input).toBeInTheDocument();
  });

  it('renders start button when not running', async () => {
    render(<TimerWidget />);
    
    const startButton = screen.getByRole('button', { name: /start/i });
    expect(startButton).toBeInTheDocument();
  });

  it('allows description input when not running', () => {
    render(<TimerWidget />);
    
    const input = screen.getByPlaceholderText(/what are you working on/i);
    fireEvent.change(input, { target: { value: 'Working on feature' } });
    
    expect(input).toHaveValue('Working on feature');
  });

  it('shows error when starting without project selected', async () => {
    render(<TimerWidget />);
    
    // Click start without selecting project
    const startButton = screen.getByRole('button', { name: /start/i });
    fireEvent.click(startButton);
    
    // Should show error message about selecting project
    await waitFor(() => {
      expect(screen.getByText(/select a project/i)).toBeInTheDocument();
    });
  });
});

describe('TimerWidget - Running State', () => {
  beforeEach(() => {
    // Mock running state
    const mockUseTimerStore = vi.fn(() => ({
      currentEntry: {
        id: 1,
        description: 'Working on tests',
        project_id: 1,
        is_running: true,
      },
      isRunning: true,
      elapsedSeconds: 3661, // 1:01:01
      isLoading: false,
      error: null,
      fetchTimer: vi.fn(),
      startTimer: vi.fn(),
      stopTimer: vi.fn().mockResolvedValue({ duration_seconds: 3661 }),
      updateElapsed: vi.fn(),
      clearError: vi.fn(),
    }));
    
    vi.doMock('../../stores/timerStore', () => ({
      useTimerStore: mockUseTimerStore,
    }));
  });

  it('shows stop button when running', async () => {
    // This test would show Stop button in running state
    // The actual implementation depends on the mocked state
  });
});
