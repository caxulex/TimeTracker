"""Timezone-aware datetime helpers (B7 foundation).

Canonical "now" and day/week/month boundary computations for the codebase.
All bounds functions return half-open ``[start, end)`` intervals as tz-aware
UTC datetimes, computed from a local civil date in the supplied IANA timezone.

DST-correctness:
    Computing bounds in the local zone *first* and then converting to UTC
    yields 23h or 25h spans on transition days, matching how end-users perceive
    a "day". Naive ``datetime.combine`` against a UTC column produces wrong
    daily totals for users east/west of UTC, which is the B6/B7 root cause.

Usage:
    from app.utils.timewindow import now_utc, day_bounds

    start, end = day_bounds(date(2026, 3, 8), "America/Los_Angeles")
    rows = await db.execute(
        select(TimeEntry).where(
            TimeEntry.start_time >= start,
            TimeEntry.start_time < end,
        )
    )
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def now_utc() -> datetime:
    """Return the current time as a tz-aware UTC ``datetime``.

    This is the only blessed "now" call across the codebase. Replacing
    ``datetime.utcnow()`` (deprecated in 3.12+, returns naive) and bare
    ``datetime.now()`` (returns local naive).
    """
    return datetime.now(timezone.utc)


def local_today(tz: str) -> date:
    """Return today's civil date as observed in IANA timezone ``tz``."""
    return datetime.now(_zone(tz)).date()


def _zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {tz!r}") from exc


def day_bounds(day: date, tz: str) -> tuple[datetime, datetime]:
    """Return ``(start, end)`` UTC datetimes covering local civil ``day`` in ``tz``.

    ``end`` is the start of the *next* local day, so the interval is half-open.
    On DST transition days the span will be 23h or 25h.
    """
    zone = _zone(tz)
    start_local = datetime(day.year, day.month, day.day, tzinfo=zone)
    next_day = day + timedelta(days=1)
    end_local = datetime(next_day.year, next_day.month, next_day.day, tzinfo=zone)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def week_bounds(
    day: date,
    tz: str,
    week_starts_on: int = 0,
) -> tuple[datetime, datetime]:
    """Return ``(start, end)`` UTC datetimes covering the local week containing ``day``.

    ``week_starts_on`` follows ``date.weekday()`` (Monday=0 .. Sunday=6).
    Default is Monday (ISO week).
    """
    if not 0 <= week_starts_on <= 6:
        raise ValueError("week_starts_on must be in 0..6")
    offset = (day.weekday() - week_starts_on) % 7
    week_start = day - timedelta(days=offset)
    week_end = week_start + timedelta(days=7)
    zone = _zone(tz)
    start_local = datetime(week_start.year, week_start.month, week_start.day, tzinfo=zone)
    end_local = datetime(week_end.year, week_end.month, week_end.day, tzinfo=zone)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def month_bounds(day: date, tz: str) -> tuple[datetime, datetime]:
    """Return ``(start, end)`` UTC datetimes covering the local month containing ``day``."""
    zone = _zone(tz)
    start_local = datetime(day.year, day.month, 1, tzinfo=zone)
    if day.month == 12:
        next_year, next_month = day.year + 1, 1
    else:
        next_year, next_month = day.year, day.month + 1
    end_local = datetime(next_year, next_month, 1, tzinfo=zone)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def range_bounds(start: date, end: date, tz: str) -> tuple[datetime, datetime]:
    """Return UTC bounds for an inclusive local date range ``[start, end]``.

    The returned interval is half-open: ``[local_start_midnight, local_(end+1)_midnight)``.
    Useful for endpoints that accept ``start_date`` / ``end_date`` query params.
    """
    if end < start:
        raise ValueError("end must be >= start")
    s, _ = day_bounds(start, tz)
    _, e = day_bounds(end, tz)
    return s, e
