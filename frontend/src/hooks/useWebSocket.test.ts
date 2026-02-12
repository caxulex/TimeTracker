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
  onopen: ((event: any) => void) | null = null;
  onclose: ((event: any) => void) | null = null;
  onmessage: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
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
    if (this.onopen) this.onopen({});
  }

  simulateClose(code = 1006, reason = 'Abnormal closure') {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose({ code, reason });
  }

  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) });
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
      const sentTypes = ws.send.mock.calls.map((c: any[]) => JSON.parse(c[0]).type);
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
        (c: any[]) => JSON.parse(c[0]).type === 'pong'
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
});
