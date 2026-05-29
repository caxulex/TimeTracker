"""Direct unit tests for ``app.services.duration_service``.

Covers the cases called out in the consolidation PR: happy path, zero pause,
non-zero pause, exact boundary (end == start), and end-before-start (verify
existing behavior — return 0 — without introducing new behavior).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.duration_service import calculate_entry_duration_for_period


class _Entry:
    """Minimal stand-in for ``TimeEntry`` exposing only the attributes the
    helper reads."""

    def __init__(
        self,
        start_time: datetime,
        end_time: datetime | None,
        duration_seconds: int = 0,
        pause_seconds: int = 0,
        is_paused: bool = False,
        paused_at: datetime | None = None,
    ) -> None:
        self.start_time = start_time
        self.end_time = end_time
        self.duration_seconds = duration_seconds
        self.pause_seconds = pause_seconds
        self.is_paused = is_paused
        self.paused_at = paused_at


UTC = timezone.utc
PERIOD_START = datetime(2026, 1, 9, 0, 0, tzinfo=UTC)
PERIOD_END = datetime(2026, 1, 10, 0, 0, tzinfo=UTC)
NOW = datetime(2026, 1, 9, 20, 0, tzinfo=UTC)


class TestCalculateEntryDurationForPeriod:
    def test_happy_path_closed_within_period(self):
        """Closed entry fully inside period returns stored duration_seconds (hot path)."""
        entry = _Entry(
            start_time=datetime(2026, 1, 9, 9, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 9, 17, 0, tzinfo=UTC),
            duration_seconds=8 * 3600,
            pause_seconds=0,
        )
        assert calculate_entry_duration_for_period(entry, PERIOD_START, PERIOD_END, NOW) == 8 * 3600

    def test_zero_pause_partial_overlap(self):
        """Partial overlap with no pause: returns the wall-clock overlap."""
        entry = _Entry(
            start_time=datetime(2026, 1, 8, 22, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 9, 6, 0, tzinfo=UTC),
            duration_seconds=8 * 3600,
            pause_seconds=0,
        )
        assert calculate_entry_duration_for_period(entry, PERIOD_START, PERIOD_END, NOW) == 6 * 3600

    def test_non_zero_pause_partial_overlap_prorates(self):
        """Partial overlap with pause: pause is prorated by overlap fraction.

        Entry: 8h wall, 1h pause (3600s). Overlap with Jan 9 = 6h (6/8 = 0.75).
        Prorated pause = int(3600 * 6*3600 / 8*3600) = 2700.
        Expected: 6*3600 - 2700 = 18900.
        """
        entry = _Entry(
            start_time=datetime(2026, 1, 8, 22, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 9, 6, 0, tzinfo=UTC),
            duration_seconds=7 * 3600,  # not used on partial-overlap branch
            pause_seconds=3600,
        )
        assert calculate_entry_duration_for_period(entry, PERIOD_START, PERIOD_END, NOW) == 18900

    def test_non_zero_pause_fully_within_returns_stored_duration(self):
        """When fully inside the period, the stored (pause-corrected)
        duration is returned verbatim — pause math is not re-applied."""
        entry = _Entry(
            start_time=datetime(2026, 1, 9, 9, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 9, 17, 0, tzinfo=UTC),
            duration_seconds=7 * 3600,  # already pause-corrected
            pause_seconds=3600,
        )
        assert calculate_entry_duration_for_period(entry, PERIOD_START, PERIOD_END, NOW) == 7 * 3600

    def test_exact_boundary_end_equals_start(self):
        """end == start collapses overlap to empty -> 0."""
        ts = datetime(2026, 1, 9, 12, 0, tzinfo=UTC)
        entry = _Entry(start_time=ts, end_time=ts, duration_seconds=0)
        assert calculate_entry_duration_for_period(entry, PERIOD_START, PERIOD_END, NOW) == 0

    def test_end_before_start_returns_zero(self):
        """Existing behavior: end_time before start_time produces no overlap -> 0.
        This documents existing behavior; no new clamping/error path is added."""
        entry = _Entry(
            start_time=datetime(2026, 1, 9, 17, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 9, 9, 0, tzinfo=UTC),
            duration_seconds=0,
        )
        assert calculate_entry_duration_for_period(entry, PERIOD_START, PERIOD_END, NOW) == 0

    def test_naive_datetimes_treated_as_utc(self):
        """Naive ``start_time``/``end_time`` are treated as UTC (existing behavior)."""
        entry = _Entry(
            start_time=datetime(2026, 1, 9, 9, 0),  # naive
            end_time=datetime(2026, 1, 9, 11, 0),   # naive
            duration_seconds=2 * 3600,
        )
        assert calculate_entry_duration_for_period(entry, PERIOD_START, PERIOD_END, NOW) == 2 * 3600

    def test_no_overlap_returns_zero(self):
        entry = _Entry(
            start_time=datetime(2026, 1, 7, 9, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 7, 17, 0, tzinfo=UTC),
            duration_seconds=8 * 3600,
        )
        assert calculate_entry_duration_for_period(entry, PERIOD_START, PERIOD_END, NOW) == 0

    def test_running_entry_within_period(self):
        """Running entry fully inside period uses live elapsed (now - start - pause)."""
        entry = _Entry(
            start_time=datetime(2026, 1, 9, 18, 0, tzinfo=UTC),
            end_time=None,
            pause_seconds=0,
        )
        # NOW = 20:00 → 2h elapsed.
        assert calculate_entry_duration_for_period(entry, PERIOD_START, PERIOD_END, NOW) == 2 * 3600

    def test_running_entry_with_pause(self):
        """Running entry, pause_seconds subtracted from live elapsed."""
        entry = _Entry(
            start_time=datetime(2026, 1, 9, 18, 0, tzinfo=UTC),
            end_time=None,
            pause_seconds=600,
        )
        assert calculate_entry_duration_for_period(entry, PERIOD_START, PERIOD_END, NOW) == 2 * 3600 - 600
