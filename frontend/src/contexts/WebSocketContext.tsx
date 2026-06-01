// ============================================
// TIME TRACKER - WEBSOCKET CONTEXT
// App-wide real-time state management
// ============================================
import { createContext, useCallback, useContext, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useWebSocket, type WebSocketMessage, type ActiveTimer, type ConnectionState } from '../hooks/useWebSocket';
import { useTimerStore } from '../stores/timerStore';

interface WebSocketContextValue {
  isConnected: boolean;
  connectionState: ConnectionState;
  connect: () => void;
  disconnect: () => void;
  reconnectNow: () => void;
  send: (message: WebSocketMessage) => boolean;
  activeTimers: ActiveTimer[];
  onlineUsers: number[];
  lastMessage: WebSocketMessage | null;
  serverTime: string | null;
  showReconnectNotification: boolean;
  notifyTimerStart: (timer: {
    project_id?: number;
    project_name?: string;
    task_id?: number;
    task_name?: string;
    description?: string;
    start_time?: string;
  }) => boolean;
  notifyTimerStop: (data: {
    duration_seconds?: number;
    project_name?: string;
    task_name?: string;
  }) => boolean;
  notifyTimerUpdate: (elapsed_seconds: number) => boolean;
  requestActiveTimers: (team_id?: number) => boolean;
  requestOnlineUsers: (team_id?: number) => boolean;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

interface WebSocketProviderProps {
  children: ReactNode;
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export function WebSocketProvider({
  children,
  onMessage,
  onConnect,
  onDisconnect
}: WebSocketProviderProps) {
  const queryClient = useQueryClient();

  // ============================================
  // RECONNECT STATE-SYNC
  // After a successful reconnect (NOT the first connect) we have
  // potentially missed broadcasts during the gap. Hydrate by:
  //   1. Refetching the running-timer state via the timer store
  //      (applyServerState reconciliation we shipped in the divergence fix).
  //   2. Invalidating server-data queries so the dashboard's
  //      "Who's Working Now" / active-session strip / etc. refetch.
  // The WS snapshot message is also applied in useWebSocket itself, so
  // active_timers / online_users are already up to date by the time this
  // runs; the refetches below cover REST-backed UI that the snapshot
  // doesn't speak to.
  // ============================================
  const handleReconnect = useCallback(() => {
    console.info('[WS] Reconnected — refetching state');
    void useTimerStore.getState().fetchTimer(true);
    queryClient.invalidateQueries({ queryKey: ['active-timers'] });
    queryClient.invalidateQueries({ queryKey: ['active-session'] });
    queryClient.invalidateQueries({ queryKey: ['online-users'] });
    queryClient.invalidateQueries({ queryKey: ['session-current'] });
    queryClient.invalidateQueries({ queryKey: ['admin-alerts'] });
  }, [queryClient]);

  const ws = useWebSocket({
    onMessage,
    onConnect,
    onReconnect: handleReconnect,
    onDisconnect,
    autoReconnect: true,
    reconnectInterval: 3000,
    maxReconnectAttempts: 5,
  });

  return (
    <WebSocketContext.Provider value={ws}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext(): WebSocketContextValue {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
}

// Re-export types for convenience
export type { WebSocketMessage, ActiveTimer, ConnectionState } from '../hooks/useWebSocket';

export type { WebSocketContextValue };
