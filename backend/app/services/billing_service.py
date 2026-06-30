"""Pure billing primitives for seat counting and pricing math.

Step 3a/3b scope only:
- Count billable workers for a company from attached ``User`` rows.
- Compute deterministic monthly pricing summary from worker count.

No Stripe API calls, no subscription creation/update side effects.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


FREE_WORKER_LIMIT = 3
PER_SEAT_MONTHLY_PRICE_DOLLARS = 5
UNLIMITED_MONTHLY_PRICE_DOLLARS = 50


@dataclass(frozen=True)
class PricingSummary:
    """Deterministic pricing summary.

    Monetary values are represented in whole dollars per month.
    """

    seats_over_free: int
    per_seat_monthly_cost_dollars: int
    should_recommend_unlimited: bool


async def count_company_billable_workers(db: AsyncSession, company_id: int) -> int:
    """Count billable workers attached to a company.

    Billing definition for step 3a:
    - Count every ``User`` where ``User.company_id == company_id``.
    - Include inactive users (no ``is_active`` filter).
    - Users with ``company_id IS NULL`` are excluded naturally.
    """

    if company_id <= 0:
        raise ValueError("company_id must be a positive integer")

    result = await db.execute(
        select(func.count(User.id)).where(User.company_id == company_id)
    )
    return int(result.scalar_one())


def calculate_monthly_pricing(worker_count: int) -> PricingSummary:
    """Compute monthly pricing summary from total attached worker count."""

    if worker_count < 0:
        raise ValueError("worker_count cannot be negative")

    seats_over_free = max(0, worker_count - FREE_WORKER_LIMIT)
    per_seat_monthly_cost_dollars = seats_over_free * PER_SEAT_MONTHLY_PRICE_DOLLARS
    should_recommend_unlimited = (
        per_seat_monthly_cost_dollars > UNLIMITED_MONTHLY_PRICE_DOLLARS
    )

    return PricingSummary(
        seats_over_free=seats_over_free,
        per_seat_monthly_cost_dollars=per_seat_monthly_cost_dollars,
        should_recommend_unlimited=should_recommend_unlimited,
    )
