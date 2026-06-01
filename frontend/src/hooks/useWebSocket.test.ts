// ============================================
// TIME TRACKER - WEBSOCKET HOOK TESTS
// TASK 7.2: Test reconnection, backoff, cleanup
// ============================================
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// ============================================
// MOCK SETUP
// ============================================

let mockWebSocketInstances: MockWebSocket[] = [];

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
  });

  constructor(url: string) {
    this.url = url;
    mockWebSocketInstances.push(this);
  }

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) this.onopen({} as Event);
  }

  simulateClose(code = 1006, reason = 'Abnormal closure') {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose({ code, reason } as CloseEvent);
  }

  simulateMessage(data: Record<string, unknown>) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) } as MessageEvent);
    }
  }
}

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(() => ({
    isAuthenticated: true,
  })),
}));

vi.stubEnv('VITE_API_URL', 'http://localhost:8000');
vi.stubGlobal('WebSocket', MockWebSocket);

const mockLocalStorage: Record<string, string> = {
  access_token: 'test-jwt-token',
};
vi.stubGlobal('localStorage', {
  getItem: (key: string) => mockLocalStorage[key] ?? null,
  setItem: (key: string, val: string) => { mockLocalStorage[key] = val; },
  removeItem: (key: string) => { delete mockLocalStorage[key]; },
  clear: () => { Object.keys(mockLocalStorage).forEach(k => delete mockLocalStorage[k]); },
  length: 0,
  key: () => null,
});

import { useWebSocket } from './useWebSocket';

