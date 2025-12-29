// ============================================
// TIME TRACKER - TIMER STORE (ZUSTAND)
// TASK-004: Timer state persistence on page refresh
// ============================================
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { TimeEntry, TimerStart } from '../types';
import { timeEntriesApi } from '../api/client';

interface TimerState {
  currentEntry: TimeEntry | null;
  isRunning: boolean;
  elapsedSeconds: number;
  isLoading: boolean;
  error: string | null;
  lastSyncTime: number | null;

  // Actions
  fetchTimer: () => Promise<void>;
  startTimer: (data?: TimerStart) => Promise<void>;
  stopTimer: () => Promise<TimeEntry | null>;
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
      elapsedSeconds: 0,
      isLoading: false,
      error: null,
      lastSyncTime: null,

      fetchTimer: async () => {
        // Don't fetch if not authenticated
        if (!isAuthenticated()) {
          console.log('[TimerStore] Skipping fetch - not authenticated');
          return;
        }
        
        // Debounce: Don't fetch if we synced in the last 2 seconds
        const { lastSyncTime } = get();
        if (lastSyncTime && Date.now() - lastSyncTime < 2000) {
          console.log('[TimerStore] Skipping fetch - recently synced');
          return;
        }
        
        set({ isLoading: true, error: null });
        try {
          const status = await timeEntriesApi.getTimer();
          console.log('[TimerStore] Fetched timer status:', status);
          if (status.is_running && status.current_entry) {
            const elapsed = calculateElapsed(status.current_entry.start_time);
            console.log('[TimerStore] Setting running timer, elapsed:', elapsed);
            set({
              currentEntry: status.current_entry,
              isRunning: true,
              elapsedSeconds: elapsed,
              isLoading: false,
              lastSyncTime: Date.now(),
            });
          } else {
            console.log('[TimerStore] No running timer, resetting state');
            set({ 
              currentEntry: null, 
              isRunning: false, 
              elapsedSeconds: 0, 
              isLoading: false,
              lastSyncTime: Date.now(),
            });
          }
        } catch (error: any) {
          // Handle 401/403 (auth errors) and 429 (rate limit) gracefully - just use local state
          const status = error.response?.status;
          if (status === 401 || status === 403 || status === 429) {
            console.warn(`[TimerStore] ${status === 429 ? 'Rate limited' : 'Auth error'}, using local state`);
            set({ isLoading: false });
            return;
          }
          console.error('[TimerStore] Error fetching timer:', error);
          set({ error: error.message, isLoading: false });
        }
      },

      startTimer: async (data?: TimerStart) => {
        set({ isLoading: true, error: null });
        try {
          const entry = await timeEntriesApi.startTimer(data);
          set({
            currentEntry: entry,
            isRunning: true,
            elapsedSeconds: 0,
            isLoading: false,
            lastSyncTime: Date.now(),
          });
        } catch (error: any) {
          const message = error.response?.data?.detail || 'Failed to start timer';
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
            elapsedSeconds: 0,
            isLoading: false,
            lastSyncTime: Date.now(),
          });
          return entry;
        } catch (error: any) {
          const message = error.response?.data?.detail || 'Failed to stop timer';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      updateElapsed: () => {
        const { currentEntry, isRunning } = get();
        if (isRunning && currentEntry) {
          const elapsed = calculateElapsed(currentEntry.start_time);
          set({ elapsedSeconds: elapsed });
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
