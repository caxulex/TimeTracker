"""Pay-rate normalization helpers shared across payroll and forecasting."""

from decimal import Decimal
from typing import Optional

HOURS_PER_WORKDAY = Decimal("8")
HOURS_PER_WORKYEAR = Decimal("2080")
MONTHS_PER_YEAR = Decimal("12")
DEFAULT_OVERTIME_MULTIPLIER = Decimal("1.5")


def normalize_rate_to_hourly(base_rate: Decimal, rate_type: Optional[str]) -> Optional[Decimal]:
    """Convert configured base_rate to an hourly equivalent when possible.

    Returns None for rate types that do not map cleanly to hourly compensation.
    """
    normalized_type = (rate_type or "hourly").lower()

    if normalized_type == "hourly":
        return base_rate
    if normalized_type == "daily":
        return base_rate / HOURS_PER_WORKDAY
    if normalized_type == "monthly":
        return (base_rate * MONTHS_PER_YEAR) / HOURS_PER_WORKYEAR
    if normalized_type == "annual":
        return base_rate / HOURS_PER_WORKYEAR
    return None


def get_overtime_multiplier(
    pay_rate_multiplier: Optional[Decimal],
    company_overtime_enabled: bool = False,
    company_overtime_multiplier: Optional[Decimal] = None,
) -> Decimal:
    """Resolve overtime multiplier with company override when enabled."""
    if company_overtime_enabled and company_overtime_multiplier is not None:
        return Decimal(company_overtime_multiplier)
    if pay_rate_multiplier is not None:
        return Decimal(pay_rate_multiplier)
    return DEFAULT_OVERTIME_MULTIPLIER
