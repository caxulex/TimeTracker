// ============================================
// TIME TRACKER - WEBSOCKET HOOK
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
  reconnectInterval?: number;
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

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const { isAuthenticated } = useAuthStore();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  const [isConnected, setIsConnected] = useState(false);
  const [activeTimers, setActiveTimers] = useState<ActiveTimer[]>([]);
  const [onlineUsers, setOnlineUsers] = useState<number[]>([]);

  const getToken = useCallback(() => {
    return localStorage.getItem('access_token');
  }, []);

  const getWebSocketUrl = useCallback(() => {
    const token = getToken();
    if (!token) return null;
    
    // Get API URL from environment variable
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const url = new URL(apiUrl);
    const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = url.host;
    return protocol + '//' + host + '/api/ws/ws?token=' + token;
  }, [getToken]);

  const connect = useCallback(() => {
    const token = getToken();
    if (!isAuthenticated || !token) {
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const wsUrl = getWebSocketUrl();
    if (!wsUrl) return;

    try {
      console.log('Connecting to WebSocket:', wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        reconnectAttempts.current = 0;
        onConnect?.();
        
        ws.send(JSON.stringify({ type: 'get_active_timers' }));
        ws.send(JSON.stringify({ type: 'get_online_users' }));
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          
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
            case 'timer_started':
              setActiveTimers(prev => {
                const filtered = prev.filter(t => t.user_id !== message.user_id);
                return [...filtered, {
                  user_id: message.user_id,
                  user_name: message.user_name,
                  project_id: message.project_id,
                  project_name: message.project_name,
                  task_id: message.task_id,
                  task_name: message.task_name,
                  description: message.description,
                  start_time: message.start_time,
                }];
              });
              break;
            case 'timer_stopped':
              setActiveTimers(prev => prev.filter(t => t.user_id !== message.user_id));
              break;
            case 'team_added':
            case 'member_added':
            case 'project_created':
            case 'task_created':
              // These events will trigger query invalidation in the consuming component
              console.log('Received update:', message.type, message.data);
              break;
          }
          
          onMessage?.(message);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);
        wsRef.current = null;
        onDisconnect?.();

        if (autoReconnect && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          console.log('Reconnecting... Attempt ' + reconnectAttempts.current + '/' + maxReconnectAttempts);
          reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        onError?.(error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
    }
  }, [isAuthenticated, getToken, getWebSocketUrl, onConnect, onDisconnect, onMessage, onError, autoReconnect, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
  }, []);

  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    console.warn('WebSocket is not connected');
    return false;
  }, []);

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
    return send({
      type: 'timer_stop',
      ...data,
    });
  }, [send]);

  const notifyTimerUpdate = useCallback((elapsed_seconds: number) => {
    return send({
      type: 'timer_update',
      elapsed_seconds,
    });
  }, [send]);

  const requestActiveTimers = useCallback((team_id?: number) => {
    return send({
      type: 'get_active_timers',
      team_id,
    });
  }, [send]);

  const requestOnlineUsers = useCallback((team_id?: number) => {
    return send({
      type: 'get_online_users',
      team_id,
    });
  }, [send]);

  useEffect(() => {
    const token = getToken();
    if (isAuthenticated && token) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [isAuthenticated, getToken, connect, disconnect]);

  return {
    isConnected,
    connect,
    disconnect,
    send,
    activeTimers,
    onlineUsers,
    notifyTimerStart,
    notifyTimerStop,
    notifyTimerUpdate,
    requestActiveTimers,
    requestOnlineUsers,
  };
}

export type { WebSocketMessage, ActiveTimer };
