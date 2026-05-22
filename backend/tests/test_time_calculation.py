# ============================================
# TIME TRACKER - TIME CALCULATION UNIT TESTS
# Tests for calculate_entry_duration_for_period()
# ============================================
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock


def calculate_entry_duration_for_period(entry, period_start, period_end, now) -> int:
    """
    Calculate the duration of a time entry that falls within a specific period.
    This handles entries that span multiple days correctly.
    
    Returns seconds of the entry that overlap with the period.
    """
    # Get entry start time with timezone
    entry_start = entry.start_time
    if entry_start.tzinfo is None:
        entry_start = entry_start.replace(tzinfo=timezone.utc)
    
    # Get entry end time (use now for running timers)
    if entry.end_time:
        entry_end = entry.end_time
        if entry_end.tzinfo is None:
            entry_end = entry_end.replace(tzinfo=timezone.utc)
    else:
        entry_end = now  # Running timer
    
    # Calculate overlap
    overlap_start = max(entry_start, period_start)
    overlap_end = min(entry_end, period_end)
    
    if overlap_start >= overlap_end:
        return 0
    
    return int((overlap_end - overlap_start).total_seconds())


class MockTimeEntry:
    """Mock TimeEntry for testing without database."""
    def __init__(self, start_time, end_time=None, duration_seconds=0):
        self.start_time = start_time
        self.end_time = end_time
        self.duration_seconds = duration_seconds


class TestCalculateEntryDurationForPeriod:
    """Tests for period-based time calculation logic."""

    def test_entry_fully_within_period(self):
        """Entry fully within period should count all hours."""
        # Jan 9, 9am-5pm entry, requesting Jan 9
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 9, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 17, 0, tzinfo=timezone.utc)
        )
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 8 * 3600  # 8 hours

    def test_entry_spans_midnight_count_next_day(self):
        """Entry from 10pm to 6am - should count 6 hours for next day."""
        # Jan 8 10pm - Jan 9 6am entry, requesting Jan 9
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 8, 22, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 6, 0, tzinfo=timezone.utc)
        )
        # Request Jan 9 only
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 6 * 3600  # 6 hours (midnight to 6am)

    def test_entry_spans_midnight_count_first_day(self):
        """Entry from 10pm to 6am - should count 2 hours for first day."""
        # Jan 8 10pm - Jan 9 6am entry, requesting Jan 8
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 8, 22, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 6, 0, tzinfo=timezone.utc)
        )
        # Request Jan 8 only
        period_start = datetime(2026, 1, 8, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 2 * 3600  # 2 hours (10pm to midnight)

    def test_running_timer_uses_now(self):
        """Running timer (no end_time) should use 'now' as end."""
        # Timer started Jan 9 at 8am, still running at 2pm
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 9, 8, 0, tzinfo=timezone.utc),
            end_time=None  # Still running!
        )
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 14, 0, tzinfo=timezone.utc)  # 2pm
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 6 * 3600  # 6 hours (8am to 2pm)

    def test_running_timer_spans_midnight(self):
        """Running timer started yesterday, still running today."""
        # Timer started Jan 8 at 10pm, still running Jan 9 at 2pm
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 8, 22, 0, tzinfo=timezone.utc),
            end_time=None  # Still running!
        )
        # Request Jan 9 only
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 14, 0, tzinfo=timezone.utc)  # 2pm
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 14 * 3600  # 14 hours (midnight to 2pm)

    def test_entry_before_period_returns_zero(self):
        """Entry completely before period should return 0."""
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 7, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 7, 17, 0, tzinfo=timezone.utc)
        )
        # Request Jan 9
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 0

    def test_entry_after_period_returns_zero(self):
        """Entry completely after period should return 0."""
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 11, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 11, 17, 0, tzinfo=timezone.utc)
        )
        # Request Jan 9
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 0

    def test_entry_extends_past_period_end(self):
        """Entry extends past period end - only count time within period."""
        # Entry Jan 9 8am - Jan 10 4pm, requesting Jan 9 only
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 9, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 10, 16, 0, tzinfo=timezone.utc)
        )
        # Request Jan 9 only
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 10, 20, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 16 * 3600  # 16 hours (8am to midnight)

    def test_multi_day_entry_middle_day(self):
        """Multi-day entry - middle day should get full 24 hours."""
        # Entry Jan 8 8am - Jan 11 4pm, requesting Jan 9 only
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 8, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 11, 16, 0, tzinfo=timezone.utc)
        )
        # Request Jan 9 only (full day in the middle)
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 11, 20, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 24 * 3600  # Full 24 hours

    def test_entry_starts_at_exact_period_boundary(self):
        """Entry starting exactly at period start."""
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 8, 0, tzinfo=timezone.utc)
        )
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 8 * 3600  # 8 hours

    def test_entry_ends_at_exact_period_boundary(self):
        """Entry ending exactly at period end."""
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 9, 16, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 10, 1, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 8 * 3600  # 8 hours (4pm to midnight)

    def test_very_short_entry(self):
        """Very short entry (1 minute)."""
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 9, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 12, 1, 0, tzinfo=timezone.utc)
        )
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        assert result == 60  # 1 minute = 60 seconds


