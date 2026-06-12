"""Working-day resolution and calendar helpers.

Weekday convention follows Python ``date.weekday()``:
- Monday=0
- Sunday=6
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

DEFAULT_WORKING_DAYS: list[int] = [0, 1, 2, 3, 4]


def normalize_working_days(
    working_days: Sequence[int] | None,
    *,
    allow_none: bool,
) -> list[int] | None:
    """Validate and normalize a working-days list.

    Rules:
    - ``None`` is allowed only when ``allow_none=True``.
    - List must be non-empty.
    - Values must be integers in ``[0, 6]``.
    - Duplicates are rejected.
    - Stored output is sorted ascending.
    """
    if working_days is None:
        if allow_none:
            return None
        raise ValueError("working_days cannot be null")

    values = list(working_days)
    if len(values) == 0:
        raise ValueError("working_days must contain at least one weekday")

    for value in values:
        if not isinstance(value, int):
            raise ValueError("working_days values must be integers")
        if value < 0 or value > 6:
            raise ValueError("working_days values must be in range 0..6")

    if len(set(values)) != len(values):
        raise ValueError("working_days cannot contain duplicates")

    return sorted(values)


def get_user_working_days(user: object) -> list[int]:
    """Resolve effective working days for a user.

    Resolution order:
    1. user.working_days (if set)
    2. user.company.working_days (if set)
    3. default Mon-Fri
    """
    user_days = getattr(user, "working_days", None)
    if user_days is not None:
        normalized = normalize_working_days(user_days, allow_none=False)
        # ``allow_none=False`` guarantees a concrete list.
        return normalized  # type: ignore[return-value]

    company = getattr(user, "company", None)
    company_days = getattr(company, "working_days", None) if company is not None else None
    if company_days is not None:
        normalized = normalize_working_days(company_days, allow_none=False)
        return normalized  # type: ignore[return-value]

    return DEFAULT_WORKING_DAYS.copy()


def is_working_day(user: object, date_value: date) -> bool:
    """Return whether ``date_value`` is a configured working day for ``user``."""
    return date_value.weekday() in get_user_working_days(user)


def count_working_days_in_range(
    user: object,
    start: date,
    end: date,
    *,
    exclude_today: bool = False,
    today: date | None = None,
) -> int:
    """Count working days in an inclusive date range.

    Args:
    - ``start``: range start (inclusive)
    - ``end``: range end (inclusive)
    - ``exclude_today``: when true, excludes ``today`` if it falls in range
    - ``today``: caller-provided tenant-local today; defaults to ``date.today()``
    """
    if end < start:
        raise ValueError("end must be on or after start")

    today_value = today or date.today()
    working_day_set = set(get_user_working_days(user))

    total = 0
    current = start
    while current <= end:
        if current.weekday() in working_day_set:
            if not (exclude_today and current == today_value):
                total += 1
        current = current.fromordinal(current.toordinal() + 1)

    return total
