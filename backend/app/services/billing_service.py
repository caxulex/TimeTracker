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
    CHECKOUT_REQUIRED = "checkout_required"
    REQUIRES_PAYMENT_ACTION = "requires_payment_action"
    RETRIABLE_ERROR = "retriable_error"
    CONFIG_ERROR = "config_error"


@dataclass(frozen=True)
class SyncResult:
    status: SyncStatus
    company_id: int
    target_quantity: int
    stripe_subscription_id: str | None = None
    checkout_url: str | None = None
    message: str | None = None


class SwitchStatus(str, Enum):
    COMPANY_NOT_FOUND = "company_not_found"
    NOOP_ALREADY_FREE = "noop_already_free"
    NOOP_ALREADY_UNLIMITED = "noop_already_unlimited"
    SWITCHED = "switched"
    DOWNGRADED_TO_FREE = "downgraded_to_free"
    SWITCHED_COMPED = "switched_comped"
    REQUIRES_PAYMENT_ACTION = "requires_payment_action"
    RETRIABLE_ERROR = "retriable_error"
    CONFIG_ERROR = "config_error"


@dataclass(frozen=True)
class SwitchResult:
    status: SwitchStatus
    company_id: int
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


async def _persist_created_subscription(
    db: AsyncSession,
    company_id: int,
    resolved_customer_id: str,
    subscription: stripe.Subscription,
) -> tuple[SyncStatus, str, str | None]:
    """Persist a newly created Stripe subscription under company row lock.

    Returns:
        (status, stripe_subscription_id, message)
    """
    company = await _get_company_for_update(db, company_id)
    if company is None:
        raise ValueError(f"Company {company_id} not found")

    if company.stripe_subscription_id:
        await db.commit()
        return (
            SyncStatus.UPDATED,
            company.stripe_subscription_id,
            "Company already subscribed during sync persistence.",
        )

    company.stripe_customer_id = resolved_customer_id
    company.stripe_subscription_id = subscription.id
    if subscription.status in {"active", "trialing"}:
        company.subscription_tier = "standard"
        status = SyncStatus.CREATED
    else:
        status = SyncStatus.REQUIRES_PAYMENT_ACTION

    await db.commit()
    return (status, subscription.id, None)


async def _resolve_or_create_stripe_customer(
    *,
    company_id: int,
    company_name: str,
    company_email: str,
    existing_customer_id: str | None,
    customer_create_key: str,
    stripe_secret_key: str,
) -> str:
    """Resolve or create the Stripe customer."""

    if existing_customer_id:
        customer_id = existing_customer_id
        return customer_id

    create_kwargs = dict(
        name=company_name,
        email=company_email,
        metadata={"company_id": str(company_id)},
        idempotency_key=customer_create_key,
        api_key=stripe_secret_key,
    )

    customer = stripe.Customer.create(**create_kwargs)
    return customer.id


def _stripe_field(obj: object, field: str):
    if isinstance(obj, dict):
        return obj.get(field)
    return getattr(obj, field, None)


def _customer_has_chargeable_card_payment_method(
    customer_id: str,
    stripe_secret_key: str,
) -> bool:
    """Return whether a customer has a chargeable card payment method."""
    try:
        customer = stripe.Customer.retrieve(
            customer_id,
            expand=["invoice_settings.default_payment_method"],
            api_key=stripe_secret_key,
        )
        invoice_settings = _stripe_field(customer, "invoice_settings")
        default_pm = _stripe_field(invoice_settings, "default_payment_method")
        if default_pm:
            default_pm_type = _stripe_field(default_pm, "type")
            if default_pm_type is None:
                # Expanded default PMs are usually objects; if Stripe returns an id
                # string here, treat it as present and chargeable.
                return True
            if default_pm_type == "card":
                return True

        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type="card",
            limit=1,
            api_key=stripe_secret_key,
        )
        pm_data = _stripe_field(payment_methods, "data") or []
        return len(pm_data) > 0
    except (TimeoutError, stripe.error.StripeError) as exc:
        # Fail TOWARD Checkout: if we cannot confirm a chargeable PM, route the
        # customer through Checkout (which safely collects a card). Returning
        # True here would send a possibly-cardless customer to Subscription.create,
        # producing a stuck "incomplete" subscription -- the exact failure Checkout
        # exists to prevent. Checkout is safe even when a card already exists.
        logger.warning(
            "Stripe payment-method inspection failed for customer %s; "
            "routing to Checkout: %s",
            customer_id,
            exc,
        )
        return False


