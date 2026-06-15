import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BreakControls } from '../BreakControls';

const mockStartBreak = vi.fn();
const mockEndBreak = vi.fn();
const mockFetchTimer = vi.fn();
const mockAddNotification = vi.fn();

vi.mock('../../../stores/sessionStore', () => ({
  useSessionStore: vi.fn(() => ({
    activeBreak: null,
    breakElapsedSeconds: 0,
    isLoading: false,
    startBreak: mockStartBreak,
    endBreak: mockEndBreak,
  })),
  formatDuration: (seconds: number) => `${seconds}s`,
}));

vi.mock('../../../stores/timerStore', () => ({
  useTimerStore: vi.fn(() => ({
    fetchTimer: mockFetchTimer,
  })),
}));

vi.mock('../../../hooks/useNotifications', () => ({
  useNotifications: () => ({
    addNotification: mockAddNotification,
  }),
}));

describe('BreakControls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'innerWidth', { value: 1024, configurable: true });
    Object.defineProperty(window, 'innerHeight', { value: 768, configurable: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders and opens at narrow viewport widths without crashing', async () => {
    Object.defineProperty(window, 'innerWidth', { value: 375, configurable: true });

    const user = userEvent.setup();
    render(<BreakControls />);

    await user.click(screen.getByRole('button', { name: /break/i }));

    expect(await screen.findByTestId('break-menu')).toBeInTheDocument();
    expect(screen.getByText(/short break/i)).toBeInTheDocument();
    expect(screen.getByText(/lunch break/i)).toBeInTheDocument();
    expect(screen.getByText(/other break/i)).toBeInTheDocument();
  });

  it('shifts horizontally and flips upward on mobile when edge overflow would occur', async () => {
    Object.defineProperty(window, 'innerWidth', { value: 320, configurable: true });
    Object.defineProperty(window, 'innerHeight', { value: 640, configurable: true });

    const user = userEvent.setup();
    render(<BreakControls />);

    await user.click(screen.getByTestId('break-menu-trigger'));

    const trigger = screen.getByTestId('break-menu-trigger');
    const menu = await screen.findByTestId('break-menu');

    vi.spyOn(trigger, 'getBoundingClientRect').mockReturnValue({
      x: 4,
      y: 200,
      width: 96,
      height: 32,
      top: 200,
      right: 100,
      bottom: 232,
      left: 4,
      toJSON: () => ({}),
    });

    vi.spyOn(menu, 'getBoundingClientRect').mockReturnValue({
      x: 0,
      y: 0,
      width: 192,
      height: 144,
      top: 0,
      right: 192,
      bottom: 144,
      left: 0,
      toJSON: () => ({}),
    });

    fireEvent(window, new Event('resize'));

    await waitFor(() => {
      const left = Number.parseFloat(menu.style.left || '0');
      const top = Number.parseFloat(menu.style.top || '0');
      expect(left).toBeGreaterThanOrEqual(8);
      expect(top).toBeLessThan(200);
      expect(menu.style.position).toBe('fixed');
    });
  });
});
