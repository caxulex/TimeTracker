// ============================================
// TIME TRACKER - CONNECTION STATUS INDICATOR TESTS
// TASK 7.2: Test visual connection status UI
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ConnectionStatusDot, ReconnectBanner } from './ConnectionStatusIndicator';

// Mock the WebSocket context
const mockContext = {
  isConnected: true,
  connectionState: 'connected' as 'connected' | 'reconnecting' | 'failed' | 'disconnected',
  connect: vi.fn(),
  disconnect: vi.fn(),
  reconnectNow: vi.fn(),
  send: vi.fn(() => true),
  activeTimers: [],
  onlineUsers: [],
  lastMessage: null,
  showReconnectNotification: false,
  notifyTimerStart: vi.fn(() => true),
  notifyTimerStop: vi.fn(() => true),
  notifyTimerUpdate: vi.fn(() => true),
  requestActiveTimers: vi.fn(() => true),
  requestOnlineUsers: vi.fn(() => true),
};

vi.mock('../contexts/WebSocketContext', () => ({
  useWebSocketContext: () => mockContext,
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('ConnectionStatusDot', () => {
  it('should render a green dot when connected', () => {
    mockContext.connectionState = 'connected';
    const { container } = render(<ConnectionStatusDot />);
    const dot = container.querySelector('[data-testid="connection-status-dot"]');
    expect(dot).toBeTruthy();
    expect(dot?.className).toContain('bg-green-500');
  });

  it('should render a yellow pulsing dot when reconnecting', () => {
    mockContext.connectionState = 'reconnecting';
    const { container } = render(<ConnectionStatusDot />);
    const dot = container.querySelector('[data-testid="connection-status-dot"]');
    expect(dot?.className).toContain('bg-yellow-400');
    expect(dot?.className).toContain('animate-pulse');
  });

  it('should render a red dot when failed', () => {
    mockContext.connectionState = 'failed';
    const { container } = render(<ConnectionStatusDot />);
    const dot = container.querySelector('[data-testid="connection-status-dot"]');
    expect(dot?.className).toContain('bg-red-500');
  });

  it('should render a gray dot when disconnected', () => {
    mockContext.connectionState = 'disconnected';
    const { container } = render(<ConnectionStatusDot />);
    const dot = container.querySelector('[data-testid="connection-status-dot"]');
    expect(dot?.className).toContain('bg-gray-400');
  });
});

describe('ReconnectBanner', () => {
  it('should not render when showReconnectNotification is false', () => {
    mockContext.showReconnectNotification = false;
    const { container } = render(<ReconnectBanner />);
    expect(container.firstChild).toBeNull();
  });

  it('should render when showReconnectNotification is true', () => {
    mockContext.showReconnectNotification = true;
    mockContext.connectionState = 'reconnecting';
    render(<ReconnectBanner />);
    expect(screen.getByText(/Real-time connection lost/)).toBeInTheDocument();
  });

  it('should show "Retrying..." when reconnecting', () => {
    mockContext.showReconnectNotification = true;
    mockContext.connectionState = 'reconnecting';
    render(<ReconnectBanner />);
    expect(screen.getByText(/Retrying/)).toBeInTheDocument();
  });

  it('should show "Updates may be delayed" when failed', () => {
    mockContext.showReconnectNotification = true;
    mockContext.connectionState = 'failed';
    render(<ReconnectBanner />);
    expect(screen.getByText(/Updates may be delayed/)).toBeInTheDocument();
  });

  it('should call reconnectNow when button is clicked', () => {
    mockContext.showReconnectNotification = true;
    mockContext.connectionState = 'failed';
    mockContext.reconnectNow = vi.fn();

    render(<ReconnectBanner />);
    const button = screen.getByText('Reconnect Now');
    fireEvent.click(button);

    expect(mockContext.reconnectNow).toHaveBeenCalledTimes(1);
  });
});
