"""Canonical helpers for time-entry duration arithmetic.

This module consolidates duration math that was previously duplicated across
``app/routers/reports.py`` and ``app/ai/services/reporting_service.py``.

The behavior is intentionally unchanged from those two prior implementations —
both were functionally equivalent (same arithmetic, same edge cases) and this
extraction is mechanical.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.utils.timer_elapsed import compute_display_elapsed_seconds


def calculate_entry_duration_for_period(
    entry: Any,
    period_start: datetime,
    period_end: datetime,
    now: datetime,
) -> int:
    """Return the seconds of ``entry`` that overlap ``[period_start, period_end]``.

    Pause-aware:
    - Closed entry fully within the period: returns the stored
      ``duration_seconds`` (already pause-corrected on /stop, /switch).
      This is the hot path — just a column read, no datetime math.
    - Closed entry partially overlapping the period: computes wall-clock
      overlap and subtracts a prorated share of ``pause_seconds`` based on
      the fraction of the entry that falls within the period.
    - Running entry: uses ``compute_display_elapsed_seconds`` for the full
      entry, then prorates by the overlap fraction (treats current
      ``pause_seconds`` as uniformly distributed across the elapsed window,
      consistent with the closed-entry proration above).

    Args:
        entry: A ``TimeEntry`` (or any object exposing ``start_time``,
            ``end_time``, ``duration_seconds``, and ``pause_seconds``).
        period_start: Start of the period (e.g., start of day), tz-aware.
        period_end: End of the period (e.g., end of day), tz-aware.
        now: Current time, used as the end for running timers.

    Returns:
        Seconds of the entry that fall within the period, with pause time
        excluded. Always ``>= 0``.
    """
    entry_start = entry.start_time
    if entry_start.tzinfo is None:
        entry_start = entry_start.replace(tzinfo=timezone.utc)

    is_running = entry.end_time is None
    if is_running:
        entry_end = now
    else:
        entry_end = entry.end_time
        if entry_end.tzinfo is None:
            entry_end = entry_end.replace(tzinfo=timezone.utc)

    overlap_start = max(entry_start, period_start)
    overlap_end = min(entry_end, period_end)

    if overlap_start >= overlap_end:
        return 0

    overlap_seconds = int((overlap_end - overlap_start).total_seconds())

    # Closed entry fully within period: stored duration is already pause-corrected.
    if not is_running and entry_start >= period_start and entry_end <= period_end:
        return int(getattr(entry, "duration_seconds", 0) or 0)

    entry_wall_seconds = int((entry_end - entry_start).total_seconds())

    if is_running:
        live_elapsed = compute_display_elapsed_seconds(entry, now=now)
        if entry_wall_seconds <= 0:
            return 0
        if entry_start >= period_start and entry_end <= period_end:
            return live_elapsed
        return max(0, int(live_elapsed * overlap_seconds / entry_wall_seconds))

    # Closed entry, partial overlap: prorate pause_seconds by overlap fraction.
    pause_seconds = int(getattr(entry, "pause_seconds", 0) or 0)
    if entry_wall_seconds > 0 and pause_seconds > 0:
        prorated_pause = int(pause_seconds * overlap_seconds / entry_wall_seconds)
        return max(0, overlap_seconds - prorated_pause)

    return overlap_seconds
