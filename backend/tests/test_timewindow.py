"""Tests for app.utils.timewindow (B7 helper)."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.utils.timewindow import day_bounds, month_bounds, now_utc, range_bounds, week_bounds


# ---------- now_utc ----------

def test_now_utc_is_tz_aware_utc():
    n = now_utc()
    assert n.tzinfo is not None
    assert n.utcoffset().total_seconds() == 0


# ---------- day_bounds basic ----------

def test_day_bounds_la_normal_day():
    """A normal LA day (PST, UTC-8): 00:00 PST = 08:00 UTC, span = 24h."""
    start, end = day_bounds(date(2026, 1, 15), "America/Los_Angeles")
    assert start == datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 16, 8, 0, tzinfo=timezone.utc)
    assert (end - start).total_seconds() == 24 * 3600


def test_day_bounds_utc_zone():
    """UTC zone: midnight aligns with UTC midnight."""
    start, end = day_bounds(date(2026, 6, 1), "UTC")
    assert start == datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)


def test_day_bounds_invalid_tz_raises():
    with pytest.raises(ValueError, match="Unknown IANA timezone"):
        day_bounds(date(2026, 1, 1), "Not/AZone")


# ---------- DST: spring-forward (23h day) ----------

def test_day_bounds_la_spring_forward_2026():
    """2026-03-08 is the LA spring-forward day. Local span is 23h."""
    start, end = day_bounds(date(2026, 3, 8), "America/Los_Angeles")
    span_hours = (end - start).total_seconds() / 3600
    assert span_hours == 23.0
    # 00:00 PST = UTC-8 = 08:00 UTC; 00:00 next day PDT = UTC-7 = 07:00 UTC
    assert start == datetime(2026, 3, 8, 8, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 3, 9, 7, 0, tzinfo=timezone.utc)


def test_day_bounds_london_spring_forward_2026():
    """2026-03-29 is the London BST start day. Local span is 23h."""
    start, end = day_bounds(date(2026, 3, 29), "Europe/London")
    span_hours = (end - start).total_seconds() / 3600
    assert span_hours == 23.0


# ---------- DST: fall-back (25h day) ----------

def test_day_bounds_la_fall_back_2026():
    """2026-11-01 is the LA fall-back day. Local span is 25h."""
    start, end = day_bounds(date(2026, 11, 1), "America/Los_Angeles")
    span_hours = (end - start).total_seconds() / 3600
    assert span_hours == 25.0
    # 00:00 PDT = UTC-7 = 07:00 UTC; 00:00 next day PST = UTC-8 = 08:00 UTC
    assert start == datetime(2026, 11, 1, 7, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)


def test_day_bounds_london_fall_back_2026():
    """2026-10-25 is the London GMT return day. Local span is 25h."""
    start, end = day_bounds(date(2026, 10, 25), "Europe/London")
    span_hours = (end - start).total_seconds() / 3600
    assert span_hours == 25.0


# ---------- week_bounds ----------

def test_week_bounds_monday_start_la():
    """ISO week containing 2026-01-15 (Thursday) starts Mon 2026-01-12."""
    start, end = week_bounds(date(2026, 1, 15), "America/Los_Angeles")
    # Mon 00:00 PST = 08:00 UTC; next Mon 00:00 PST = 08:00 UTC seven days later
    assert start == datetime(2026, 1, 12, 8, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 19, 8, 0, tzinfo=timezone.utc)


def test_week_bounds_sunday_start():
    """week_starts_on=6 → Sunday-start. 2026-01-15 (Thu) → Sun 2026-01-11."""
    start, _end = week_bounds(date(2026, 1, 15), "UTC", week_starts_on=6)
    assert start.date() == date(2026, 1, 11)


def test_week_bounds_spans_dst_transition():
    """A week containing the LA spring-forward day spans 7*24 - 1 = 167h."""
    # 2026-03-08 (spring forward, Sun) is in the ISO week 2026-03-02 .. 2026-03-08 (Mon-start)
    # So the week ending starts Mon 2026-03-09 at 07:00 UTC, started Mon 2026-03-02 at 08:00 UTC
    start, end = week_bounds(date(2026, 3, 8), "America/Los_Angeles")
    span_hours = (end - start).total_seconds() / 3600
    assert span_hours == 167.0


def test_week_bounds_invalid_starts_on():
    with pytest.raises(ValueError):
        week_bounds(date(2026, 1, 15), "UTC", week_starts_on=7)


# ---------- month_bounds ----------

def test_month_bounds_january_la():
    start, end = month_bounds(date(2026, 1, 15), "America/Los_Angeles")
    assert start == datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc)


def test_month_bounds_december_rolls_year():
    start, end = month_bounds(date(2026, 12, 31), "UTC")
    assert start == datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc)


def test_month_bounds_march_la_includes_spring_forward():
    """March 2026 in LA contains spring-forward → 31*24 - 1 = 743h."""
    start, end = month_bounds(date(2026, 3, 15), "America/Los_Angeles")
    span_hours = (end - start).total_seconds() / 3600
    assert span_hours == 743.0


# ---------- Cross-endpoint semantics ----------

def test_intervals_are_half_open():
    """day_bounds end equals next-day start (no overlap, no gap)."""
    _start_a, end_a = day_bounds(date(2026, 6, 1), "America/Los_Angeles")
    start_b, _end_b = day_bounds(date(2026, 6, 2), "America/Los_Angeles")
    assert end_a == start_b


# ---------- range_bounds ----------

def test_range_bounds_inclusive_local_range():
    start, end = range_bounds(date(2026, 6, 1), date(2026, 6, 7), "America/Los_Angeles")
    # 7 full local days, normal time, all PDT (UTC-7) → 7*24h
    span_hours = (end - start).total_seconds() / 3600
    assert span_hours == 7 * 24
    assert start == datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 6, 8, 7, 0, tzinfo=timezone.utc)


def test_range_bounds_single_day():
    """A single-day range matches day_bounds exactly."""
    rs, re = range_bounds(date(2026, 3, 8), date(2026, 3, 8), "America/Los_Angeles")
    ds, de = day_bounds(date(2026, 3, 8), "America/Los_Angeles")
    assert (rs, re) == (ds, de)


def test_range_bounds_rejects_inverted():
    with pytest.raises(ValueError):
        range_bounds(date(2026, 6, 7), date(2026, 6, 1), "UTC")


def test_range_bounds_spans_dst_correctly():
    """A range straddling LA spring-forward loses 1h locally → 7*24 - 1 = 167h."""
    start, end = range_bounds(date(2026, 3, 7), date(2026, 3, 13), "America/Los_Angeles")
    span_hours = (end - start).total_seconds() / 3600
    assert span_hours == 167.0
