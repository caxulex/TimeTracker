// ============================================
// TIME TRACKER - WEBSOCKET CONTEXT
// App-wide real-time state management
// ============================================
import { createContext, useContext, type ReactNode } from 'react';
import { useWebSocket, type WebSocketMessage, type ActiveTimer } from '../hooks/useWebSocket';

interface WebSocketContextValue {
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
  send: (message: WebSocketMessage) => boolean;
  activeTimers: ActiveTimer[];
  onlineUsers: number[];
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
  const ws = useWebSocket({
    onMessage,
    onConnect,
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
export type { WebSocketMessage, ActiveTimer } from '../hooks/useWebSocket';

export type { WebSocketContextValue };
