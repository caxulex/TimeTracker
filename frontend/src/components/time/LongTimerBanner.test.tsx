// ============================================
// TIME TRACKER - LONG TIMER BANNER TESTS (PR-B)
// ============================================
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import type { TimeEntry } from '../../types';

// ---- Mock dependencies ----
const stopTimerMutateMock = vi.fn();

vi.mock('../../stores/timerStore', () => ({
  useTimerStore: vi.fn(),
}));

vi.mock('../../hooks/useApi', () => ({
  useStopTimer: vi.fn(() => ({
    mutate: stopTimerMutateMock,
    isPending: false,
  })),
}));

// Stub the heavy EditEntryModal so we only verify the trigger contract.
vi.mock('./EditEntryModal', () => ({
  EditEntryModal: ({
    entry,
    isOpen,
    onClose,
  }: {
    entry: TimeEntry | null;
    isOpen: boolean;
    onClose: () => void;
  }) =>
    isOpen ? (
      <div data-testid="edit-entry-modal" data-entry-id={entry?.id ?? ''}>
        <button onClick={onClose} data-testid="edit-modal-close">close</button>
      </div>
    ) : null,
}));

import { LongTimerBanner } from './LongTimerBanner';
import { useTimerStore } from '../../stores/timerStore';

const useTimerStoreMock = useTimerStore as unknown as ReturnType<typeof vi.fn>;