class TestTotalHoursCalculation:
    """Test that all hours are properly accounted for across days."""

    def test_total_hours_preserved_across_days(self):
        """An 8-hour overnight entry should sum to 8 hours total."""
        # 10pm to 6am = 8 hours total
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 8, 22, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 6, 0, tzinfo=timezone.utc)
        )
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)
        
        # Calculate for Jan 8 (2 hours: 10pm-midnight)
        day1_start = datetime(2026, 1, 8, 0, 0, tzinfo=timezone.utc)
        day1_end = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        day1_seconds = calculate_entry_duration_for_period(entry, day1_start, day1_end, now)
        
        # Calculate for Jan 9 (6 hours: midnight-6am)
        day2_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        day2_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        day2_seconds = calculate_entry_duration_for_period(entry, day2_start, day2_end, now)
        
        # Sum should equal original 8 hours
        total_seconds = day1_seconds + day2_seconds
        assert total_seconds == 8 * 3600
        assert day1_seconds == 2 * 3600  # 2 hours on day 1
        assert day2_seconds == 6 * 3600  # 6 hours on day 2

    def test_week_period_captures_all_entries(self):
        """A week period should capture all entries that overlap."""
        # Entry from Jan 6 to Jan 10 (4 days)
        entry = MockTimeEntry(
            start_time=datetime(2026, 1, 6, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 10, 17, 0, tzinfo=timezone.utc)
        )
        now = datetime(2026, 1, 10, 20, 0, tzinfo=timezone.utc)
        
        # Request Jan 6-12 (full week)
        period_start = datetime(2026, 1, 6, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 13, 0, 0, tzinfo=timezone.utc)
        
        result = calculate_entry_duration_for_period(entry, period_start, period_end, now)
        
        # Should be: Jan 6 8am to Jan 10 5pm = 4 days 9 hours
        expected = (4 * 24 + 9) * 3600  # 105 hours
        assert result == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============================================
# PAUSE-AWARE REPORT OVERLAP TESTS
# Targets the REAL helper at app.routers.reports
# (PR: fix/reports-overlap-honors-pause-seconds)
# ============================================

from app.routers.reports import (
    calculate_entry_duration as real_calculate_entry_duration,
    calculate_entry_duration_for_period as real_calculate_entry_duration_for_period,
)


