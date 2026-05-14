// ============================================
// TIME TRACKER - ACTIVE TIMERS RENDER TESTS
// Covers the three activity_state branches: working / break / meeting.
// ============================================
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
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
