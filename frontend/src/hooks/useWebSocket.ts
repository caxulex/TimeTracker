// ============================================
// TIME TRACKER - WEBSOCKET HOOK
// TASK 7.2: Robust reconnection with exponential backoff,
//           network event handling, and user notifications
// ============================================
import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '../stores/authStore';

interface WebSocketMessage {
  type: string;
  [key: string]: unknown;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  /**
   * Fires after a successful reconnect ONLY — NOT on the very first
   * connect of the hook's lifetime. App-level state-sync (e.g. timer
   * refetch, React Query invalidation) belongs here so the dashboard
   * hydrates from the server immediately after the transport recovers.
   */
  onReconnect?: () => void;
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
  /**
   * Timestamp at which the user entered the CURRENT activity state.
   *  - "working": equals ``start_time`` of the running TimeEntry.
   *  - "break":   ``SessionBreak.start_time`` of the open break.
   *  - "meeting": ``SessionMeeting.start_time`` of the open meeting.
   * The "Who's Working Now" panel anchors its displayed duration to
   * this so break/meeting time shows the elapsed time IN that state,
   * not the (frozen or otherwise) work-time elapsed.
   */
  state_started_at?: string;
  /** Server-computed (now - state_started_at) at response time. */
  state_elapsed_seconds?: number;
  activity_state?: 'working' | 'break' | 'meeting';
  break_type?: 'short' | 'lunch' | 'other' | null;
  meeting_type?: 'internal' | 'external' | 'client' | null;
  meeting_title?: string | null;
}

// ============================================
// EXPONENTIAL BACKOFF
// Attempts:  1s -> 2s -> 4s -> 8s -> 16s -> 30s (capped)
// ============================================
const BASE_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30_000;

