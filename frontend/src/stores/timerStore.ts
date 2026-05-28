// ============================================
// TIME TRACKER - TIMER STORE (ZUSTAND)
// TASK-004: Timer state persistence on page refresh
// ============================================
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { TimeEntry, TimerStart } from '../types';
import { timeEntriesApi } from '../api/client';
import axios from 'axios';
import { isNoRunningTimerError } from '../utils/timerErrors';

interface TimerState {
  currentEntry: TimeEntry | null;
  isRunning: boolean;
  isPaused: boolean;  // True when on break or in meeting
  elapsedSeconds: number;
  isLoading: boolean;
  error: string | null;
  lastSyncTime: number | null;

  // Actions
  fetchTimer: (forceRefresh?: boolean) => Promise<void>;
  startTimer: (data?: TimerStart) => Promise<void>;
  stopTimer: () => Promise<TimeEntry | null>;
  switchTimer: (data: { project_id: number; task_id?: number; description?: string }) => Promise<void>;
  updateElapsed: () => void;
  clearError: () => void;
  syncWithBackend: () => Promise<void>;
}

// Helper to calculate elapsed seconds from start time
const calculateElapsed = (startTime: string): number => {
  const start = new Date(startTime).getTime();
  const now = Date.now();
  return Math.max(0, Math.floor((now - start) / 1000));
};

// Helper to check if user is authenticated
const isAuthenticated = (): boolean => {
  return !!localStorage.getItem('access_token');
};