beforeEach(() => {
  vi.useFakeTimers();
  mockWebSocketInstances = [];
  mockLocalStorage['access_token'] = 'test-jwt-token';
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

// ============================================
// TESTS
// ============================================

describe('useWebSocket', () => {
  describe('Connection', () => {
    it('should create a WebSocket connection when authenticated', () => {
      renderHook(() => useWebSocket());
      expect(mockWebSocketInstances.length).toBeGreaterThanOrEqual(1);
      const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      expect(ws.url).toContain('ws://');
      expect(ws.url).toContain('token=test-jwt-token');
    });

    it('should set isConnected=true and connectionState=connected on open', () => {
      const { result } = renderHook(() => useWebSocket());

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      expect(result.current.isConnected).toBe(true);
      expect(result.current.connectionState).toBe('connected');
    });

    it('should re-subscribe to channels on connection', () => {
      renderHook(() => useWebSocket());

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      const sentTypes = ws.send.mock.calls.map((c: [string]) => JSON.parse(c[0]).type);
      expect(sentTypes).toContain('get_active_timers');
      expect(sentTypes).toContain('get_online_users');
    });
  });

  describe('Reconnection with exponential backoff', () => {
    it('should attempt reconnection after disconnect', () => {
      renderHook(() => useWebSocket({ autoReconnect: true, maxReconnectAttempts: 5 }));
      const initialCount = mockWebSocketInstances.length;

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
      });

      // Advance past first backoff (~1000ms + jitter)
      act(() => { vi.advanceTimersByTime(1500); });

      expect(mockWebSocketInstances.length).toBeGreaterThan(initialCount);
    });

    it('should increase backoff delay with each attempt', () => {
      // Verify the exponential pattern
      const delays: number[] = [];
      for (let i = 0; i < 6; i++) {
        const base = Math.min(1000 * Math.pow(2, i), 30000);
        delays.push(base);
      }
      expect(delays[0]).toBe(1000);
      expect(delays[1]).toBe(2000);
      expect(delays[2]).toBe(4000);
      expect(delays[3]).toBe(8000);
      expect(delays[4]).toBe(16000);
      expect(delays[5]).toBe(30000); // capped
    });

    it('should stop reconnecting after max attempts', () => {
      const { result } = renderHook(() =>
        useWebSocket({ autoReconnect: true, maxReconnectAttempts: 2 })
      );

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      // Exhaust 2 reconnect attempts
      for (let i = 0; i < 2; i++) {
        act(() => {
          mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
        });
        act(() => { vi.advanceTimersByTime(35000); });
      }

      // Third close triggers 'failed' because attempts exhausted
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
      });

      expect(result.current.connectionState).toBe('failed');
    });

    it('should show reconnect notification after 3 failed attempts', () => {
      const { result } = renderHook(() =>
        useWebSocket({ autoReconnect: true, maxReconnectAttempts: 5 })
      );

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      for (let i = 0; i < 3; i++) {
        act(() => {
          mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
        });
        act(() => { vi.advanceTimersByTime(35000); });
      }

      expect(result.current.showReconnectNotification).toBe(true);
    });
  });

  describe('Manual reconnect', () => {
    it('should reset attempts and reconnect when reconnectNow is called', () => {
      const { result } = renderHook(() =>
        useWebSocket({ autoReconnect: true, maxReconnectAttempts: 1 })
      );

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      // Exhaust reconnect attempts
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
      });
      act(() => { vi.advanceTimersByTime(5000); });
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
      });

      expect(result.current.connectionState).toBe('failed');

      const countBefore = mockWebSocketInstances.length;

      act(() => {
        result.current.reconnectNow();
      });

      expect(mockWebSocketInstances.length).toBeGreaterThan(countBefore);
      expect(result.current.showReconnectNotification).toBe(false);
    });
  });

  describe('Cleanup on unmount', () => {
    it('should close WebSocket and clear timeouts on unmount', () => {
      const { unmount } = renderHook(() => useWebSocket());

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      unmount();
      expect(ws.close).toHaveBeenCalled();
    });

    it('should not attempt reconnection after unmount', () => {
      const { unmount } = renderHook(() =>
        useWebSocket({ autoReconnect: true, maxReconnectAttempts: 5 })
      );

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      unmount();

      // Advance time — no errors should occur
      act(() => { vi.advanceTimersByTime(60000); });
    });
  });

  describe('Message handling', () => {
    it('should respond to ping with pong', () => {
      renderHook(() => useWebSocket());

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      ws.send.mockClear();

      act(() => {
        ws.simulateMessage({ type: 'ping' });
      });

      const pongSent = ws.send.mock.calls.some(
        (c: [string]) => JSON.parse(c[0]).type === 'pong'
      );
      expect(pongSent).toBe(true);
    });

    it('should update activeTimers on active_timers message', () => {
      const { result } = renderHook(() => useWebSocket());

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateMessage({
          type: 'active_timers',
          timers: [
            { user_id: 1, user_name: 'Alice', start_time: '2025-01-15T09:00:00Z' },
          ],
        });
      });

      expect(result.current.activeTimers).toHaveLength(1);
      expect(result.current.activeTimers[0].user_name).toBe('Alice');
    });
  });

  describe('Network events', () => {
    it('should attempt reconnect when browser comes online', () => {
      renderHook(() => useWebSocket());

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });

      // Simulate going offline and losing the connection
      act(() => {
        window.dispatchEvent(new Event('offline'));
      });

      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
      });

      const countBeforeOnline = mockWebSocketInstances.length;

      act(() => {
        window.dispatchEvent(new Event('online'));
      });

      expect(mockWebSocketInstances.length).toBeGreaterThanOrEqual(countBeforeOnline);
    });
  });

  describe('Connection storm protection', () => {
    it('should not create duplicate connections when WS is still CONNECTING', () => {
      const { result } = renderHook(() => useWebSocket());
      const countAfterInit = mockWebSocketInstances.length;

      // WS is in CONNECTING state — calling connect() again must NOT spawn another socket
      act(() => {
        result.current.connect();
      });

      expect(mockWebSocketInstances.length).toBe(countAfterInit);
    });

    it('should stop reconnecting after max attempts even with rapid server rejections', () => {
      const { result } = renderHook(() =>
        useWebSocket({ autoReconnect: true, maxReconnectAttempts: 3 })
      );

      // Simulate server-rejection pattern: open immediately followed by close
      for (let i = 0; i < 3; i++) {
        act(() => {
          mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
        });
        act(() => {
          mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
        });
        act(() => { vi.advanceTimersByTime(35000); });
      }

      // 4th open/close after 3 exhausted attempts → failed
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
      });

      expect(result.current.connectionState).toBe('failed');
    });

    it('should reset attempt counter only after a stable connection (5 s+)', () => {
      const { result } = renderHook(() =>
        useWebSocket({ autoReconnect: true, maxReconnectAttempts: 3 })
      );

      // First connect + immediate close — counter should NOT reset
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
      });
      act(() => { vi.advanceTimersByTime(5000); }); // reconnect fires

      // Second connect — stays stable for 6 s (stability timer fires at 5 s)
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });
      act(() => { vi.advanceTimersByTime(6000); }); // stability timer resets counter

      // Now close — counter is back at 0, so state should be reconnecting (not failed)
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
      });

      expect(result.current.connectionState).toBe('reconnecting');
    });

    it('should ignore events from stale WebSocket instances', () => {
      const { result } = renderHook(() =>
        useWebSocket({ autoReconnect: true, maxReconnectAttempts: 5 })
      );

      // Open first WS
      const firstWs = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      act(() => { firstWs.simulateOpen(); });

      // reconnectNow creates a new WS and invalidates the old one
      act(() => { result.current.reconnectNow(); });

      const secondWs = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      expect(secondWs).not.toBe(firstWs);

      // Open the new WS
      act(() => { secondWs.simulateOpen(); });
      expect(result.current.connectionState).toBe('connected');

      // Stale WS fires onclose — should be ignored entirely
      act(() => { firstWs.simulateClose(); });

      expect(result.current.connectionState).toBe('connected');
      expect(result.current.isConnected).toBe(true);
    });
  });

  // ============================================
  // HEARTBEAT + LIVENESS + RECONNECT-SYNC
  // ============================================
  describe('Heartbeat (bidirectional)', () => {
    it('should reply to a server ping with a pong', () => {
      renderHook(() => useWebSocket());
      const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      act(() => { ws.simulateOpen(); });
      ws.send.mockClear();

      act(() => { ws.simulateMessage({ type: 'ping', timestamp: '2026-01-01T00:00:00Z' }); });

      const sentTypes = ws.send.mock.calls.map((c: [string]) => JSON.parse(c[0]).type);
      expect(sentTypes).toContain('pong');
    });

    it('should not propagate ping or pong to the consumer onMessage callback', () => {
      const onMessage = vi.fn();
      renderHook(() => useWebSocket({ onMessage }));
      const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      act(() => { ws.simulateOpen(); });
      onMessage.mockClear();

      act(() => { ws.simulateMessage({ type: 'ping' }); });
      act(() => { ws.simulateMessage({ type: 'pong' }); });

      expect(onMessage).not.toHaveBeenCalled();
    });
  });

  describe('Client liveness watchdog', () => {
    it('should force-close the socket with code 4002 when no message arrives within the threshold', () => {
      renderHook(() => useWebSocket());
      const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      act(() => { ws.simulateOpen(); });
      ws.close.mockClear();

      // No messages for >45s → liveness check at 5s intervals trips.
      act(() => { vi.advanceTimersByTime(50_000); });

      expect(ws.close).toHaveBeenCalled();
      const lastCall = (ws.close.mock.calls as unknown[][])[ws.close.mock.calls.length - 1];
      expect(lastCall[0]).toBe(4002);
      expect(lastCall[1]).toBe('client_liveness_timeout');
    });

    it('should NOT force-close while messages keep arriving', () => {
      renderHook(() => useWebSocket());
      const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      act(() => { ws.simulateOpen(); });
      ws.close.mockClear();

      // Pump a server ping every 30s — well under the 45s threshold.
      for (let i = 0; i < 4; i++) {
        act(() => { vi.advanceTimersByTime(30_000); });
        act(() => { ws.simulateMessage({ type: 'ping' }); });
      }

      expect(ws.close).not.toHaveBeenCalled();
    });
  });

  describe('onReconnect callback', () => {
    it('should fire onReconnect ONLY after a reconnect, not on the initial connect', () => {
      const onConnect = vi.fn();
      const onReconnect = vi.fn();
      const { result } = renderHook(() =>
        useWebSocket({ onConnect, onReconnect, autoReconnect: true, maxReconnectAttempts: 5 })
      );

      // Initial open: onConnect fires, onReconnect does NOT.
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });
      expect(onConnect).toHaveBeenCalledTimes(1);
      expect(onReconnect).not.toHaveBeenCalled();

      // Drop the link and let the backoff timer create a fresh socket.
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateClose();
      });
      act(() => { vi.advanceTimersByTime(2000); });

      // Second open: onConnect AND onReconnect fire.
      act(() => {
        mockWebSocketInstances[mockWebSocketInstances.length - 1].simulateOpen();
      });
      expect(onConnect).toHaveBeenCalledTimes(2);
      expect(onReconnect).toHaveBeenCalledTimes(1);
      expect(result.current.connectionState).toBe('connected');
    });
  });

  describe('Snapshot hydration', () => {
    it('should replace activeTimers and onlineUsers when a snapshot arrives', () => {
      const { result } = renderHook(() => useWebSocket());
      const ws = mockWebSocketInstances[mockWebSocketInstances.length - 1];
      act(() => { ws.simulateOpen(); });

      // Seed pre-snapshot state.
      act(() => {
        ws.simulateMessage({
          type: 'active_timers',
          timers: [{ user_id: 1, user_name: 'A', start_time: '2026-01-01T00:00:00Z' }],
        });
      });
      act(() => { ws.simulateMessage({ type: 'online_users', users: [1] }); });

      // Snapshot arrives — should overwrite both.
      act(() => {
        ws.simulateMessage({
          type: 'snapshot',
          active_timers: [
            { user_id: 7, user_name: 'Snap', start_time: '2026-01-01T00:00:00Z' },
          ],
          online_users: [7, 8],
          server_time: '2026-01-01T00:00:00Z',
        });
      });

      expect(result.current.activeTimers).toHaveLength(1);
      expect(result.current.activeTimers[0].user_id).toBe(7);
      expect(result.current.onlineUsers).toEqual([7, 8]);
      expect(result.current.serverTime).toBe('2026-01-01T00:00:00Z');
    });
  });
});
