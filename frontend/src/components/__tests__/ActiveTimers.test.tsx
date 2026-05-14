// ============================================
// TIME TRACKER - ACTIVE TIMERS RENDER TESTS
// Covers the three activity_state branches: working / break / meeting,
// and the state-anchored duration display.
// ============================================
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { ActiveTimers } from '../ActiveTimers';
import type { ActiveTimer } from '../../contexts/WebSocketContext';

// Mock the WebSocket context so we control the activeTimers payload.
vi.mock('../../contexts/WebSocketContext', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>;
  return {
    ...actual,
    useWebSocketContext: () => mockCtx,
  };
});

let mockCtx: {
  isConnected: boolean;
  activeTimers: ActiveTimer[];
  requestActiveTimers: (id?: number) => void;
};

function setCtx(timers: ActiveTimer[]) {
  mockCtx = {
    isConnected: true,
    activeTimers: timers,
    requestActiveTimers: () => {},
  };
}

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ActiveTimers />
    </QueryClientProvider>
  );
}

describe('ActiveTimers — activity_state rendering', () => {
  const base: ActiveTimer = {
    user_id: 1,
    user_name: 'Alice',
    project_id: 10,
    project_name: 'Paradise Home Health Care',
    task_id: 5,
    task_name: 'Charting',
    start_time: new Date(Date.now() - 60_000).toISOString(),
  };

  it('renders working state with project + task', () => {
    setCtx([{ ...base, activity_state: 'working' }]);
    renderPanel();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    // Project + task line uses bullet separator.
    expect(
      screen.getByText(/Paradise Home Health Care.*Charting/)
    ).toBeInTheDocument();
    // No break / meeting indicators.
    expect(screen.queryByText(/On break/)).not.toBeInTheDocument();
    expect(screen.queryByText(/In meeting/)).not.toBeInTheDocument();
  });

  it('renders break state with break_type label', () => {
    setCtx([
      {
        ...base,
        activity_state: 'break',
        break_type: 'lunch',
      },
    ]);
    renderPanel();
    expect(screen.getByText(/On break/)).toBeInTheDocument();
    expect(screen.getByText(/Lunch/)).toBeInTheDocument();
  });

  it('renders meeting state with meeting title and no project', () => {
    setCtx([
      {
        ...base,
        project_id: undefined,
        project_name: undefined,
        task_name: undefined,
        activity_state: 'meeting',
        meeting_type: 'client',
        meeting_title: 'Weekly sync',
      },
    ]);
    renderPanel();
    expect(screen.getByText(/In meeting/)).toBeInTheDocument();
    expect(screen.getByText(/Weekly sync/)).toBeInTheDocument();
    // Project label should not appear in the meeting branch.
    expect(screen.queryByText('Paradise Home Health Care')).not.toBeInTheDocument();
  });
});

describe('ActiveTimers — state-anchored elapsed display', () => {
  // Freeze "now" so the panel's once-per-second ticker is deterministic.
  const FIXED_NOW = new Date('2026-05-14T12:00:00.000Z').getTime();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(FIXED_NOW));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const baseTimer: ActiveTimer = {
    user_id: 1,
    user_name: 'Bob',
    project_id: 10,
    project_name: 'P',
    // Started working 1 hour ago.
    start_time: new Date(FIXED_NOW - 3600 * 1000).toISOString(),
    elapsed_seconds: 3600,
  };

  it('working state shows duration anchored to start_time', () => {
    setCtx([
      {
        ...baseTimer,
        activity_state: 'working',
        state_started_at: baseTimer.start_time,
        state_elapsed_seconds: 3600,
      },
    ]);
    renderPanel();
    expect(screen.getByText('01:00:00')).toBeInTheDocument();
  });

  it('break state shows the BREAK duration (anchored to state_started_at), not the work elapsed', () => {
    // User has been working an hour but JUST went on break 74s ago.
    const breakStartedAt = new Date(FIXED_NOW - 74 * 1000).toISOString();
    setCtx([
      {
        ...baseTimer,
        activity_state: 'break',
        break_type: 'lunch',
        // Work elapsed is frozen at 1h, but the panel must show break duration.
        elapsed_seconds: 3600,
        state_started_at: breakStartedAt,
        state_elapsed_seconds: 74,
      },
    ]);
    renderPanel();
    // 74s -> 00:01:14, NOT 01:00:00 / 01:00:14.
    expect(screen.getByText('00:01:14')).toBeInTheDocument();
    expect(screen.queryByText('01:00:00')).not.toBeInTheDocument();
  });

  it('break state does NOT tick forward when state_started_at is stable', () => {
    // state_started_at is fixed: we advance the wall clock but the props
    // don't change. Since formatElapsed re-derives from state_started_at
    // every re-render, advancing time SHOULD change the display — but
    // the displayed value must NEVER exceed the actual seconds elapsed
    // since state_started_at, i.e. it must not drift independently.
    const breakStartedAt = new Date(FIXED_NOW - 10 * 1000).toISOString();
    setCtx([
      {
        ...baseTimer,
        activity_state: 'break',
        break_type: 'short',
        elapsed_seconds: 3600,
        state_started_at: breakStartedAt,
        state_elapsed_seconds: 10,
      },
    ]);
    renderPanel();
    expect(screen.getByText('00:00:10')).toBeInTheDocument();

    // Advance the wall clock by 5s. The component's internal setInterval
    // tick should re-render and display 00:00:15 — the value derived
    // from (now - state_started_at), NOT a freely-running local counter
    // started from elapsed_seconds (3600).
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.getByText('00:00:15')).toBeInTheDocument();
    // And critically, the work-time figure (which the buggy panel used
    // to surface) is nowhere on screen.
    expect(screen.queryByText(/01:00:/)).not.toBeInTheDocument();
  });

  it('meeting state displays the meeting duration from state_started_at', () => {
    const meetingStartedAt = new Date(FIXED_NOW - 125 * 1000).toISOString();
    setCtx([
      {
        ...baseTimer,
        project_id: undefined,
        project_name: undefined,
        activity_state: 'meeting',
        meeting_type: 'internal',
        meeting_title: 'Standup',
        state_started_at: meetingStartedAt,
        state_elapsed_seconds: 125,
      },
    ]);
    renderPanel();
    // 125s -> 00:02:05.
    expect(screen.getByText('00:02:05')).toBeInTheDocument();
  });
});