function buildRunningEntry(overrides: Partial<TimeEntry> = {}): TimeEntry {
  return {
    id: 42,
    user_id: 1,
    project_id: 1,
    task_id: 11,
    start_time: new Date(Date.now() - 7 * 3600 * 1000).toISOString(),
    end_time: null,
    duration_seconds: 0,
    description: 'Deep work',
    is_running: true,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function setTimerState(state: {
  isRunning: boolean;
  currentEntry: TimeEntry | null;
  elapsedSeconds: number;
}) {
  useTimerStoreMock.mockReturnValue(state);
}

// ---- Notification API mock ----
type NotificationInstance = { title: string; options?: NotificationOptions };
const notificationCalls: NotificationInstance[] = [];
const requestPermissionMock = vi.fn();
let mockedPermission: NotificationPermission = 'default';

class MockNotification {
  static get permission(): NotificationPermission {
    return mockedPermission;
  }
  static requestPermission(
    cb?: (result: NotificationPermission) => void
  ): Promise<NotificationPermission> {
    return requestPermissionMock(cb);
  }
  constructor(title: string, options?: NotificationOptions) {
    notificationCalls.push({ title, options });
  }
}

beforeEach(() => {
  // The global test setup stubs localStorage with vi.fn() that don't persist;
  // wire a real Map-backed store so this component's reads/writes round-trip.
  const store = new Map<string, string>();
  const ls = window.localStorage as unknown as {
    getItem: ReturnType<typeof vi.fn>;
    setItem: ReturnType<typeof vi.fn>;
    removeItem: ReturnType<typeof vi.fn>;
    clear: ReturnType<typeof vi.fn>;
  };
  ls.getItem.mockImplementation((k: string) => (store.has(k) ? store.get(k)! : null));
  ls.setItem.mockImplementation((k: string, v: string) => {
    store.set(k, String(v));
  });
  ls.removeItem.mockImplementation((k: string) => {
    store.delete(k);
  });
  ls.clear.mockImplementation(() => store.clear());

  notificationCalls.length = 0;
  stopTimerMutateMock.mockReset();
  requestPermissionMock.mockReset();
  requestPermissionMock.mockResolvedValue('granted');
  mockedPermission = 'default';
  // Install Notification on window
  (window as unknown as { Notification: typeof MockNotification }).Notification =
    MockNotification as unknown as typeof Notification;
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('LongTimerBanner', () => {
  it('does_not_render_when_no_running_timer', () => {
    setTimerState({ isRunning: false, currentEntry: null, elapsedSeconds: 0 });
    const { container } = render(<LongTimerBanner />);
    expect(container.querySelector('[data-testid="long-timer-banner"]')).toBeNull();
  });

  it('does_not_render_when_elapsed_under_6h', () => {
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 5 * 3600 + 59 * 60,
    });
    const { container } = render(<LongTimerBanner />);
    expect(container.querySelector('[data-testid="long-timer-banner"]')).toBeNull();
  });

  it('renders_with_6h_message_when_elapsed_just_over_6h', () => {
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 6 * 3600 + 5,
    });
    render(<LongTimerBanner />);
    expect(screen.getByTestId('long-timer-banner')).toBeInTheDocument();
    expect(screen.getByText(/over 6 hours/i)).toBeInTheDocument();
  });

  it('renders_with_8h_message_at_8h_threshold', () => {
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 8 * 3600 + 5,
    });
    render(<LongTimerBanner />);
    expect(screen.getByText(/over 8 hours/i)).toBeInTheDocument();
  });

  it('keepGoing_button_dismisses_banner', () => {
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 6 * 3600 + 5,
    });
    const { container } = render(<LongTimerBanner />);
    expect(screen.getByTestId('long-timer-banner')).toBeInTheDocument();

    fireEvent.click(screen.getByText(/yes, keep going/i));

    expect(container.querySelector('[data-testid="long-timer-banner"]')).toBeNull();
    const stored = JSON.parse(localStorage.getItem('longTimerDismissals') || '{}');
    expect(stored['42']).toBe(6);
  });

  it('banner_reappears_at_next_threshold_after_dismissal', () => {
    // Dismiss at 6h
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 7 * 3600,
    });
    localStorage.setItem('longTimerDismissals', JSON.stringify({ '42': 6 }));

    const { rerender, container } = render(<LongTimerBanner />);
    // At 7h with 6 dismissed, banner should NOT render.
    expect(container.querySelector('[data-testid="long-timer-banner"]')).toBeNull();

    // Now elapsed crosses 8h
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 8 * 3600 + 5,
    });
    rerender(<LongTimerBanner />);

    expect(screen.getByTestId('long-timer-banner')).toBeInTheDocument();
    expect(screen.getByText(/over 8 hours/i)).toBeInTheDocument();
  });

  it('stopNow_button_calls_stopTimer', () => {
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 6 * 3600 + 5,
    });
    render(<LongTimerBanner />);
    fireEvent.click(screen.getByText(/stop now/i));
    expect(stopTimerMutateMock).toHaveBeenCalledTimes(1);
  });

  it('adjustEndTime_button_opens_EditEntryModal', () => {
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 6 * 3600 + 5,
    });
    render(<LongTimerBanner />);
    expect(screen.queryByTestId('edit-entry-modal')).toBeNull();

    fireEvent.click(screen.getByText(/adjust end time/i));

    const modal = screen.getByTestId('edit-entry-modal');
    expect(modal).toBeInTheDocument();
    expect(modal.getAttribute('data-entry-id')).toBe('42');
  });

  it('requests_notification_permission_on_first_render', async () => {
    mockedPermission = 'default';
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 6 * 3600 + 5,
    });
    await act(async () => {
      render(<LongTimerBanner />);
    });
    expect(requestPermissionMock).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem('longTimerNotificationPermission')).toBe('granted');
  });

  it('does_not_re_request_permission_after_denial', async () => {
    localStorage.setItem('longTimerNotificationPermission', 'denied');
    mockedPermission = 'denied';
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 6 * 3600 + 5,
    });
    await act(async () => {
      render(<LongTimerBanner />);
    });
    expect(requestPermissionMock).not.toHaveBeenCalled();
  });

  it('fires_system_notification_when_permission_granted', async () => {
    mockedPermission = 'granted';
    setTimerState({
      isRunning: true,
      currentEntry: buildRunningEntry(),
      elapsedSeconds: 6 * 3600 + 5,
    });
    await act(async () => {
      render(<LongTimerBanner />);
    });
    expect(notificationCalls.length).toBe(1);
    expect(notificationCalls[0].title).toMatch(/TimeTracker/i);
    expect(notificationCalls[0].options?.body).toMatch(/Deep work/);
    expect(notificationCalls[0].options?.body).toMatch(/6 hours/);
  });
});
