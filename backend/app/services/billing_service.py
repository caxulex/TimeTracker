"""Billing primitives and Stripe subscription creation for seat-based billing.

Current scope:
- Count billable workers for a company from attached ``User`` rows.
- Compute deterministic monthly pricing summary from worker count.
- Create a per-seat Stripe subscription for the standard tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Company, User


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


class CreateSubscriptionStatus(str, Enum):
    CREATED = "created"
    NOOP_ZERO_SEATS = "noop_zero_seats"
    NOOP_ALREADY_SUBSCRIBED = "noop_already_subscribed"
    REQUIRES_PAYMENT_ACTION = "requires_payment_action"
    RETRIABLE_ERROR = "retriable_error"
    CONFIG_ERROR = "config_error"


@dataclass(frozen=True)
class CreateSubscriptionResult:
    status: CreateSubscriptionStatus
    company_id: int
    seats_over_free: int
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    stripe_subscription_status: str | None = None
    message: str | None = None


async def _get_company_for_update(db: AsyncSession, company_id: int) -> Company | None:
    result = await db.execute(
        select(Company).where(Company.id == company_id).with_for_update()
    )
    return result.scalar_one_or_none()


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


async def create_standard_subscription(
    db: AsyncSession,
    company_id: int,
) -> CreateSubscriptionResult:
    """Create a Stripe per-seat monthly subscription for a company.

    Concurrency/idempotency model:
    - Transaction A: lock company row, pre-check state, compute seats, release lock.
    - Stripe calls: create/reuse customer and create subscription with deterministic
      idempotency keys.
    - Transaction B: re-lock company row, re-check subscription guard, persist IDs.
    """

    if company_id <= 0:
        raise ValueError("company_id must be a positive integer")

    stripe_secret_key = settings.STRIPE_SECRET_KEY.strip()
    stripe_price_per_seat_monthly_id = (
        getattr(settings, "STRIPE_PRICE_PER_SEAT_MONTHLY_ID", "").strip()
    )
    if not stripe_secret_key or not stripe_price_per_seat_monthly_id:
        return CreateSubscriptionResult(
            status=CreateSubscriptionStatus.CONFIG_ERROR,
            company_id=company_id,
            seats_over_free=0,
            message=(
                "Stripe configuration missing: STRIPE_SECRET_KEY and "
                "STRIPE_PRICE_PER_SEAT_MONTHLY_ID are required"
            ),
        )

    customer_create_key = f"customer-create-company-{company_id}"
    subscription_create_key = f"subscription-create-company-{company_id}"

    existing_customer_id: str | None = None
    company_name: str = ""
    company_email: str = ""
    seats_over_free = 0

    # Transaction A: lock + pre-check + seat derivation
    try:
        company = await _get_company_for_update(db, company_id)
        if company is None:
            raise ValueError(f"Company {company_id} not found")

        if company.stripe_subscription_id:
            result = CreateSubscriptionResult(
                status=CreateSubscriptionStatus.NOOP_ALREADY_SUBSCRIBED,
                company_id=company_id,
                seats_over_free=0,
                stripe_customer_id=company.stripe_customer_id,
                stripe_subscription_id=company.stripe_subscription_id,
            )
            await db.commit()
            return result

        worker_count = await count_company_billable_workers(db, company_id)
        pricing = calculate_monthly_pricing(worker_count)
        if pricing.seats_over_free == 0:
            result = CreateSubscriptionResult(
                status=CreateSubscriptionStatus.NOOP_ZERO_SEATS,
                company_id=company_id,
                seats_over_free=0,
                stripe_customer_id=company.stripe_customer_id,
            )
            await db.commit()
            return result

        seats_over_free = pricing.seats_over_free
        existing_customer_id = company.stripe_customer_id
        company_name = company.name
        company_email = company.email
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Stripe calls (outside DB lock)
    try:
        if existing_customer_id:
            stripe_customer_id = existing_customer_id
        else:
            customer = stripe.Customer.create(
                name=company_name,
                email=company_email,
                metadata={"company_id": str(company_id)},
                idempotency_key=customer_create_key,
                api_key=stripe_secret_key,
            )
            stripe_customer_id = customer.id

        subscription = stripe.Subscription.create(
            customer=stripe_customer_id,
            items=[
                {
                    "price": stripe_price_per_seat_monthly_id,
                    "quantity": seats_over_free,
                }
            ],
            idempotency_key=subscription_create_key,
            api_key=stripe_secret_key,
        )
    except (TimeoutError, stripe.error.StripeError) as exc:
        return CreateSubscriptionResult(
            status=CreateSubscriptionStatus.RETRIABLE_ERROR,
            company_id=company_id,
            seats_over_free=seats_over_free,
            message=str(exc),
        )

    subscription_id = subscription.id
    subscription_status = subscription.status
    final_status = CreateSubscriptionStatus.CREATED

    # Transaction B: re-lock + idempotent persistence
    try:
        company = await _get_company_for_update(db, company_id)
        if company is None:
            raise ValueError(f"Company {company_id} not found")

        if company.stripe_subscription_id:
            result = CreateSubscriptionResult(
                status=CreateSubscriptionStatus.NOOP_ALREADY_SUBSCRIBED,
                company_id=company_id,
                seats_over_free=seats_over_free,
                stripe_customer_id=company.stripe_customer_id,
                stripe_subscription_id=company.stripe_subscription_id,
            )
            await db.commit()
            return result

        company.stripe_customer_id = stripe_customer_id
        company.stripe_subscription_id = subscription_id

        if subscription_status in {"active", "trialing"}:
            company.subscription_tier = "standard"
        else:
            final_status = CreateSubscriptionStatus.REQUIRES_PAYMENT_ACTION

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return CreateSubscriptionResult(
        status=final_status,
        company_id=company_id,
        seats_over_free=seats_over_free,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=subscription_id,
        stripe_subscription_status=subscription_status,
    )
