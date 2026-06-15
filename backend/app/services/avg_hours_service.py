"""Centralized Avg Hours/Day computation service.

Provides a single, transparent implementation of "average hours per day"
with rich metadata so callers can render honest copy to users.

Built on the Phase 4a working-day helpers in app.utils.working_days.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.working_days import DEFAULT_WORKING_DAYS, count_working_days_in_range


@dataclass
class AvgHoursResult:
    """Rich result from compute_avg_hours."""

    value: Decimal                    # avg hours/day
    numerator_hours: Decimal          # total hours used in numerator
    denominator_days: int             # divisor used
    denominator_type: Literal[
        "working_days_completed",     # working days excluding today
        "working_days_all",           # working days including today
        "days_with_entries",          # only days with hours logged
        "calendar_days",              # all calendar days (legacy)
    ]
    includes_today: bool              # whether today is in the period
    today_is_partial: bool            # today is in range AND not excluded
    working_days_source: Literal["user", "company", "default"]
    working_days_used: list[int] = field(default_factory=list)


async def _resolve_working_days(
    db: AsyncSession,
    user: object,
) -> tuple[list[int], Literal["user", "company", "default"]]:
    """Resolve effective working days for a user without ORM relationship traversal.

    Resolution order:
    1. user.working_days (direct column — always safe in async context)
    2. company.working_days via db query using user.company_id
    3. DEFAULT Mon-Fri

    Returns (working_days_list, source_label).
    """
    user_days = getattr(user, "working_days", None)
    if user_days is not None and len(user_days) > 0:
        return sorted(user_days), "user"

    company_id = getattr(user, "company_id", None)
    if company_id is not None:
        from app.models import Company

        result = await db.execute(
            select(Company.working_days).where(Company.id == company_id)
        )
        company_days = result.scalar_one_or_none()
        if company_days is not None and len(company_days) > 0:
            return sorted(company_days), "company"

    return DEFAULT_WORKING_DAYS.copy(), "default"


async def compute_avg_hours(
    db: AsyncSession,
    user: object,
    total_hours: Decimal,
    period_start: date,
    period_end: date,
    *,
    today: date | None = None,
    exclude_today: bool = True,
    today_hours: Decimal | None = None,
    fallback_to_days_with_entries: bool = False,
    days_with_entries: int | None = None,
) -> AvgHoursResult:
    """Compute Avg Hours/Day with full transparency metadata.

    Default behavior:
    - Divisor = working days in [period_start, period_end] excluding today
    - Working days = user.working_days → company.working_days → Mon-Fri
    - today = caller-resolved tenant-local today (falls back to date.today())

    Args:
        db: Async SQLAlchemy session (used for company working_days fallback).
        user: User model instance (must have working_days and company_id attrs).
        total_hours: Total hours in the numerator (covering the full period
            including today's partial hours if today is in the period).
        period_start: Start of the period (inclusive).
        period_end: End of the period (inclusive).
        today: Tenant-local today. Defaults to date.today().
        exclude_today: When True, exclude today from the denominator if it
            falls in the period. This is the primary behavior for
            "in-progress" periods to avoid artificially low averages.
        today_hours: Hours logged today (within the period). When
            exclude_today=True and today is in the period, this value is
            subtracted from total_hours so that numerator and denominator
            are aligned (both exclude today). Callers MUST pass this when
            exclude_today=True and today falls in the period; omitting it
            leaves the numerator/denominator misaligned and produces an
            inflated average.
        fallback_to_days_with_entries: When True and denominator would be 0,
            use days_with_entries instead.
        days_with_entries: Number of distinct dates with logged hours.
            Required when fallback_to_days_with_entries=True.

    Returns:
        AvgHoursResult with value and rich metadata.
    """
    today_resolved = today or date.today()

    # Resolve working days without ORM relationship traversal
    working_days_used, working_days_source = await _resolve_working_days(db, user)

    # Build a mock user that get_user_working_days / count_working_days_in_range
    # can safely use (the mock has working_days set as a plain list, no ORM lazy load)
    from types import SimpleNamespace

    mock_user = SimpleNamespace(working_days=working_days_used, company=None)

    today_in_range = period_start <= today_resolved <= period_end
    includes_today = today_in_range

    # Align the numerator: when today is excluded from the denominator,
    # strip today's hours from the numerator so both sides exclude today.
    if exclude_today and today_in_range and today_hours is not None:
        aligned_numerator = total_hours - today_hours
        # Guard against negative values from clock skew or rounding
        if aligned_numerator < Decimal("0"):
            aligned_numerator = Decimal("0")
    else:
        aligned_numerator = total_hours

    # Choose denominator type
    if exclude_today and today_in_range:
        denominator_days = count_working_days_in_range(
            mock_user,
            period_start,
            period_end,
            exclude_today=True,
            today=today_resolved,
        )
        denominator_type: Literal[
            "working_days_completed",
            "working_days_all",
            "days_with_entries",
            "calendar_days",
        ] = "working_days_completed"
        today_is_partial = False
    else:
        denominator_days = count_working_days_in_range(
            mock_user,
            period_start,
            period_end,
            exclude_today=False,
            today=today_resolved,
        )
        denominator_type = "working_days_all"
        today_is_partial = today_in_range  # today is included in the count

    # Edge case: denominator is 0 (e.g. period falls entirely on non-working days,
    # or period_end < period_start after exclusion)
    if denominator_days == 0:
        if fallback_to_days_with_entries and days_with_entries is not None and days_with_entries > 0:
            denominator_days = days_with_entries
            denominator_type = "days_with_entries"
        else:
            # Return 0 avg rather than divide-by-zero
            return AvgHoursResult(
                value=Decimal("0"),
                numerator_hours=aligned_numerator,
                denominator_days=0,
                denominator_type=denominator_type,
                includes_today=includes_today,
                today_is_partial=today_is_partial,
                working_days_source=working_days_source,
                working_days_used=working_days_used,
            )

    value = (aligned_numerator / Decimal(denominator_days)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return AvgHoursResult(
        value=value,
        numerator_hours=aligned_numerator,
        denominator_days=denominator_days,
        denominator_type=denominator_type,
        includes_today=includes_today,
        today_is_partial=today_is_partial,
        working_days_source=working_days_source,
        working_days_used=working_days_used,
    )