def _create_checkout_session_for_standard_subscription(
    *,
    company_id: int,
    resolved_customer_id: str,
    price_id: str,
    quantity: int,
    stripe_secret_key: str,
):
    checkout_success_url = (
        getattr(settings, "STRIPE_CHECKOUT_SUCCESS_URL", "").strip()
        or "https://timetracker.shaemarcus.com/billing"
    )
    checkout_cancel_url = (
        getattr(settings, "STRIPE_CHECKOUT_CANCEL_URL", "").strip()
        or "https://timetracker.shaemarcus.com/billing"
    )

    return stripe.checkout.Session.create(
        mode="subscription",
        customer=resolved_customer_id,
        line_items=[{"price": price_id, "quantity": quantity}],
        metadata={"company_id": str(company_id)},
        subscription_data={"metadata": {"company_id": str(company_id)}},
        success_url=checkout_success_url,
        cancel_url=checkout_cancel_url,
        idempotency_key=f"checkout-session-company-{company_id}",
        api_key=stripe_secret_key,
    )


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
        stripe_customer_id = await _resolve_or_create_stripe_customer(
            company_id=company_id,
            company_name=company_name,
            company_email=company_email,
            existing_customer_id=existing_customer_id,
            customer_create_key=customer_create_key,
            stripe_secret_key=stripe_secret_key,
        )

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

    worker_count = await count_company_billable_workers(db, company_id)
    target_quantity = max(0, worker_count - FREE_WORKER_LIMIT)
    return await _sync_subscription_to_target(db, company_id, target_quantity)


