// ============================================
// TIME TRACKER - SESSION STORE (ZUSTAND)
// Micro-Task Management: Work Sessions, Breaks, Meetings
// ============================================
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
  WorkSession,
  SessionBreak,
  SessionMeeting,
  SessionBreakCreate,
  SessionMeetingCreate,
  SessionStatus,
} from '../types';
import { sessionsApi } from '../api/client';

// WebSocket event payload types
interface SessionWebSocketEvent {
  user_id: number;
  data?: WorkSession;
}

interface BreakWebSocketEvent {
  user_id: number;
  data?: SessionBreak & { duration_seconds?: number };
}

interface MeetingWebSocketEvent {
  user_id: number;
  data?: SessionMeeting & { duration_seconds?: number };
}

// Error type for catch blocks
interface ApiError {
  response?: {
    status?: number;
    data?: { detail?: string };
  };
  message?: string;
}

interface SessionState {
  // Current session state
  currentSession: WorkSession | null;
  activeBreak: SessionBreak | null;
  activeMeeting: SessionMeeting | null;
  
  // UI state
  isLoading: boolean;
  error: string | null;
  lastSyncTime: number | null;
  
  // Calculated elapsed times (updated by interval)
  sessionElapsedSeconds: number;
  breakElapsedSeconds: number;
  meetingElapsedSeconds: number;

  // Actions
  fetchCurrentSession: () => Promise<void>;
  startSession: () => Promise<void>;
  endSession: () => Promise<void>;
  startBreak: (data: SessionBreakCreate) => Promise<void>;
  endBreak: () => Promise<void>;
  startMeeting: (data: SessionMeetingCreate) => Promise<void>;
  endMeeting: () => Promise<void>;
  updateElapsedTimes: () => void;
  clearError: () => void;
  
  // WebSocket event handlers
  handleSessionStarted: (data: SessionWebSocketEvent) => void;
  handleSessionEnded: (data: SessionWebSocketEvent) => void;
  handleBreakStarted: (data: BreakWebSocketEvent) => void;
  handleBreakEnded: (data: BreakWebSocketEvent) => void;
  handleMeetingStarted: (data: MeetingWebSocketEvent) => void;
  handleMeetingEnded: (data: MeetingWebSocketEvent) => void;
}

// Helper to calculate elapsed seconds from ISO start time
const calculateElapsed = (startTime: string): number => {
  const start = new Date(startTime).getTime();
  const now = Date.now();
  return Math.max(0, Math.floor((now - start) / 1000));
};