export const useTimerStore = create<TimerState>()(
  persist(
    (set, get) => ({
      currentEntry: null,
      isRunning: false,
      isPaused: false,
      elapsedSeconds: 0,
      isLoading: false,
      error: null,
      lastSyncTime: null,

      fetchTimer: async (forceRefresh?: boolean) => {
        // Don't fetch if not authenticated
        if (!isAuthenticated()) {
          console.log('[TimerStore] Skipping fetch - not authenticated');
          return;
        }
        
        // Debounce: Don't fetch if we synced in the last 2 seconds (unless forced)
        const { lastSyncTime } = get();
        if (!forceRefresh && lastSyncTime && Date.now() - lastSyncTime < 2000) {
          console.log('[TimerStore] Skipping fetch - recently synced');
          return;
        }
        
        set({ isLoading: true, error: null });
        try {
          const status = await timeEntriesApi.getTimer();
          console.log('[TimerStore] Fetched timer status:', status);
          if (status.is_running && status.current_entry) {
            const entry = status.current_entry;
            const isPaused = entry.is_paused || false;
            // Calculate elapsed: total time minus pause time
            let elapsed = calculateElapsed(entry.start_time);
            // Subtract accumulated pause seconds
            elapsed -= entry.pause_seconds || 0;
            // If currently paused, don't include time since pause started
            if (isPaused && entry.paused_at) {
              const pauseElapsed = calculateElapsed(entry.paused_at);
              elapsed -= pauseElapsed;
            }
            console.log('[TimerStore] Setting timer, elapsed:', elapsed, 'isPaused:', isPaused);
            set({
              currentEntry: entry,
              isRunning: true,
              isPaused: isPaused,
              elapsedSeconds: Math.max(0, elapsed),
              isLoading: false,
              lastSyncTime: Date.now(),
            });
          } else {
            console.log('[TimerStore] No running timer, resetting state');
            set({ 
              currentEntry: null, 
              isRunning: false, 
              isPaused: false,
              elapsedSeconds: 0, 
              isLoading: false,
              lastSyncTime: Date.now(),
            });
          }
        } catch (error: unknown) {
          // Handle 401/403 (auth errors) and 429 (rate limit) gracefully - just use local state
          const status = axios.isAxiosError(error) ? error.response?.status : undefined;
          if (status === 401 || status === 403 || status === 429) {
            console.warn(`[TimerStore] ${status === 429 ? 'Rate limited' : 'Auth error'}, using local state`);
            set({ isLoading: false });
            return;
          }
          console.error('[TimerStore] Error fetching timer:', error);
          set({ error: error instanceof Error ? error.message : 'Unknown error', isLoading: false });
        }
      },

      startTimer: async (data?: TimerStart) => {
        set({ isLoading: true, error: null });
        try {
          const entry = await timeEntriesApi.startTimer(data);
          set({
            currentEntry: entry,
            isRunning: true,
            isPaused: false,
            elapsedSeconds: 0,
            isLoading: false,
            lastSyncTime: Date.now(),
          });
        } catch (error: unknown) {
          let message = 'Failed to start timer';
          if (axios.isAxiosError(error)) {
            message = error.response?.data?.detail || message;
          } else if (typeof error === 'object' && error !== null) {
            const resp = (error as Record<string, unknown>).response as Record<string, unknown> | undefined;
            const data = resp?.data as Record<string, unknown> | undefined;
            if (typeof data?.detail === 'string') message = data.detail;
          }
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      stopTimer: async () => {
        set({ isLoading: true, error: null });
        try {
          const entry = await timeEntriesApi.stopTimer();
          set({
            currentEntry: null,
            isRunning: false,
            isPaused: false,
            elapsedSeconds: 0,
            isLoading: false,
            lastSyncTime: Date.now(),
          });
          return entry;
        } catch (error: unknown) {
          if (isNoRunningTimerError(error)) {
            set({
              currentEntry: null,
              isRunning: false,
              isPaused: false,
              elapsedSeconds: 0,
              isLoading: false,
              error: null,
              lastSyncTime: Date.now(),
            });

            try {
              await get().fetchTimer(true);
            } catch {
              // Keep local state reconciled even if a forced refresh fails.
            }

            throw error;
          }

          let message = 'Failed to stop timer';
          if (axios.isAxiosError(error)) {
            message = error.response?.data?.detail || message;
          } else if (typeof error === 'object' && error !== null) {
            const resp = (error as Record<string, unknown>).response as Record<string, unknown> | undefined;
            const data = resp?.data as Record<string, unknown> | undefined;
            if (typeof data?.detail === 'string') message = data.detail;
          }
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      switchTimer: async (data: { project_id: number; task_id?: number; description?: string }) => {
        set({ isLoading: true, error: null });
        try {
          const entry = await timeEntriesApi.switchTimer(data);
          set({
            currentEntry: entry,
            isRunning: true,
            isPaused: false,
            elapsedSeconds: 0,  // Reset task timer — session clock keeps going
            isLoading: false,
            lastSyncTime: Date.now(),
          });
        } catch (error: unknown) {
          let message = 'Failed to switch task';
          if (axios.isAxiosError(error)) {
            message = error.response?.data?.detail || message;
          } else if (typeof error === 'object' && error !== null) {
            const resp = (error as Record<string, unknown>).response as Record<string, unknown> | undefined;
            const data = resp?.data as Record<string, unknown> | undefined;
            if (typeof data?.detail === 'string') message = data.detail;
          }
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      updateElapsed: () => {
        const { currentEntry, isRunning, isPaused } = get();
        // Don't increment if paused (on break or in meeting)
        if (isRunning && currentEntry && !isPaused) {
          let elapsed = calculateElapsed(currentEntry.start_time);
          // Subtract accumulated pause seconds
          elapsed -= currentEntry.pause_seconds || 0;
          set({ elapsedSeconds: Math.max(0, elapsed) });
        }
      },

      clearError: () => set({ error: null }),

      // Sync local state with backend
      syncWithBackend: async () => {
        const { lastSyncTime, isRunning, currentEntry } = get();
        
        // Only sync if we have local state or haven't synced in 5 minutes
        const shouldSync = !lastSyncTime || 
          Date.now() - lastSyncTime > 5 * 60 * 1000 ||
          (isRunning && currentEntry);
        
        if (shouldSync) {
          try {
            const status = await timeEntriesApi.getTimer();
            
            // Backend has a running timer
            if (status.is_running && status.current_entry) {
              const elapsed = calculateElapsed(status.current_entry.start_time);
              set({
                currentEntry: status.current_entry,
                isRunning: true,
                elapsedSeconds: elapsed,
                lastSyncTime: Date.now(),
              });
            } 
            // Local shows running but backend doesn't - trust backend
            else if (get().isRunning) {
              set({
                currentEntry: null,
                isRunning: false,
                elapsedSeconds: 0,
                lastSyncTime: Date.now(),
              });
            }
          } catch (error) {
            // If sync fails, continue with local state
            console.warn('Timer sync failed:', error);
          }
        }
      },
    }),
    {
      name: 'timer-storage',
      partialize: (state) => ({
        currentEntry: state.currentEntry,
        isRunning: state.isRunning,
        lastSyncTime: state.lastSyncTime,
      }),
      // On rehydrate, sync with backend to get fresh state (with debounce)
      onRehydrateStorage: () => (state) => {
        console.log('[TimerStore] Rehydrating state from localStorage:', state);
        if (state?.isRunning && state?.currentEntry) {
          const elapsed = calculateElapsed(state.currentEntry.start_time);
          state.elapsedSeconds = elapsed;
          console.log('[TimerStore] Rehydrated with running timer, elapsed:', elapsed);
        }
        
        // Only fetch from backend if authenticated and we haven't synced recently
        if (!isAuthenticated()) {
          console.log('[TimerStore] Skipping backend sync - not authenticated');
          return;
        }
        
        const shouldSync = !state?.lastSyncTime || Date.now() - state.lastSyncTime > 30000;
        if (shouldSync && state) {
          console.log('[TimerStore] Triggering backend sync (stale data)...');
          // Use setTimeout to avoid calling async during rehydration
          setTimeout(() => state.fetchTimer(), 100);
        } else {
          console.log('[TimerStore] Skipping backend sync (recent data available)');
        }
      },
    }
  )
);