async def _sync_subscription_to_target(
    db: AsyncSession,
    company_id: int,
    target_quantity: int,
) -> SyncResult:
    """Synchronize a standard-tier company subscription quantity to an explicit target."""

    if company_id <= 0:
        raise ValueError("company_id must be a positive integer")
    if target_quantity < 0:
        raise ValueError("target_quantity cannot be negative")

    # Transaction A: lock row, read stable state, release lock.
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
        stripe_customer_id = company.stripe_customer_id
        company_name = company.name
        company_email = company.email
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
        customer_create_key = f"customer-create-company-{company_id}"
        subscription_create_key = f"subscription-create-company-{company_id}"
        try:
            resolved_customer_id = await _resolve_or_create_stripe_customer(
                company_id=company_id,
                company_name=company_name,
                company_email=company_email,
                existing_customer_id=stripe_customer_id,
                customer_create_key=customer_create_key,
                stripe_secret_key=stripe_secret_key,
            )

            has_chargeable_pm = _customer_has_chargeable_card_payment_method(
                resolved_customer_id,
                stripe_secret_key,
            )

            if not has_chargeable_pm:
                checkout_session = _create_checkout_session_for_standard_subscription(
                    company_id=company_id,
                    resolved_customer_id=resolved_customer_id,
                    price_id=stripe_price_per_seat_monthly_id,
                    quantity=target_quantity,
                    stripe_secret_key=stripe_secret_key,
                )
                return SyncResult(
                    status=SyncStatus.CHECKOUT_REQUIRED,
                    company_id=company_id,
                    target_quantity=target_quantity,
                    checkout_url=_stripe_field(checkout_session, "url"),
                    message="Checkout required to collect a valid payment method.",
                )

            subscription = stripe.Subscription.create(
                customer=resolved_customer_id,
                items=[
                    {
                        "price": stripe_price_per_seat_monthly_id,
                        "quantity": target_quantity,
                    }
                ],
                idempotency_key=subscription_create_key,
                api_key=stripe_secret_key,
            )
        except (TimeoutError, stripe.error.StripeError) as exc:
            return SyncResult(
                status=SyncStatus.RETRIABLE_ERROR,
                company_id=company_id,
                target_quantity=target_quantity,
                message=str(exc),
            )

        try:
            final_status, persisted_subscription_id, persist_message = (
                await _persist_created_subscription(
                    db,
                    company_id,
                    resolved_customer_id,
                    subscription,
                )
            )
        except Exception:
            await db.rollback()
            raise

        return SyncResult(
            status=final_status,
            company_id=company_id,
            target_quantity=target_quantity,
            stripe_subscription_id=persisted_subscription_id,
            message=persist_message,
        )

    if target_quantity >= 1 and stripe_subscription_id:
        modify_key = f"subscription-sync-company-{company_id}-qty-{target_quantity}"
        try:
            subscription = stripe.Subscription.retrieve(
                stripe_subscription_id,
                expand=["items"],
                api_key=stripe_secret_key,
            )
            subscription_items = subscription["items"]["data"]
            if not subscription_items:
                return SyncResult(
                    status=SyncStatus.RETRIABLE_ERROR,
                    company_id=company_id,
                    target_quantity=target_quantity,
                    stripe_subscription_id=stripe_subscription_id,
                    message="Stripe subscription has no items to update.",
                )

            item_id = subscription_items[0]["id"]
            stripe.Subscription.modify(
                stripe_subscription_id,
                items=[{"id": item_id, "quantity": target_quantity}],
                proration_behavior="create_prorations",
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


async def switch_company_to_unlimited(
    db: AsyncSession,
    company_id: int,
) -> SwitchResult:
    """Switch a company to the unlimited monthly plan."""

    if company_id <= 0:
        raise ValueError("company_id must be a positive integer")

    stripe_secret_key = settings.STRIPE_SECRET_KEY.strip()
    stripe_price_unlimited_monthly_id = (
        getattr(settings, "STRIPE_PRICE_UNLIMITED_MONTHLY_ID", "").strip()
    )

    company_tier = ""
    stripe_subscription_id: str | None = None
    stripe_customer_id: str | None = None
    company_name = ""
    company_email = ""
    billable_workers = 0

    try:
        company = await _get_company_for_update(db, company_id)
        if company is None:
            await db.commit()
            return SwitchResult(
                status=SwitchStatus.COMPANY_NOT_FOUND,
                company_id=company_id,
                message="Company not found.",
            )

        company_tier = company.subscription_tier
        stripe_subscription_id = company.stripe_subscription_id
        stripe_customer_id = company.stripe_customer_id
        company_name = company.name
        company_email = company.email
        billable_workers = await count_company_billable_workers(db, company_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    if company_tier == "unlimited":
        return SwitchResult(
            status=SwitchStatus.NOOP_ALREADY_UNLIMITED,
            company_id=company_id,
            stripe_subscription_id=stripe_subscription_id,
            message="Company is already on the unlimited tier.",
        )

    if company_tier == "standard" and not stripe_subscription_id:
        try:
            company = await _get_company_for_update(db, company_id)
            if company is None:
                await db.commit()
                return SwitchResult(
                    status=SwitchStatus.COMPANY_NOT_FOUND,
                    company_id=company_id,
                    message="Company not found.",
                )

            if company.subscription_tier == "unlimited":
                await db.commit()
                return SwitchResult(
                    status=SwitchStatus.NOOP_ALREADY_UNLIMITED,
                    company_id=company_id,
                    stripe_subscription_id=company.stripe_subscription_id,
                    message="Company is already on the unlimited tier.",
                )

            company.subscription_tier = "unlimited"
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        return SwitchResult(
            status=SwitchStatus.SWITCHED_COMPED,
            company_id=company_id,
            stripe_subscription_id=stripe_subscription_id,
            message="Company had no Stripe subscription to swap; marked unlimited.",
        )

    if company_tier == "free" and billable_workers == 0:
        try:
            company = await _get_company_for_update(db, company_id)
            if company is None:
                await db.commit()
                return SwitchResult(
                    status=SwitchStatus.COMPANY_NOT_FOUND,
                    company_id=company_id,
                    message="Company not found.",
                )

            if company.subscription_tier == "unlimited":
                await db.commit()
                return SwitchResult(
                    status=SwitchStatus.NOOP_ALREADY_UNLIMITED,
                    company_id=company_id,
                    stripe_subscription_id=company.stripe_subscription_id,
                    message="Company is already on the unlimited tier.",
                )

            company.subscription_tier = "unlimited"
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        return SwitchResult(
            status=SwitchStatus.SWITCHED_COMPED,
            company_id=company_id,
            stripe_subscription_id=stripe_subscription_id,
            message="Company had no billable workers and was marked unlimited without Stripe.",
        )

    if not stripe_secret_key or not stripe_price_unlimited_monthly_id:
        return SwitchResult(
            status=SwitchStatus.CONFIG_ERROR,
            company_id=company_id,
            stripe_subscription_id=stripe_subscription_id,
            message=(
                "Stripe configuration missing: STRIPE_SECRET_KEY and "
                "STRIPE_PRICE_UNLIMITED_MONTHLY_ID are required"
            ),
        )

    if company_tier == "standard" and stripe_subscription_id:
        switch_key = f"subscription-switch-unlimited-company-{company_id}"
        try:
            subscription = stripe.Subscription.retrieve(
                stripe_subscription_id,
                expand=["items"],
                api_key=stripe_secret_key,
            )
            subscription_items = subscription["items"]["data"]
            if not subscription_items:
                return SwitchResult(
                    status=SwitchStatus.RETRIABLE_ERROR,
                    company_id=company_id,
                    stripe_subscription_id=stripe_subscription_id,
                    message="Stripe subscription has no items to update.",
                )

            item_id = subscription_items[0]["id"]
            subscription = stripe.Subscription.modify(
                stripe_subscription_id,
                items=[
                    {
                        "id": item_id,
                        "price": stripe_price_unlimited_monthly_id,
                        "quantity": 1,
                    }
                ],
                proration_behavior="create_prorations",
                idempotency_key=switch_key,
                api_key=stripe_secret_key,
            )
        except (TimeoutError, stripe.error.StripeError) as exc:
            return SwitchResult(
                status=SwitchStatus.RETRIABLE_ERROR,
                company_id=company_id,
                stripe_subscription_id=stripe_subscription_id,
                message=str(exc),
            )

        subscription_status = getattr(subscription, "status", None)
        if subscription_status in {"incomplete", "past_due"}:
            return SwitchResult(
                status=SwitchStatus.REQUIRES_PAYMENT_ACTION,
                company_id=company_id,
                stripe_subscription_id=stripe_subscription_id,
                message="Stripe subscription requires payment action.",
            )

        try:
            company = await _get_company_for_update(db, company_id)
            if company is None:
                await db.commit()
                return SwitchResult(
                    status=SwitchStatus.COMPANY_NOT_FOUND,
                    company_id=company_id,
                    stripe_subscription_id=stripe_subscription_id,
                    message="Company not found.",
                )

            if company.subscription_tier == "unlimited":
                await db.commit()
                return SwitchResult(
                    status=SwitchStatus.NOOP_ALREADY_UNLIMITED,
                    company_id=company_id,
                    stripe_subscription_id=company.stripe_subscription_id,
                    message="Company is already on the unlimited tier.",
                )

            company.subscription_tier = "unlimited"
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        return SwitchResult(
            status=SwitchStatus.SWITCHED,
            company_id=company_id,
            stripe_subscription_id=stripe_subscription_id,
            message="Company subscription switched to unlimited.",
        )

    if company_tier == "free" and billable_workers >= 1:
        customer_create_key = f"customer-create-company-{company_id}"
        subscription_create_key = f"subscription-create-company-{company_id}"

        try:
            resolved_customer_id = await _resolve_or_create_stripe_customer(
                company_id=company_id,
                company_name=company_name,
                company_email=company_email,
                existing_customer_id=stripe_customer_id,
                customer_create_key=customer_create_key,
                stripe_secret_key=stripe_secret_key,
            )

            subscription = stripe.Subscription.create(
                customer=resolved_customer_id,
                items=[
                    {
                        "price": stripe_price_unlimited_monthly_id,
                        "quantity": 1,
                    }
                ],
                idempotency_key=subscription_create_key,
                api_key=stripe_secret_key,
            )
        except (TimeoutError, stripe.error.StripeError) as exc:
            return SwitchResult(
                status=SwitchStatus.RETRIABLE_ERROR,
                company_id=company_id,
                message=str(exc),
            )

        subscription_status = getattr(subscription, "status", None)
        if subscription_status in {"incomplete", "past_due"}:
            try:
                company = await _get_company_for_update(db, company_id)
                if company is None:
                    await db.commit()
                    return SwitchResult(
                        status=SwitchStatus.COMPANY_NOT_FOUND,
                        company_id=company_id,
                        stripe_subscription_id=subscription.id,
                        message="Company not found.",
                    )

                company.stripe_customer_id = resolved_customer_id
                company.stripe_subscription_id = subscription.id
                await db.commit()
            except Exception:
                await db.rollback()
                raise

            return SwitchResult(
                status=SwitchStatus.REQUIRES_PAYMENT_ACTION,
                company_id=company_id,
                stripe_subscription_id=subscription.id,
                message="Stripe subscription requires payment action.",
            )

        try:
            company = await _get_company_for_update(db, company_id)
            if company is None:
                await db.commit()
                return SwitchResult(
                    status=SwitchStatus.COMPANY_NOT_FOUND,
                    company_id=company_id,
                    stripe_subscription_id=subscription.id,
                    message="Company not found.",
                )

            if company.subscription_tier == "unlimited":
                await db.commit()
                return SwitchResult(
                    status=SwitchStatus.NOOP_ALREADY_UNLIMITED,
                    company_id=company_id,
                    stripe_subscription_id=company.stripe_subscription_id,
                    message="Company is already on the unlimited tier.",
                )

            company.stripe_customer_id = resolved_customer_id
            company.stripe_subscription_id = subscription.id
            company.subscription_tier = "unlimited"
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        return SwitchResult(
            status=SwitchStatus.SWITCHED,
            company_id=company_id,
            stripe_subscription_id=subscription.id,
            message="Company subscription created for unlimited billing.",
        )

    return SwitchResult(
        status=SwitchStatus.RETRIABLE_ERROR,
        company_id=company_id,
        stripe_subscription_id=stripe_subscription_id,
        message="Unsupported billing state for unlimited switch.",
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


async def reconcile_company_subscription(
    db: AsyncSession,
    company_id: int,
) -> SyncResult:
    """Run seat-sync reconciliation for one company via the shared sync path."""

    if company_id <= 0:
        raise ValueError("company_id must be a positive integer")

    result = await db.execute(select(Company.id).where(Company.id == company_id))
    existing_company_id = result.scalar_one_or_none()
    if existing_company_id is None:
        return SyncResult(
            status=SyncStatus.COMPANY_NOT_FOUND,
            company_id=company_id,
            target_quantity=0,
            message="Company not found.",
        )

    return await sync_company_subscription_quantity(db, company_id)


async def downgrade_company_to_free(
    db: AsyncSession,
    company_id: int,
) -> SwitchResult:
    """Downgrade a company to free after subscription termination."""

    if company_id <= 0:
        raise ValueError("company_id must be a positive integer")

    try:
        company = await _get_company_for_update(db, company_id)
        if company is None:
            await db.commit()
            return SwitchResult(
                status=SwitchStatus.COMPANY_NOT_FOUND,
                company_id=company_id,
                message="Company not found.",
            )

        if company.subscription_tier == "free":
            existing_subscription_id = company.stripe_subscription_id
            await db.commit()
            return SwitchResult(
                status=SwitchStatus.NOOP_ALREADY_FREE,
                company_id=company_id,
                stripe_subscription_id=existing_subscription_id,
                message="Company is already on the free tier.",
            )

        company.subscription_tier = "free"
        company.stripe_subscription_id = None
        kept_customer_id = company.stripe_customer_id
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return SwitchResult(
        status=SwitchStatus.DOWNGRADED_TO_FREE,
        company_id=company_id,
        stripe_subscription_id=None,
        message=(
            "Company downgraded to free tier; subscription cleared and customer retained "
            f"({kept_customer_id})."
        ),
    )