// Helper to check if user is authenticated
const isAuthenticated = (): boolean => {
  return !!localStorage.getItem('access_token');
};

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      // Initial state
      currentSession: null,
      activeBreak: null,
      activeMeeting: null,
      isLoading: false,
      error: null,
      lastSyncTime: null,
      sessionElapsedSeconds: 0,
      breakElapsedSeconds: 0,
      meetingElapsedSeconds: 0,

      // Fetch current session from backend
      fetchCurrentSession: async () => {
        if (!isAuthenticated()) {
          console.log('[SessionStore] Skipping fetch - not authenticated');
          return;
        }

        // Debounce: Don't fetch if we synced in the last 2 seconds
        const { lastSyncTime } = get();
        if (lastSyncTime && Date.now() - lastSyncTime < 2000) {
          console.log('[SessionStore] Skipping fetch - recently synced');
          return;
        }

        set({ isLoading: true, error: null });
        try {
          const status = await sessionsApi.getCurrentSession();
          console.log('[SessionStore] Fetched session status:', status);

          if (status.has_active_session && status.session) {
            // Use backend's global_timer_seconds which already subtracts breaks + meetings
            const sessionElapsed = Math.max(0, status.global_timer_seconds);
            const breakElapsed = status.current_break 
              ? calculateElapsed(status.current_break.start_time) 
              : 0;
            const meetingElapsed = status.current_meeting 
              ? calculateElapsed(status.current_meeting.start_time) 
              : 0;

            set({
              currentSession: status.session,
              activeBreak: status.current_break || null,
              activeMeeting: status.current_meeting || null,
              sessionElapsedSeconds: sessionElapsed,
              breakElapsedSeconds: breakElapsed,
              meetingElapsedSeconds: meetingElapsed,
              isLoading: false,
              lastSyncTime: Date.now(),
            });
          } else {
            set({
              currentSession: null,
              activeBreak: null,
              activeMeeting: null,
              sessionElapsedSeconds: 0,
              breakElapsedSeconds: 0,
              meetingElapsedSeconds: 0,
              isLoading: false,
              lastSyncTime: Date.now(),
            });
          }
        } catch (err: unknown) {
          const error = err as ApiError;
          const status = error.response?.status;
          if (status === 401 || status === 403 || status === 429) {
            console.warn(`[SessionStore] ${status === 429 ? 'Rate limited' : 'Auth error'}, using local state`);
            set({ isLoading: false });
            return;
          }
          console.error('[SessionStore] Error fetching session:', error);
          set({ error: error.message || 'Unknown error', isLoading: false });
        }
      },

      // Start a new work session (clock in)
      startSession: async () => {
        set({ isLoading: true, error: null });
        try {
          const session = await sessionsApi.startSession();
          set({
            currentSession: session,
            activeBreak: null,
            activeMeeting: null,
            sessionElapsedSeconds: 0,
            breakElapsedSeconds: 0,
            meetingElapsedSeconds: 0,
            isLoading: false,
            lastSyncTime: Date.now(),
          });
        } catch (err: unknown) {
          const error = err as ApiError;
          const message = error.response?.data?.detail || 'Failed to start session';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      // End current work session (clock out)
      endSession: async () => {
        set({ isLoading: true, error: null });
        try {
          await sessionsApi.endSession();
          set({
            currentSession: null,
            activeBreak: null,
            activeMeeting: null,
            sessionElapsedSeconds: 0,
            breakElapsedSeconds: 0,
            meetingElapsedSeconds: 0,
            isLoading: false,
            lastSyncTime: Date.now(),
          });
        } catch (err: unknown) {
          const error = err as ApiError;
          const message = error.response?.data?.detail || 'Failed to end session';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      // Start a break
      startBreak: async (data: SessionBreakCreate) => {
        set({ isLoading: true, error: null });
        try {
          const brk = await sessionsApi.startBreak(data);
          const { currentSession } = get();
          if (currentSession) {
            set({
              currentSession: { ...currentSession, status: 'break' as SessionStatus },
              activeBreak: brk,
              breakElapsedSeconds: 0,
              isLoading: false,
              lastSyncTime: Date.now(),
            });
          }
        } catch (err: unknown) {
          const error = err as ApiError;
          const message = error.response?.data?.detail || 'Failed to start break';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      // End current break
      endBreak: async () => {
        set({ isLoading: true, error: null });
        try {
          const brk = await sessionsApi.endBreak();
          const { currentSession } = get();
          if (currentSession) {
            set({
              currentSession: { 
                ...currentSession, 
                status: 'active' as SessionStatus,
                total_break_seconds: currentSession.total_break_seconds + (brk.duration_seconds || 0),
              },
              activeBreak: null,
              breakElapsedSeconds: 0,
              isLoading: false,
              lastSyncTime: Date.now(),
            });
          }
        } catch (err: unknown) {
          const error = err as ApiError;
          const message = error.response?.data?.detail || 'Failed to end break';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      // Start a meeting
      startMeeting: async (data: SessionMeetingCreate) => {
        set({ isLoading: true, error: null });
        try {
          const meeting = await sessionsApi.startMeeting(data);
          const { currentSession } = get();
          if (currentSession) {
            set({
              currentSession: { ...currentSession, status: 'meeting' as SessionStatus },
              activeMeeting: meeting,
              meetingElapsedSeconds: 0,
              isLoading: false,
              lastSyncTime: Date.now(),
            });
          }
        } catch (err: unknown) {
          const error = err as ApiError;
          const message = error.response?.data?.detail || 'Failed to start meeting';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      // End current meeting
      endMeeting: async () => {
        set({ isLoading: true, error: null });
        try {
          const meeting = await sessionsApi.endMeeting();
          const { currentSession } = get();
          if (currentSession) {
            set({
              currentSession: { 
                ...currentSession, 
                status: 'active' as SessionStatus,
                total_meeting_seconds: currentSession.total_meeting_seconds + (meeting.duration_seconds || 0),
              },
              activeMeeting: null,
              meetingElapsedSeconds: 0,
              isLoading: false,
              lastSyncTime: Date.now(),
            });
          }
        } catch (err: unknown) {
          const error = err as ApiError;
          const message = error.response?.data?.detail || 'Failed to end meeting';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      // Update elapsed times (called by interval)
      updateElapsedTimes: () => {
        const { currentSession, activeBreak, activeMeeting } = get();
        
        if (currentSession) {
          // Session clock = raw elapsed - breaks only (meetings count as work time)
          let sessionElapsed = calculateElapsed(currentSession.start_time)
            - (currentSession.total_break_seconds || 0);
          
          // If currently on break, also subtract the live break duration
          if (activeBreak) {
            sessionElapsed -= calculateElapsed(activeBreak.start_time);
          }
          
          set({ sessionElapsedSeconds: Math.max(0, sessionElapsed) });
        }
        
        if (activeBreak) {
          const breakElapsed = calculateElapsed(activeBreak.start_time);
          set({ breakElapsedSeconds: breakElapsed });
        }
        
        if (activeMeeting) {
          const meetingElapsed = calculateElapsed(activeMeeting.start_time);
          set({ meetingElapsedSeconds: meetingElapsed });
        }
      },

      clearError: () => set({ error: null }),

      // ============================================
      // WEBSOCKET EVENT HANDLERS
      // ============================================
      
      handleSessionStarted: (data: SessionWebSocketEvent) => {
        // Only update if it's for the current user
        const currentUserId = get().currentSession?.user_id;
        if (data.user_id === currentUserId || !currentUserId) {
          // Refetch to get full session data
          get().fetchCurrentSession();
        }
      },

      handleSessionEnded: (data: SessionWebSocketEvent) => {
        const { currentSession } = get();
        if (currentSession && data.user_id === currentSession.user_id) {
          set({
            currentSession: null,
            activeBreak: null,
            activeMeeting: null,
            sessionElapsedSeconds: 0,
            breakElapsedSeconds: 0,
            meetingElapsedSeconds: 0,
          });
        }
      },

      handleBreakStarted: (data: BreakWebSocketEvent) => {
        const { currentSession } = get();
        if (currentSession && data.user_id === currentSession.user_id && data.data) {
          set({
            currentSession: { ...currentSession, status: 'break' as SessionStatus },
            activeBreak: data.data,
            breakElapsedSeconds: 0,
          });
        }
      },

      handleBreakEnded: (data: BreakWebSocketEvent) => {
        const { currentSession } = get();
        if (currentSession && data.user_id === currentSession.user_id) {
          set({
            currentSession: { 
              ...currentSession, 
              status: 'active' as SessionStatus,
              total_break_seconds: currentSession.total_break_seconds + (data.data?.duration_seconds || 0),
            },
            activeBreak: null,
            breakElapsedSeconds: 0,
          });
        }
      },

      handleMeetingStarted: (data: MeetingWebSocketEvent) => {
        const { currentSession } = get();
        if (currentSession && data.user_id === currentSession.user_id && data.data) {
          set({
            currentSession: { ...currentSession, status: 'meeting' as SessionStatus },
            activeMeeting: data.data,
            meetingElapsedSeconds: 0,
          });
        }
      },

      handleMeetingEnded: (data: MeetingWebSocketEvent) => {
        const { currentSession } = get();
        if (currentSession && data.user_id === currentSession.user_id) {
          set({
            currentSession: { 
              ...currentSession, 
              status: 'active' as SessionStatus,
              total_meeting_seconds: currentSession.total_meeting_seconds + (data.data?.duration_seconds || 0),
            },
            activeMeeting: null,
            meetingElapsedSeconds: 0,
          });
        }
      },
    }),
    {
      name: 'session-storage',
      partialize: (state) => ({
        currentSession: state.currentSession,
        activeBreak: state.activeBreak,
        activeMeeting: state.activeMeeting,
        lastSyncTime: state.lastSyncTime,
      }),
      // On rehydrate, recalculate elapsed times and optionally sync with backend
      onRehydrateStorage: () => (state) => {
        console.log('[SessionStore] Rehydrating state from localStorage:', state);
        
        if (state?.currentSession) {
          // Subtract breaks only — meetings count as work time
          let elapsed = calculateElapsed(state.currentSession.start_time)
            - (state.currentSession.total_break_seconds || 0);
          if (state.activeBreak) {
            elapsed -= calculateElapsed(state.activeBreak.start_time);
          }
          state.sessionElapsedSeconds = Math.max(0, elapsed);
        }
        if (state?.activeBreak) {
          state.breakElapsedSeconds = calculateElapsed(state.activeBreak.start_time);
        }
        if (state?.activeMeeting) {
          state.meetingElapsedSeconds = calculateElapsed(state.activeMeeting.start_time);
        }

        // Only fetch from backend if authenticated and we haven't synced recently
        if (!isAuthenticated()) {
          console.log('[SessionStore] Skipping backend sync - not authenticated');
          return;
        }

        const shouldSync = !state?.lastSyncTime || Date.now() - state.lastSyncTime > 30000;
        if (shouldSync && state) {
          console.log('[SessionStore] Triggering backend sync (stale data)...');
          setTimeout(() => state.fetchCurrentSession(), 100);
        } else {
          console.log('[SessionStore] Skipping backend sync (recent data available)');
        }
      },
    }
  )
);

// ============================================
// HELPER HOOKS
// ============================================

/**
 * Helper to format seconds as HH:MM:SS
 */
export const formatDuration = (totalSeconds: number): string => {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  
  return [
    hours.toString().padStart(2, '0'),
    minutes.toString().padStart(2, '0'),
    seconds.toString().padStart(2, '0'),
  ].join(':');
};

/**
 * Get session status display info
 */
export const getSessionStatusInfo = (status: SessionStatus | undefined) => {
  switch (status) {
    case 'active':
      return { label: 'Working', color: 'green', icon: '🟢' };
    case 'break':
      return { label: 'On Break', color: 'yellow', icon: '☕' };
    case 'meeting':
      return { label: 'In Meeting', color: 'blue', icon: '📅' };
    case 'completed':
      return { label: 'Completed', color: 'gray', icon: '✓' };
    default:
      return { label: 'Not Started', color: 'gray', icon: '⚪' };
  }
};
