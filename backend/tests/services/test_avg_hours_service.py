# backend/tests/services/test_avg_hours_service.py
"""Tests for the centralized avg_hours_service.

These tests are pure-Python (no DB needed) because compute_avg_hours
resolves company working_days via a DB query only when:
  - user.working_days is None, AND
  - user.company_id is not None

All tests below control for that by either:
  - Setting user.working_days directly (no DB call needed), OR
  - Setting user.company_id = None (no DB call needed), OR
  - Using a mock DB session that returns the expected company data.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.avg_hours_service import AvgHoursResult, compute_avg_hours

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(working_days=None, company_id=None):
    """Build a minimal user-like object."""
    return SimpleNamespace(working_days=working_days, company_id=company_id)


def _mock_db(company_working_days=None):
    """Build an AsyncSession mock that returns ``company_working_days``
    when queried for Company.working_days."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = company_working_days
    db = MagicMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


# ---------------------------------------------------------------------------
# Basic Mon-Fri user — full completed week (Mon-Fri, today=Sat after week)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_basic_mon_fri_full_week_completed():
    """Mon-Fri user, full week done, today is Saturday (outside range)."""
    # Mon 2026-06-08 … Fri 2026-06-12
    period_start = date(2026, 6, 8)
    period_end = date(2026, 6, 12)
    today = date(2026, 6, 13)  # Saturday — outside range

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[0, 1, 2, 3, 4]),
        Decimal("40"),
        period_start,
        period_end,
        today=today,
        exclude_today=True,
    )

    assert result.denominator_days == 5
    assert result.denominator_type == "working_days_all"  # today not in range → no exclusion
    assert result.value == Decimal("8.00")
    assert result.numerator_hours == Decimal("40")
    assert result.includes_today is False
    assert result.today_is_partial is False
    assert result.working_days_source == "user"
    assert result.working_days_used == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_basic_mon_fri_full_week_completed_value():
    """Mon-Fri user, 38.5 hours for the week, today outside range."""
    period_start = date(2026, 6, 8)
    period_end = date(2026, 6, 12)
    today = date(2026, 6, 13)

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[0, 1, 2, 3, 4]),
        Decimal("38.5"),
        period_start,
        period_end,
        today=today,
    )

    # 38.5 / 5 = 7.70
    assert result.value == Decimal("7.70")
    assert result.denominator_days == 5


# ---------------------------------------------------------------------------
# Mid-week: today=Wednesday, exclude_today=True (default)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mon_fri_mid_week_today_excluded():
    """Mon-Fri user, period Mon-Fri, today is Wednesday.
    Divisor = working days in full range EXCLUDING today = Mon+Tue+Thu+Fri = 4."""
    period_start = date(2026, 6, 8)   # Monday
    period_end = date(2026, 6, 12)    # Friday
    today = date(2026, 6, 10)         # Wednesday

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[0, 1, 2, 3, 4]),
        Decimal("16"),
        period_start,
        period_end,
        today=today,
        exclude_today=True,
    )

    # All configured working days in range minus today: Mon + Tue + Thu + Fri = 4
    assert result.denominator_days == 4
    assert result.denominator_type == "working_days_completed"
    assert result.value == Decimal("4.00")
    assert result.includes_today is True
    assert result.today_is_partial is False  # excluded → not partial


@pytest.mark.asyncio
async def test_mon_fri_mid_week_today_included():
    """Same as above but exclude_today=False — divisor includes Wednesday."""
    period_start = date(2026, 6, 8)
    period_end = date(2026, 6, 12)
    today = date(2026, 6, 10)

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[0, 1, 2, 3, 4]),
        Decimal("24"),
        period_start,
        period_end,
        today=today,
        exclude_today=False,
    )

    # Mon + Tue + Wed + Thu + Fri = 5 (full week, exclude_today=False)
    assert result.denominator_days == 5
    assert result.denominator_type == "working_days_all"
    assert result.value == Decimal("4.80")
    assert result.today_is_partial is True  # today in range AND not excluded