// ============================================
// LIVENESS WATCHDOG
// Server pings every WS_HEARTBEAT_INTERVAL_SEC (default 30s). The client
// gives 15s of slack for network jitter; if no message of any kind has
// arrived in 45s we force-close with code 4002 “client_liveness_timeout”
// so the existing reconnect machinery picks the link back up.
// ============================================
const LIVENESS_THRESHOLD_MS = 45_000;
const LIVENESS_CHECK_INTERVAL_MS = 5_000;
const LIVENESS_CLOSE_CODE = 4002;
const LIVENESS_CLOSE_REASON = 'client_liveness_timeout';

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
    onReconnect,
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
  const connectionIdRef = useRef(0);
  const stabilityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Tracks whether the hook has ever observed a successful onopen. Used
  // to gate the onReconnect callback so it fires on reconnects only.
  const hasConnectedBeforeRef = useRef(false);
  // Liveness watchdog refs.
  const lastMessageAtRef = useRef<number>(Date.now());
  const livenessIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Used for [WS] log correlation + the "reconnect after Xms" timing.
  const lastDisconnectAtRef = useRef<number | null>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [activeTimers, setActiveTimers] = useState<ActiveTimer[]>([]);
  const [onlineUsers, setOnlineUsers] = useState<number[]>([]);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [serverTime, setServerTime] = useState<string | null>(null);
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

    // Guard: don't create a second socket while one is OPEN or still CONNECTING
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) return;

    // Cancel any pending reconnect to avoid duplicate connections
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close any stale connection (e.g. in CLOSING state)
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

      // Track connection instance — stale handlers from closed
      // sockets will see a mismatched ID and bail out
      const thisConnectionId = ++connectionIdRef.current;

      ws.onopen = () => {
        if (!isMountedRef.current || connectionIdRef.current !== thisConnectionId) return;
        setIsConnected(true);
        setConnectionState('connected');
        setShowReconnectNotification(false);
        // Defer attempt-counter reset until connection has been stable for 5 s.
        // Prevents an infinite 1-req/s loop when the server immediately rejects.
        if (stabilityTimerRef.current) clearTimeout(stabilityTimerRef.current);
        stabilityTimerRef.current = setTimeout(() => {
          reconnectAttempts.current = 0;
          stabilityTimerRef.current = null;
        }, 5000);

        const isReconnect = hasConnectedBeforeRef.current;
        const attemptNumber = reconnectAttempts.current;
        if (isReconnect) {
          const ms = lastDisconnectAtRef.current
            ? Date.now() - lastDisconnectAtRef.current
            : 0;
          console.info(`[WS] Reconnected after ${ms}ms (attempt ${attemptNumber})`);
        } else {
          console.info(`[WS] Connected (attempt: ${attemptNumber})`);
        }

        // Reset liveness clock on every successful open.
        lastMessageAtRef.current = Date.now();
        // (Re)start liveness watchdog so a silent dead link triggers a
        // reconnect via close-code 4002.
        if (livenessIntervalRef.current) clearInterval(livenessIntervalRef.current);
        livenessIntervalRef.current = setInterval(() => {
          if (!isMountedRef.current) return;
          const idle = Date.now() - lastMessageAtRef.current;
          if (idle > LIVENESS_THRESHOLD_MS && wsRef.current?.readyState === WebSocket.OPEN) {
            console.info('[WS] Liveness timeout — forcing reconnect');
            try { wsRef.current.close(LIVENESS_CLOSE_CODE, LIVENESS_CLOSE_REASON); } catch { /* ignore */ }
          }
        }, LIVENESS_CHECK_INTERVAL_MS);

        onConnect?.();
        if (isReconnect) {
          onReconnect?.();
        }
        hasConnectedBeforeRef.current = true;

        // Re-subscribe to channels on (re)connection
        ws.send(JSON.stringify({ type: 'get_active_timers' }));
        ws.send(JSON.stringify({ type: 'get_online_users' }));
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current || connectionIdRef.current !== thisConnectionId) return;
        // Liveness: ANY message proves the link is alive.
        lastMessageAtRef.current = Date.now();
        try {
          const message: WebSocketMessage = JSON.parse(event.data);

          // Infrastructure messages (ping/pong) are NOT propagated to the
          // consumer's onMessage callback or to lastMessage.
          if (message.type === 'ping') {
            console.debug('[WS] Heartbeat OK');
            try {
              ws.send(JSON.stringify({ type: 'pong', timestamp: new Date().toISOString() }));
            } catch { /* ignore — onclose will handle */ }
            return;
          }
          if (message.type === 'pong') {
            console.debug('[WS] Heartbeat OK');
            return;
          }

          setLastMessage(message);

          switch (message.type) {
            case 'snapshot': {
              // Hydration payload sent immediately after (re)connect. Replace
              // local state wholesale so the UI matches the server's view
              // even if individual broadcasts were missed during the gap.
              const snapshotTimers = (message.active_timers as ActiveTimer[] | undefined) ?? [];
              const snapshotUsers = (message.online_users as number[] | undefined) ?? [];
              setActiveTimers(snapshotTimers);
              setOnlineUsers(snapshotUsers);
              if (typeof message.server_time === 'string') {
                setServerTime(message.server_time);
              }
              break;
            }
            case 'active_timers':
              setActiveTimers((message.timers as typeof activeTimers) || []);
              break;
            case 'online_users':
              setOnlineUsers((message.users as typeof onlineUsers) || []);
              break;
            case 'timer_started': {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const timerData = (message.data || message) as any;
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
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const stopData = (message.data || message) as any;
              setActiveTimers(prev => prev.filter(t => t.user_id !== stopData.user_id));
              break;
            }
            case 'timer_updated': {
              // Canonical channel for in-place activity_state mutations
              // (break/meeting start/end). Payload is the full active-timer
              // cache entry — replace the matching user's row.
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const updated = (message.data || message) as any;
              if (!updated || typeof updated.user_id !== 'number') break;
              setActiveTimers(prev => {
                const filtered = prev.filter(t => t.user_id !== updated.user_id);
                return [...filtered, updated as ActiveTimer];
              });
              break;
            }
            case 'team_added':
            case 'member_added':
            case 'project_created':
            case 'task_created':
              break;
            case 'notification':
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              if (message.data && (window as any).__handleIncomingNotification) {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
        if (!isMountedRef.current || connectionIdRef.current !== thisConnectionId) return;
        setIsConnected(false);
        wsRef.current = null;
        lastDisconnectAtRef.current = Date.now();
        console.info(`[WS] Disconnected: code=${_event?.code} reason=${_event?.reason || ''}`);

        // Cancel stability timer — short-lived connections keep increasing attempts
        if (stabilityTimerRef.current) {
          clearTimeout(stabilityTimerRef.current);
          stabilityTimerRef.current = null;
        }
        // Stop the liveness watchdog while disconnected; it will be
        // restarted on the next successful onopen.
        if (livenessIntervalRef.current) {
          clearInterval(livenessIntervalRef.current);
          livenessIntervalRef.current = null;
        }

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
        if (!isMountedRef.current || connectionIdRef.current !== thisConnectionId) return;
        onError?.(error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      setConnectionState('disconnected');
    }
  }, [isAuthenticated, getToken, getWebSocketUrl, onConnect, onReconnect, onDisconnect, onMessage, onError, autoReconnect, maxReconnectAttempts]);

  // ============================================
  // DISCONNECT
  // ============================================
  const disconnect = useCallback(() => {
    manualDisconnectRef.current = true;
    connectionIdRef.current++; // invalidate stale event handlers

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (stabilityTimerRef.current) {
      clearTimeout(stabilityTimerRef.current);
      stabilityTimerRef.current = null;
    }

    if (livenessIntervalRef.current) {
      clearInterval(livenessIntervalRef.current);
      livenessIntervalRef.current = null;
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
    if (stabilityTimerRef.current) {
      clearTimeout(stabilityTimerRef.current);
      stabilityTimerRef.current = null;
    }
    // Invalidate stale handlers and close any existing connection
    connectionIdRef.current++;
    if (wsRef.current) {
      try { wsRef.current.close(); } catch { /* ignore */ }
      wsRef.current = null;
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
        // Clear any pending reconnect to avoid racing with this connect
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
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

      if (stabilityTimerRef.current) {
        clearTimeout(stabilityTimerRef.current);
        stabilityTimerRef.current = null;
      }

      if (livenessIntervalRef.current) {
        clearInterval(livenessIntervalRef.current);
        livenessIntervalRef.current = null;
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
    serverTime,
    showReconnectNotification,
    notifyTimerStart,
    notifyTimerStop,
    notifyTimerUpdate,
    requestActiveTimers,
    requestOnlineUsers,
  };
}

export type { WebSocketMessage, ActiveTimer };
