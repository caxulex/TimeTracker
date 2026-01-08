// ============================================
// TIME TRACKER - TIMER STORE TESTS
// Phase 7: Testing - Zustand timer store
// ============================================
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act } from '@testing-library/react';
import type { TimeEntry, TimerStatus } from '../types';

// Mock the time entries API
vi.mock('../api/client', () => ({
  timeEntriesApi: {
    getTimer: vi.fn(),
    startTimer: vi.fn(),
    stopTimer: vi.fn(),
  },
}));

// Import after mocking
import { useTimerStore } from './timerStore';
import { timeEntriesApi } from '../api/client';

// Helper to create a valid TimeEntry for tests
const createMockEntry = (overrides: Partial<TimeEntry> = {}): TimeEntry => ({
  id: 1,
  user_id: 1,
  project_id: null,
  task_id: null,
  start_time: new Date().toISOString(),
  end_time: null,
  duration_seconds: 0,
  description: null,
  is_running: true,
  created_at: new Date().toISOString(),
  ...overrides,
});

// Simple mock storage for testing
const createMockStorage = () => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
    get length() { return Object.keys(store).length; },
    key: (index: number) => Object.keys(store)[index] || null,
  };
};

describe('Timer Store', () => {
  let mockStorage: ReturnType<typeof createMockStorage>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockStorage = createMockStorage();
    // Override global localStorage for these tests
    Object.defineProperty(window, 'localStorage', { value: mockStorage, writable: true });
    // Set up authentication for timer tests
    mockStorage.setItem('access_token', 'test-token');
    // Reset store state
    useTimerStore.setState({
      currentEntry: null,
      isRunning: false,
      elapsedSeconds: 0,
      isLoading: false,
      error: null,
      lastSyncTime: null,
    });
  });

  afterEach(() => {
    mockStorage.clear();
  });

  describe('Initial State', () => {
    it('should have no current entry initially', () => {
      const { currentEntry } = useTimerStore.getState();
      expect(currentEntry).toBeNull();
    });

    it('should not be running initially', () => {
      const { isRunning } = useTimerStore.getState();
      expect(isRunning).toBe(false);
    });

    it('should have zero elapsed seconds initially', () => {
      const { elapsedSeconds } = useTimerStore.getState();
      expect(elapsedSeconds).toBe(0);
    });

    it('should not be loading initially', () => {
      const { isLoading } = useTimerStore.getState();
      expect(isLoading).toBe(false);
    });

    it('should have no error initially', () => {
      const { error } = useTimerStore.getState();
      expect(error).toBeNull();
    });
  });

  describe('Start Timer', () => {
    it('should start timer successfully', async () => {
      const mockEntry = createMockEntry({
        description: 'Working on task',
        project_id: 1,
      });

      vi.mocked(timeEntriesApi.startTimer).mockResolvedValue(mockEntry);

      await act(async () => {
        await useTimerStore.getState().startTimer({
          project_id: 1,
          description: 'Working on task',
        });
      });

      const { currentEntry, isRunning, isLoading, error } = useTimerStore.getState();
      expect(currentEntry).toEqual(mockEntry);
      expect(isRunning).toBe(true);
      expect(isLoading).toBe(false);
      expect(error).toBeNull();
    });

    it('should start timer without params', async () => {
      const mockEntry = createMockEntry();

      vi.mocked(timeEntriesApi.startTimer).mockResolvedValue(mockEntry);

      await act(async () => {
        await useTimerStore.getState().startTimer();
      });

      const { currentEntry, isRunning } = useTimerStore.getState();
      expect(currentEntry).toEqual(mockEntry);
      expect(isRunning).toBe(true);
    });

    it('should handle start timer failure', async () => {
      vi.mocked(timeEntriesApi.startTimer).mockRejectedValue({
        response: {
          data: {
            detail: 'Timer already running',
          },
        },
      });

      await act(async () => {
        try {
          await useTimerStore.getState().startTimer();
        } catch (e) {
          // Expected
        }
      });

      const { error, isRunning, isLoading } = useTimerStore.getState();
      expect(error).toBe('Timer already running');
      expect(isRunning).toBe(false);
      expect(isLoading).toBe(false);
    });
  });

  describe('Stop Timer', () => {
    it('should stop timer successfully', async () => {
      const runningEntry = createMockEntry({
        description: 'Test',
        is_running: true,
      });

      // First set timer as running
      useTimerStore.setState({
        currentEntry: runningEntry,
        isRunning: true,
        elapsedSeconds: 100,
      });

      const completedEntry = createMockEntry({
        id: 1,
        end_time: new Date().toISOString(),
        duration_seconds: 100,
        description: 'Test',
        is_running: false,
      });

      vi.mocked(timeEntriesApi.stopTimer).mockResolvedValue(completedEntry);

      let result;
      await act(async () => {
        result = await useTimerStore.getState().stopTimer();
      });

      const { currentEntry, isRunning, elapsedSeconds, isLoading, error } = useTimerStore.getState();
      expect(result).toEqual(completedEntry);
      expect(currentEntry).toBeNull();
      expect(isRunning).toBe(false);
      expect(elapsedSeconds).toBe(0);
      expect(isLoading).toBe(false);
      expect(error).toBeNull();
    });

    it('should handle stop timer failure', async () => {
      const runningEntry = createMockEntry({ is_running: true });
      useTimerStore.setState({
        currentEntry: runningEntry,
        isRunning: true,
      });

      vi.mocked(timeEntriesApi.stopTimer).mockRejectedValue({
        response: {
          data: {
            detail: 'No active timer',
          },
        },
      });

      await act(async () => {
        try {
          await useTimerStore.getState().stopTimer();
        } catch (e) {
          // Expected
        }
      });

      const { error, isLoading } = useTimerStore.getState();
      expect(error).toBe('No active timer');
      expect(isLoading).toBe(false);
    });
  });

  describe('Fetch Timer', () => {
    it('should fetch running timer from backend', async () => {
      // Must be authenticated
      localStorage.setItem('access_token', 'valid-token');

      const mockEntry = createMockEntry({
        id: 1,
        start_time: new Date(Date.now() - 60000).toISOString(), // 1 minute ago
        description: 'Working',
        project_id: 1,
        is_running: true,
      });

      const mockStatus: TimerStatus = {
        is_running: true,
        current_entry: mockEntry,
      };

      vi.mocked(timeEntriesApi.getTimer).mockResolvedValue(mockStatus);

      await act(async () => {
        await useTimerStore.getState().fetchTimer();
      });

      const { currentEntry, isRunning, elapsedSeconds } = useTimerStore.getState();
      expect(currentEntry).toEqual(mockEntry);
      expect(isRunning).toBe(true);
      expect(elapsedSeconds).toBeGreaterThanOrEqual(59); // ~60 seconds
    });

    it('should reset state when no timer is running', async () => {
      localStorage.setItem('access_token', 'valid-token');

      // First set some state
      useTimerStore.setState({
        currentEntry: createMockEntry(),
        isRunning: true,
        elapsedSeconds: 100,
      });

      const mockStatus: TimerStatus = {
        is_running: false,
        current_entry: undefined,
      };

      vi.mocked(timeEntriesApi.getTimer).mockResolvedValue(mockStatus);

      await act(async () => {
        await useTimerStore.getState().fetchTimer();
      });

      const { currentEntry, isRunning, elapsedSeconds } = useTimerStore.getState();
      expect(currentEntry).toBeNull();
      expect(isRunning).toBe(false);
      expect(elapsedSeconds).toBe(0);
    });

    it('should not fetch when not authenticated', async () => {
      // Remove token to simulate unauthenticated state
      mockStorage.removeItem('access_token');

      await act(async () => {
        await useTimerStore.getState().fetchTimer();
      });

      expect(timeEntriesApi.getTimer).not.toHaveBeenCalled();
    });
  });

  describe('Update Elapsed', () => {
    it('should update elapsed seconds when running', () => {
      const startTime = new Date(Date.now() - 120000).toISOString(); // 2 minutes ago

      const runningEntry = createMockEntry({
        start_time: startTime,
        is_running: true,
      });

      useTimerStore.setState({
        currentEntry: runningEntry,
        isRunning: true,
        elapsedSeconds: 0,
      });

      act(() => {
        useTimerStore.getState().updateElapsed();
      });

      const { elapsedSeconds } = useTimerStore.getState();
      expect(elapsedSeconds).toBeGreaterThanOrEqual(119); // ~120 seconds
    });

    it('should not update when not running', () => {
      useTimerStore.setState({
        currentEntry: null,
        isRunning: false,
        elapsedSeconds: 50,
      });

      act(() => {
        useTimerStore.getState().updateElapsed();
      });

      const { elapsedSeconds } = useTimerStore.getState();
      expect(elapsedSeconds).toBe(50); // Unchanged
    });
  });

  describe('Clear Error', () => {
    it('should clear error state', () => {
      useTimerStore.setState({ error: 'Some error' });

      act(() => {
        useTimerStore.getState().clearError();
      });

      const { error } = useTimerStore.getState();
      expect(error).toBeNull();
    });
  });

  describe('Sync With Backend', () => {
    it('should sync when stale', async () => {
      localStorage.setItem('access_token', 'token');

      const mockEntry = createMockEntry({
        id: 5,
        description: 'Synced entry',
        project_id: 2,
        is_running: true,
      });

      const mockStatus: TimerStatus = {
        is_running: true,
        current_entry: mockEntry,
      };

      vi.mocked(timeEntriesApi.getTimer).mockResolvedValue(mockStatus);

      // Set stale lastSyncTime (6 minutes ago)
      useTimerStore.setState({
        lastSyncTime: Date.now() - 6 * 60 * 1000,
      });

      await act(async () => {
        await useTimerStore.getState().syncWithBackend();
      });

      expect(timeEntriesApi.getTimer).toHaveBeenCalled();
      const { currentEntry, isRunning } = useTimerStore.getState();
      expect(currentEntry?.id).toBe(5);
      expect(isRunning).toBe(true);
    });

    it('should handle sync failures gracefully', async () => {
      localStorage.setItem('access_token', 'token');

      const mockEntry = createMockEntry({ id: 1, is_running: true });

      useTimerStore.setState({
        lastSyncTime: null, // Force sync
        currentEntry: mockEntry,
        isRunning: true,
      });

      vi.mocked(timeEntriesApi.getTimer).mockRejectedValue(new Error('Network error'));

      // Should not throw
      await act(async () => {
        await useTimerStore.getState().syncWithBackend();
      });

      // State should be preserved on failure
      const { currentEntry, isRunning } = useTimerStore.getState();
      expect(currentEntry?.id).toBe(1);
      expect(isRunning).toBe(true);
    });
  });
});
