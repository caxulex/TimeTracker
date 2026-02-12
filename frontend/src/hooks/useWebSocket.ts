// ============================================
// TIME TRACKER - WEBSOCKET HOOK
// TASK 7.2: Robust reconnection with exponential backoff,
//           network event handling, and user notifications
// ============================================
import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '../stores/authStore';

interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  reconnectInterval?: number; // kept for API compat, ignored — using backoff
  maxReconnectAttempts?: number;
}

interface ActiveTimer {
  user_id: number;
  user_name: string;
  project_id?: number;
  project_name?: string;
  task_id?: number;
  task_name?: string;
  description?: string;
  start_time: string;
  elapsed_seconds?: number;
}

// ============================================
// EXPONENTIAL BACKOFF
// Attempts:  1s -> 2s -> 4s -> 8s -> 16s -> 30s (capped)
// ============================================
const BASE_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30_000;

function calculateBackoff(attempt: number): number {
  const backoff = Math.min(BASE_BACKOFF_MS * Math.pow(2, attempt), MAX_BACKOFF_MS);
  // +/-20% jitter to prevent thundering herd
  const jitter = backoff * 0.2 * (Math.random() * 2 - 1);
  return Math.round(backoff + jitter);
}

// ============================================
// CONNECTION STATE
// ============================================
export type ConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'failed';

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    autoReconnect = true,
    maxReconnectAttempts = 5,
  } = options;

  const { isAuthenticated } = useAuthStore();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  const manualDisconnectRef = useRef(false);

  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [activeTimers, setActiveTimers] = useState<ActiveTimer[]>([]);
  const [onlineUsers, setOnlineUsers] = useState<number[]>([]);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [showReconnectNotification, setShowReconnectNotification] = useState(false);

  const getToken = useCallback(() => {
    return localStorage.getItem('access_token');
  }, []);

  const getWebSocketUrl = useCallback(() => {
    const token = getToken();
    if (!token) return null;

    const apiUrl = import.meta.env.VITE_API_URL;

    if (!apiUrl) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      return protocol + '//' + host + '/api/ws/ws?token=' + token;
    }

    const url = new URL(apiUrl);
    const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = url.host;
    return protocol + '//' + host + '/api/ws/ws?token=' + token;
  }, [getToken]);

  // ============================================
  // CONNECT
  // ============================================
  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    const token = getToken();
    if (!isAuthenticated || !token) return;

    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // Close any stale connection
    if (wsRef.current) {
      try { wsRef.current.close(); } catch { /* ignore */ }
      wsRef.current = null;
    }

    const wsUrl = getWebSocketUrl();
    if (!wsUrl) return;

    try {
      setConnectionState('connecting');
      manualDisconnectRef.current = false;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setIsConnected(true);
        setConnectionState('connected');
        setShowReconnectNotification(false);
        reconnectAttempts.current = 0;
        onConnect?.();

        // Re-subscribe to channels on (re)connection
        ws.send(JSON.stringify({ type: 'get_active_timers' }));
        ws.send(JSON.stringify({ type: 'get_online_users' }));
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);

          switch (message.type) {
            case 'ping':
              ws.send(JSON.stringify({ type: 'pong' }));
              break;
            case 'active_timers':
              setActiveTimers(message.timers || []);
              break;
            case 'online_users':
              setOnlineUsers(message.users || []);
              break;
            case 'timer_started': {
              const timerData = message.data || message;
              setActiveTimers(prev => {
                const filtered = prev.filter(t => t.user_id !== timerData.user_id);
                return [...filtered, {
                  user_id: timerData.user_id,
                  user_name: timerData.user_name,
                  project_id: timerData.project_id,
                  project_name: timerData.project_name,
                  task_id: timerData.task_id,
                  task_name: timerData.task_name,
                  description: timerData.description,
                  start_time: timerData.start_time,
                }];
              });
              break;
            }
            case 'timer_stopped': {
              const stopData = message.data || message;
              setActiveTimers(prev => prev.filter(t => t.user_id !== stopData.user_id));
              break;
            }
            case 'team_added':
            case 'member_added':
            case 'project_created':
            case 'task_created':
              break;
            case 'notification':
              if (message.data && (window as any).__handleIncomingNotification) {
                (window as any).__handleIncomingNotification(message.data);
              }
              break;
          }

          onMessage?.(message);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onclose = (_event) => {
        if (!isMountedRef.current) return;
        setIsConnected(false);
        wsRef.current = null;
        onDisconnect?.();

        // Don't reconnect if manually disconnected
        if (manualDisconnectRef.current) {
          setConnectionState('disconnected');
          return;
        }

        if (autoReconnect && reconnectAttempts.current < maxReconnectAttempts) {
          const backoffMs = calculateBackoff(reconnectAttempts.current);
          reconnectAttempts.current++;
          setConnectionState('reconnecting');

          // Show notification after 3 failed attempts
          if (reconnectAttempts.current >= 3) {
            setShowReconnectNotification(true);
          }

          reconnectTimeoutRef.current = setTimeout(connect, backoffMs);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setConnectionState('failed');
          setShowReconnectNotification(true);
        }
      };

      ws.onerror = (error) => {
        if (!isMountedRef.current) return;
        onError?.(error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      setConnectionState('disconnected');
    }
  }, [isAuthenticated, getToken, getWebSocketUrl, onConnect, onDisconnect, onMessage, onError, autoReconnect, maxReconnectAttempts]);

  // ============================================
  // DISCONNECT
  // ============================================
  const disconnect = useCallback(() => {
    manualDisconnectRef.current = true;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
    setConnectionState('disconnected');
    setShowReconnectNotification(false);
    reconnectAttempts.current = 0;
  }, []);

  // ============================================
  // MANUAL RECONNECT (for "Reconnect Now" button)
  // ============================================
  const reconnectNow = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    reconnectAttempts.current = 0;
    setShowReconnectNotification(false);
    setConnectionState('connecting');
    connect();
  }, [connect]);

  // ============================================
  // SEND
  // ============================================
  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  // ============================================
  // CONVENIENCE SENDERS
  // ============================================
  const notifyTimerStart = useCallback((timer: {
    project_id?: number;
    project_name?: string;
    task_id?: number;
    task_name?: string;
    description?: string;
    start_time?: string;
  }) => {
    return send({
      type: 'timer_start',
      ...timer,
      start_time: timer.start_time || new Date().toISOString(),
    });
  }, [send]);

  const notifyTimerStop = useCallback((data: {
    duration_seconds?: number;
    project_name?: string;
    task_name?: string;
  }) => {
    return send({ type: 'timer_stop', ...data });
  }, [send]);

  const notifyTimerUpdate = useCallback((elapsed_seconds: number) => {
    return send({ type: 'timer_update', elapsed_seconds });
  }, [send]);

  const requestActiveTimers = useCallback((team_id?: number) => {
    return send({ type: 'get_active_timers', team_id });
  }, [send]);

  const requestOnlineUsers = useCallback((team_id?: number) => {
    return send({ type: 'get_online_users', team_id });
  }, [send]);

  // ============================================
  // AUTO-CONNECT ON AUTH CHANGE
  // ============================================
  useEffect(() => {
    if (isAuthenticated) {
      connect();
    } else {
      disconnect();
    }
  }, [isAuthenticated, connect, disconnect]);

  // ============================================
  // NETWORK CHANGE EVENT LISTENERS
  // ============================================
  useEffect(() => {
    const handleOnline = () => {
      if (isAuthenticated && !wsRef.current) {
        reconnectAttempts.current = 0;
        connect();
      }
    };

    const handleOffline = () => {
      setConnectionState('disconnected');
      setIsConnected(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [isAuthenticated, connect]);

  // ============================================
  // CLEANUP ON UNMOUNT
  // ============================================
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  return {
    isConnected,
    connectionState,
    connect,
    disconnect,
    reconnectNow,
    send,
    activeTimers,
    onlineUsers,
    lastMessage,
    showReconnectNotification,
    notifyTimerStart,
    notifyTimerStop,
    notifyTimerUpdate,
    requestActiveTimers,
    requestOnlineUsers,
  };
}

export type { WebSocketMessage, ActiveTimer };