# ---------------------------------------------------------------------------
# Custom working_days (includes Saturday)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_custom_working_days_includes_saturday():
    """User with Tue-Sat schedule. Period Mon-Sat, today=Sun after period."""
    # Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5
    period_start = date(2026, 6, 8)   # Monday
    period_end = date(2026, 6, 13)    # Saturday
    today = date(2026, 6, 14)         # Sunday — outside period

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[1, 2, 3, 4, 5]),  # Tue-Sat
        Decimal("35"),
        period_start,
        period_end,
        today=today,
    )

    # Tue 9, Wed 10, Thu 11, Fri 12, Sat 13 → 5 working days
    assert result.denominator_days == 5
    assert result.value == Decimal("7.00")
    assert result.working_days_used == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Company working_days inheritance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_company_working_days_inheritance():
    """User has no working_days → falls back to company's [0,1,2,3] (Mon-Thu)."""
    period_start = date(2026, 6, 8)
    period_end = date(2026, 6, 11)    # Mon-Thu
    today = date(2026, 6, 12)         # Friday outside period

    db = _mock_db(company_working_days=[0, 1, 2, 3])
    result = await compute_avg_hours(
        db,
        _user(working_days=None, company_id=42),
        Decimal("32"),
        period_start,
        period_end,
        today=today,
    )

    assert result.denominator_days == 4
    assert result.value == Decimal("8.00")
    assert result.working_days_source == "company"
    assert result.working_days_used == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_default_working_days_when_no_user_or_company():
    """No user.working_days, no company_id → defaults to Mon-Fri."""
    period_start = date(2026, 6, 8)
    period_end = date(2026, 6, 12)
    today = date(2026, 6, 13)

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=None, company_id=None),
        Decimal("40"),
        period_start,
        period_end,
        today=today,
    )

    assert result.denominator_days == 5
    assert result.working_days_source == "default"
    assert result.working_days_used == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# today not in range — no exclusion needed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_today_not_in_range_no_exclusion():
    """Period is entirely in the past; today is after. All working days counted."""
    period_start = date(2026, 6, 1)   # Monday
    period_end = date(2026, 6, 5)     # Friday
    today = date(2026, 6, 12)         # Far future

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[0, 1, 2, 3, 4]),
        Decimal("40"),
        period_start,
        period_end,
        today=today,
        exclude_today=True,
    )

    assert result.denominator_days == 5
    assert result.includes_today is False
    assert result.denominator_type == "working_days_all"


# ---------------------------------------------------------------------------
# Zero hours
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_hours():
    """Zero total hours → value is 0.00."""
    period_start = date(2026, 6, 8)
    period_end = date(2026, 6, 12)
    today = date(2026, 6, 13)

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[0, 1, 2, 3, 4]),
        Decimal("0"),
        period_start,
        period_end,
        today=today,
    )

    assert result.value == Decimal("0.00")
    assert result.denominator_days == 5


# ---------------------------------------------------------------------------
# Denominator would be zero — edge case
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_denominator_zero_without_fallback():
    """Period is a single day that IS today, exclude_today=True → 0 working days.
    Without fallback → returns 0 avg."""
    # Use a Monday as period_start = period_end = today
    today = date(2026, 6, 8)  # Monday

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[0, 1, 2, 3, 4]),
        Decimal("8"),
        today,
        today,
        today=today,
        exclude_today=True,
        fallback_to_days_with_entries=False,
    )

    assert result.denominator_days == 0
    assert result.value == Decimal("0")


@pytest.mark.asyncio
async def test_denominator_zero_with_days_with_entries_fallback():
    """Same edge case but with fallback_to_days_with_entries=True."""
    today = date(2026, 6, 8)

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[0, 1, 2, 3, 4]),
        Decimal("8"),
        today,
        today,
        today=today,
        exclude_today=True,
        fallback_to_days_with_entries=True,
        days_with_entries=1,
    )

    assert result.denominator_days == 1
    assert result.denominator_type == "days_with_entries"
    assert result.value == Decimal("8.00")


# ---------------------------------------------------------------------------
# Metadata correctness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metadata_completeness():
    """All metadata fields are populated with correct types and values."""
    period_start = date(2026, 6, 8)
    period_end = date(2026, 6, 12)
    today = date(2026, 6, 10)  # Wednesday — in range

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[0, 1, 2, 3, 4]),
        Decimal("20"),
        period_start,
        period_end,
        today=today,
        exclude_today=True,
    )

    assert isinstance(result, AvgHoursResult)
    assert isinstance(result.value, Decimal)
    assert isinstance(result.numerator_hours, Decimal)
    assert isinstance(result.denominator_days, int)
    assert isinstance(result.denominator_type, str)
    assert isinstance(result.includes_today, bool)
    assert isinstance(result.today_is_partial, bool)
    assert isinstance(result.working_days_source, str)
    assert isinstance(result.working_days_used, list)
    assert all(isinstance(d, int) for d in result.working_days_used)

    # Mon + Tue + Thu + Fri (Wed = today excluded) = 4
    assert result.denominator_days == 4
    assert result.numerator_hours == Decimal("20")


@pytest.mark.asyncio
async def test_rounding_to_two_decimal_places():
    """Result value is rounded to 2 decimal places."""
    period_start = date(2026, 6, 8)
    period_end = date(2026, 6, 12)
    today = date(2026, 6, 13)

    result = await compute_avg_hours(
        _mock_db(),
        _user(working_days=[0, 1, 2, 3, 4]),
        Decimal("7"),  # 7 / 5 = 1.4, should be 1.40
        period_start,
        period_end,
        today=today,
    )

    # 7 / 5 = 1.40
    assert result.value == Decimal("1.40")
    assert str(result.value) in {"1.40", "1.4"}
