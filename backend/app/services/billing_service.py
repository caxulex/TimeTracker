"""Billing primitives and Stripe subscription creation for seat-based billing.

Current scope:
- Count billable workers for a company from attached ``User`` rows.
- Compute deterministic monthly pricing summary from worker count.
- Create a per-seat Stripe subscription for the standard tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging

import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Company, User


FREE_WORKER_LIMIT = 3
PER_SEAT_MONTHLY_PRICE_DOLLARS = 5
UNLIMITED_MONTHLY_PRICE_DOLLARS = 50


logger = logging.getLogger(__name__)


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


class SyncStatus(str, Enum):
    COMPANY_NOT_FOUND = "company_not_found"
    NOOP_NOT_STANDARD = "noop_not_standard"
    NOOP_NOTHING_TO_DO = "noop_nothing_to_do"
    NOOP_ZERO_WITH_SUBSCRIPTION = "noop_zero_with_subscription"
    CREATED = "created"
    UPDATED = "updated"
    REQUIRES_PAYMENT_ACTION = "requires_payment_action"
    RETRIABLE_ERROR = "retriable_error"
    CONFIG_ERROR = "config_error"


@dataclass(frozen=True)
class SyncResult:
    status: SyncStatus
    company_id: int
    target_quantity: int
    stripe_subscription_id: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class AddWorkerDecision:
    allowed: bool
    reason_code: str
    worker_count: int
    free_limit: int
    subscription_tier: str
    has_subscription: bool
    message: str


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


async def can_company_add_worker(db: AsyncSession, company_id: int) -> AddWorkerDecision:
    """Return whether one more worker may be attached to a company.

    This is a pre-check only (no mutation and no locking).

    Current enforcement note:
    - The staff-create-user path in users.py is the only existing path that
      attaches a user to an existing company and must call this guard.
    - If invitations.py is later fixed to attach invited users to a company,
      that accept-invite path must also call this guard to avoid a bypass.
    """

    if company_id <= 0:
        raise ValueError("company_id must be a positive integer")

    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()

    if company is None:
        return AddWorkerDecision(
            allowed=False,
            reason_code="company_not_found",
            worker_count=0,
            free_limit=FREE_WORKER_LIMIT,
            subscription_tier="unknown",
            has_subscription=False,
            message="Company not found.",
        )

    worker_count = await count_company_billable_workers(db, company_id)
    has_subscription = bool(company.stripe_subscription_id)
    is_free_unsubscribed = (
        company.stripe_subscription_id is None and company.subscription_tier == "free"
    )

    if is_free_unsubscribed and (worker_count + 1 > FREE_WORKER_LIMIT):
        return AddWorkerDecision(
            allowed=False,
            reason_code="blocked_free_limit",
            worker_count=worker_count,
            free_limit=FREE_WORKER_LIMIT,
            subscription_tier=company.subscription_tier,
            has_subscription=has_subscription,
            message=(
                "You are at the free limit of 3 workers. Deactivated users still "
                "count toward this limit and can be DELETED to reclaim a slot, "
                "or you can upgrade to a paid plan."
            ),
        )

    return AddWorkerDecision(
        allowed=True,
        reason_code="allowed",
        worker_count=worker_count,
        free_limit=FREE_WORKER_LIMIT,
        subscription_tier=company.subscription_tier,
        has_subscription=has_subscription,
        message="OK to add worker.",
    )


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


async def sync_company_subscription_quantity(
    db: AsyncSession,
    company_id: int,
) -> SyncResult:
    """Synchronize a standard-tier company subscription quantity to billable seats."""

    if company_id <= 0:
        raise ValueError("company_id must be a positive integer")

    # Transaction A: lock row, read stable state, compute target, release lock.
    try:
        company = await _get_company_for_update(db, company_id)
        if company is None:
            await db.commit()
            return SyncResult(
                status=SyncStatus.COMPANY_NOT_FOUND,
                company_id=company_id,
                target_quantity=0,
                message="Company not found.",
            )

        subscription_tier = company.subscription_tier
        stripe_subscription_id = company.stripe_subscription_id
        worker_count = await count_company_billable_workers(db, company_id)
        target_quantity = max(0, worker_count - FREE_WORKER_LIMIT)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    if subscription_tier != "standard":
        return SyncResult(
            status=SyncStatus.NOOP_NOT_STANDARD,
            company_id=company_id,
            target_quantity=target_quantity,
            stripe_subscription_id=stripe_subscription_id,
            message="Company tier is not standard; no per-seat sync required.",
        )

    stripe_secret_key = settings.STRIPE_SECRET_KEY.strip()
    stripe_price_per_seat_monthly_id = (
        getattr(settings, "STRIPE_PRICE_PER_SEAT_MONTHLY_ID", "").strip()
    )
    if not stripe_secret_key or not stripe_price_per_seat_monthly_id:
        return SyncResult(
            status=SyncStatus.CONFIG_ERROR,
            company_id=company_id,
            target_quantity=target_quantity,
            stripe_subscription_id=stripe_subscription_id,
            message=(
                "Stripe configuration missing: STRIPE_SECRET_KEY and "
                "STRIPE_PRICE_PER_SEAT_MONTHLY_ID are required"
            ),
        )

    if target_quantity >= 1 and not stripe_subscription_id:
        create_result = await create_standard_subscription(db, company_id)
        status_map = {
            CreateSubscriptionStatus.CREATED: SyncStatus.CREATED,
            CreateSubscriptionStatus.REQUIRES_PAYMENT_ACTION: SyncStatus.REQUIRES_PAYMENT_ACTION,
            CreateSubscriptionStatus.RETRIABLE_ERROR: SyncStatus.RETRIABLE_ERROR,
            CreateSubscriptionStatus.CONFIG_ERROR: SyncStatus.CONFIG_ERROR,
            CreateSubscriptionStatus.NOOP_ZERO_SEATS: SyncStatus.NOOP_NOTHING_TO_DO,
            CreateSubscriptionStatus.NOOP_ALREADY_SUBSCRIBED: SyncStatus.UPDATED,
        }
        return SyncResult(
            status=status_map[create_result.status],
            company_id=company_id,
            target_quantity=target_quantity,
            stripe_subscription_id=create_result.stripe_subscription_id,
            message=create_result.message,
        )

    if target_quantity >= 1 and stripe_subscription_id:
        modify_key = f"subscription-sync-company-{company_id}-qty-{target_quantity}"
        try:
            subscription = stripe.Subscription.retrieve(
                stripe_subscription_id,
                api_key=stripe_secret_key,
            )
            subscription_items = getattr(getattr(subscription, "items", None), "data", [])
            if not subscription_items:
                return SyncResult(
                    status=SyncStatus.RETRIABLE_ERROR,
                    company_id=company_id,
                    target_quantity=target_quantity,
                    stripe_subscription_id=stripe_subscription_id,
                    message="Stripe subscription has no items to update.",
                )

            item_id = subscription_items[0].id
            stripe.Subscription.modify(
                stripe_subscription_id,
                items=[{"id": item_id, "quantity": target_quantity}],
                idempotency_key=modify_key,
                api_key=stripe_secret_key,
            )
        except (TimeoutError, stripe.error.StripeError) as exc:
            return SyncResult(
                status=SyncStatus.RETRIABLE_ERROR,
                company_id=company_id,
                target_quantity=target_quantity,
                stripe_subscription_id=stripe_subscription_id,
                message=str(exc),
            )

        return SyncResult(
            status=SyncStatus.UPDATED,
            company_id=company_id,
            target_quantity=target_quantity,
            stripe_subscription_id=stripe_subscription_id,
        )

    if target_quantity == 0 and stripe_subscription_id:
        logger.warning(
            "Seat sync no-op for company %s: target quantity is zero but subscription %s exists",
            company_id,
            stripe_subscription_id,
        )
        return SyncResult(
            status=SyncStatus.NOOP_ZERO_WITH_SUBSCRIPTION,
            company_id=company_id,
            target_quantity=0,
            stripe_subscription_id=stripe_subscription_id,
            message="Target quantity is zero while subscription exists; deferred decision.",
        )

    return SyncResult(
        status=SyncStatus.NOOP_NOTHING_TO_DO,
        company_id=company_id,
        target_quantity=0,
        stripe_subscription_id=stripe_subscription_id,
    )


async def reconcile_all_standard_subscriptions(db: AsyncSession) -> list[SyncResult]:
    """Run seat-sync reconciliation for every standard-tier company."""

    result = await db.execute(
        select(Company.id)
        .where(Company.subscription_tier == "standard")
        .order_by(Company.id.asc())
    )
    company_ids = [int(company_id) for company_id in result.scalars().all()]

    sync_results: list[SyncResult] = []
    for company_id in company_ids:
        sync_results.append(await sync_company_subscription_quantity(db, company_id))

    return sync_results