class MockPauseAwareEntry:
    """Mock TimeEntry exposing all attrs the pause-aware helper needs."""

    def __init__(
        self,
        start_time,
        end_time=None,
        duration_seconds=0,
        pause_seconds=0,
        is_paused=False,
        paused_at=None,
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.duration_seconds = duration_seconds
        self.pause_seconds = pause_seconds
        self.is_paused = is_paused
        self.paused_at = paused_at


class TestPauseAwareOverlap:
    """Verify report overlap helper subtracts pause time (PR #26/#27/#31 lineage)."""

    def test_fully_within_period_with_pause_returns_duration_seconds(self):
        """Laura's case: 7h wall-clock entry minus 1h48m lunch -> uses stored duration."""
        # 09:00-16:00 entry (7h wall-clock) on 2026-05-20, 1h48m (6480s) pause
        # stored duration_seconds = 7h - 1h48m = 5h12m = 18720s
        entry = MockPauseAwareEntry(
            start_time=datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 20, 16, 0, tzinfo=timezone.utc),
            duration_seconds=18720,
            pause_seconds=6480,
        )
        period_start = datetime(2026, 5, 20, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 5, 21, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 5, 21, 0, 0, tzinfo=timezone.utc)

        result = real_calculate_entry_duration_for_period(entry, period_start, period_end, now)

        assert result == 18720  # NOT 25200 (7h wall-clock)

    def test_fully_within_period_no_pause_returns_duration_seconds(self):
        """Entry with no pause: still uses stored duration_seconds (== wall-clock)."""
        entry = MockPauseAwareEntry(
            start_time=datetime(2026, 1, 9, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 17, 0, tzinfo=timezone.utc),
            duration_seconds=8 * 3600,
            pause_seconds=0,
        )
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)

        result = real_calculate_entry_duration_for_period(entry, period_start, period_end, now)

        assert result == 8 * 3600

    def test_partial_overlap_prorates_pause(self):
        """8h entry with 2h pause; period captures 2h of it -> 2h - 0.5h = 1.5h."""
        # Entry: 22:00 -> 06:00 next day = 8h wall-clock, 2h pause -> stored 6h
        # Period: previous day only -> overlap = 2h (22:00 - midnight)
        # prorated pause = 2h * (2/8) = 0.5h
        # expected: 2h - 0.5h = 1.5h = 5400s
        entry = MockPauseAwareEntry(
            start_time=datetime(2026, 1, 8, 22, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 6, 0, tzinfo=timezone.utc),
            duration_seconds=6 * 3600,
            pause_seconds=2 * 3600,
        )
        period_start = datetime(2026, 1, 8, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 12, 0, tzinfo=timezone.utc)

        result = real_calculate_entry_duration_for_period(entry, period_start, period_end, now)

        assert result == int(1.5 * 3600)  # 5400s

    def test_partial_overlap_no_pause_returns_wall_clock_overlap(self):
        """Without pause, partial overlap behaves as before (wall-clock overlap)."""
        entry = MockPauseAwareEntry(
            start_time=datetime(2026, 1, 8, 22, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 6, 0, tzinfo=timezone.utc),
            duration_seconds=8 * 3600,
            pause_seconds=0,
        )
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 12, 0, tzinfo=timezone.utc)

        result = real_calculate_entry_duration_for_period(entry, period_start, period_end, now)

        assert result == 6 * 3600

    def test_per_day_decomposition_sums_to_duration_seconds(self):
        """Critical invariant: per-day breakdown of multi-day entry == duration_seconds."""
        # 8h wall-clock, 2h pause -> duration = 6h (21600s)
        entry = MockPauseAwareEntry(
            start_time=datetime(2026, 1, 8, 22, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 6, 0, tzinfo=timezone.utc),
            duration_seconds=6 * 3600,
            pause_seconds=2 * 3600,
        )
        now = datetime(2026, 1, 9, 12, 0, tzinfo=timezone.utc)

        day1_start = datetime(2026, 1, 8, 0, 0, tzinfo=timezone.utc)
        day1_end = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        day2_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        day2_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)

        d1 = real_calculate_entry_duration_for_period(entry, day1_start, day1_end, now)
        d2 = real_calculate_entry_duration_for_period(entry, day2_start, day2_end, now)

        # Allow off-by-one due to integer truncation in proration
        total = d1 + d2
        assert abs(total - 6 * 3600) <= 1

    def test_running_timer_uses_pause_aware_helper(self):
        """Running entry currently on break: live elapsed freezes at pause moment."""
        # Started 08:00, paused at 10:00 with 0 prior pause -> elapsed frozen at 2h.
        # Without 'now' affecting it because is_paused is True.
        entry = MockPauseAwareEntry(
            start_time=datetime(2026, 1, 9, 8, 0, tzinfo=timezone.utc),
            end_time=None,
            duration_seconds=0,
            pause_seconds=0,
            is_paused=True,
            paused_at=datetime(2026, 1, 9, 10, 0, tzinfo=timezone.utc),
        )
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        # 'now' is 14:00, but elapsed must freeze at 10:00 -> 2h.
        now = datetime(2026, 1, 9, 14, 0, tzinfo=timezone.utc)

        result = real_calculate_entry_duration_for_period(entry, period_start, period_end, now)

        # Entry fully within today -> returns live_elapsed directly = 2h
        assert result == 2 * 3600

    def test_running_timer_active_subtracts_accumulated_pause(self):
        """Running entry not on break: elapsed = (now - start) - accumulated pause."""
        entry = MockPauseAwareEntry(
            start_time=datetime(2026, 1, 9, 8, 0, tzinfo=timezone.utc),
            end_time=None,
            duration_seconds=0,
            pause_seconds=30 * 60,  # took a 30-min break earlier
            is_paused=False,
            paused_at=None,
        )
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 14, 0, tzinfo=timezone.utc)  # 6h since start

        result = real_calculate_entry_duration_for_period(entry, period_start, period_end, now)

        assert result == 6 * 3600 - 30 * 60  # 5h30m

    def test_duration_seconds_none_returns_zero_no_exception(self):
        """Defensive: data-integrity edge case where duration_seconds is None."""
        entry = MockPauseAwareEntry(
            start_time=datetime(2026, 1, 9, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 17, 0, tzinfo=timezone.utc),
            duration_seconds=None,
            pause_seconds=0,
        )
        period_start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)

        result = real_calculate_entry_duration_for_period(entry, period_start, period_end, now)

        assert result == 0

    def test_calculate_entry_duration_running_uses_pause_aware_helper(self):
        """The single-entry (non-period) helper must also honor pause for running timers."""
        entry = MockPauseAwareEntry(
            start_time=datetime(2026, 1, 9, 8, 0, tzinfo=timezone.utc),
            end_time=None,
            duration_seconds=0,
            pause_seconds=30 * 60,
        )
        now = datetime(2026, 1, 9, 14, 0, tzinfo=timezone.utc)

        result = real_calculate_entry_duration(entry, now)

        assert result == 6 * 3600 - 30 * 60

    def test_calculate_entry_duration_closed_returns_duration_seconds(self):
        """Closed entries: just use stored duration (already pause-corrected at /stop)."""
        entry = MockPauseAwareEntry(
            start_time=datetime(2026, 1, 9, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 9, 17, 0, tzinfo=timezone.utc),
            duration_seconds=18720,  # pause-corrected
            pause_seconds=6480,
        )
        now = datetime(2026, 1, 9, 20, 0, tzinfo=timezone.utc)

        result = real_calculate_entry_duration(entry, now)

        assert result == 18720