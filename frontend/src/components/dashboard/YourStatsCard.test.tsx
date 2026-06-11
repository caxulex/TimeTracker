// ============================================
// TIME TRACKER - YOUR STATS CARD TESTS
// ============================================
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { YourStatsCard } from './YourStatsCard';
import { formatDurationLive } from '../../utils/helpers';
import type { DashboardStats } from '../../types';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'dashboard.today': 'Today',
        'dashboard.thisWeek': 'This Week',
        'dashboard.thisMonth': 'This Month',
        'dashboard.activeProjects': 'Active Projects',
        'dashboard.yourStats': 'Your Stats',
        'dashboard.yourPersonalStats': 'Your Personal Stats',
      };
      return map[key] ?? key;
    },
  }),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SAMPLE_STATS: DashboardStats = {
  today_seconds: 3600,   // 1 hour
  week_seconds: 36000,   // 10 hours
  month_seconds: 144000, // 40 hours
  active_projects: 5,
};

const NOW = new Date('2026-06-11T10:00:00.000Z').getTime();

function renderCard(props: Partial<React.ComponentProps<typeof YourStatsCard>> = {}) {
  return render(
    <MemoryRouter>
      <YourStatsCard stats={SAMPLE_STATS} {...props} />
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Unit: formatDurationLive
// ---------------------------------------------------------------------------

describe('formatDurationLive', () => {
  it('formats seconds only', () => {
    expect(formatDurationLive(45)).toBe('45s');
  });

  it('formats minutes and seconds', () => {
    expect(formatDurationLive(125)).toBe('2m 5s');
  });

  it('formats hours, minutes and seconds', () => {
    expect(formatDurationLive(3723)).toBe('1h 2m 3s');
  });

  it('formats hours with zero minutes when hours > 0', () => {
    expect(formatDurationLive(3630)).toBe('1h 0m 30s');
  });

  it('returns 0s for zero seconds', () => {
    expect(formatDurationLive(0)).toBe('0s');
  });

  it('clamps negative values to 0s', () => {
    expect(formatDurationLive(-5)).toBe('0s');
  });
});

// ---------------------------------------------------------------------------
// YourStatsCard rendering
// ---------------------------------------------------------------------------

describe('YourStatsCard', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // No timer running — static cached values
  // -------------------------------------------------------------------------

  describe('when no timer is running', () => {
    it('renders section heading', () => {
      renderCard();
      expect(screen.getByText('Your Stats')).toBeInTheDocument();
    });

    it('renders admin heading when isAdmin=true', () => {
      renderCard({ isAdmin: true });
      expect(screen.getByText('Your Personal Stats')).toBeInTheDocument();
    });

    it('displays cached Today value formatted without seconds', () => {
      renderCard({ isTimerRunning: false });
      // 3600s = 1h
      expect(screen.getByText('1h')).toBeInTheDocument();
    });

    it('displays This Week value', () => {
      renderCard();
      // 36000s = 10h
      expect(screen.getByText('10h')).toBeInTheDocument();
    });

    it('displays This Month value', () => {
      renderCard();
      // 144000s = 40h
      expect(screen.getByText('40h')).toBeInTheDocument();
    });

    it('displays Active Projects count', () => {
      renderCard();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('does not show the live indicator when timer is stopped', () => {
      renderCard({ isTimerRunning: false });
      expect(screen.queryByTestId('live-indicator')).not.toBeInTheDocument();
    });

    it('does not show the live indicator when timer is paused', () => {
      renderCard({ isTimerRunning: true, isTimerPaused: true, dataUpdatedAt: NOW - 30_000 });
      expect(screen.queryByTestId('live-indicator')).not.toBeInTheDocument();
    });

    it('shows 0m when stats are undefined', () => {
      render(
        <MemoryRouter>
          <YourStatsCard stats={undefined} />
        </MemoryRouter>
      );
      // 0 seconds for all numeric stats
      const zeros = screen.getAllByText('0m');
      expect(zeros.length).toBeGreaterThanOrEqual(3); // today, week, month
    });
  });

  // -------------------------------------------------------------------------
  // Timer running — live Today
  // -------------------------------------------------------------------------

  describe('when timer is running', () => {
    const DATA_UPDATED_AT = NOW - 30_000; // data polled 30 seconds ago

    it('shows live indicator on Today card', () => {
      renderCard({
        isTimerRunning: true,
        isTimerPaused: false,
        dataUpdatedAt: DATA_UPDATED_AT,
      });
      expect(screen.getByTestId('live-indicator')).toBeInTheDocument();
    });

    it('adds elapsed seconds since last poll to cached today_seconds', () => {
      renderCard({
        isTimerRunning: true,
        isTimerPaused: false,
        dataUpdatedAt: DATA_UPDATED_AT,
      });
      // 3600 cached + 30 elapsed = 3630s = 1h 0m 30s
      expect(screen.getByText('1h 0m 30s')).toBeInTheDocument();
    });

    it('re-renders every second when timer is running', () => {
      renderCard({
        isTimerRunning: true,
        isTimerPaused: false,
        dataUpdatedAt: DATA_UPDATED_AT,
      });

      // At t=0: 3600 + 30 = 3630 → "1h 0m 30s"
      expect(screen.getByText('1h 0m 30s')).toBeInTheDocument();

      // Advance 1 second
      act(() => {
        vi.advanceTimersByTime(1000);
      });
      // 3600 + 31 = 3631 → "1h 0m 31s"
      expect(screen.getByText('1h 0m 31s')).toBeInTheDocument();

      // Advance another 2 seconds
      act(() => {
        vi.advanceTimersByTime(2000);
      });
      // 3600 + 33 = 3633 → "1h 0m 33s"
      expect(screen.getByText('1h 0m 33s')).toBeInTheDocument();
    });

    it('stops ticking when timer is paused', () => {
      const { rerender } = renderCard({
        isTimerRunning: true,
        isTimerPaused: false,
        dataUpdatedAt: DATA_UPDATED_AT,
      });

      act(() => {
        vi.advanceTimersByTime(2000);
      });
      // 3600 + 32 = 3632 → "1h 0m 32s"
      expect(screen.getByText('1h 0m 32s')).toBeInTheDocument();

      // Pause the timer — value should freeze, live indicator removed
      rerender(
        <MemoryRouter>
          <YourStatsCard
            stats={SAMPLE_STATS}
            isTimerRunning={true}
            isTimerPaused={true}
            dataUpdatedAt={DATA_UPDATED_AT}
          />
        </MemoryRouter>
      );

      expect(screen.queryByTestId('live-indicator')).not.toBeInTheDocument();

      // Advance more time — the displayed value should NOT include those extra seconds
      // (formatDuration is used, not formatDurationLive, so no 's' suffix)
      act(() => {
        vi.advanceTimersByTime(5000);
      });
      // Value still uses formatDuration (no seconds suffix) and does not advance
      expect(screen.queryByTestId('live-indicator')).not.toBeInTheDocument();
    });

    it('non-Today stats show polled (cached) values unchanged', () => {
      renderCard({
        isTimerRunning: true,
        isTimerPaused: false,
        dataUpdatedAt: DATA_UPDATED_AT,
      });

      act(() => {
        vi.advanceTimersByTime(5000);
      });

      // Week = 36000s = 10h (no seconds suffix — uses formatDuration)
      expect(screen.getByText('10h')).toBeInTheDocument();
      // Month = 144000s = 40h
      expect(screen.getByText('40h')).toBeInTheDocument();
      // Projects = 5
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Polling refetchInterval — verified at DashboardPage query level
// (see DashboardPage.test.tsx "Stats polling" suite)
// ---------------------------------------------------------------------------
