"""Stripe webhook router.

Signature verification, event idempotency, and safe event dispatch (subscription.updated -> reconcile; payment_succeeded -> log).
"""

from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Company, StripeWebhookEvent
from app.services.billing_service import (
    _persist_created_subscription,
    downgrade_company_to_free,
    reconcile_company_subscription,
)
from app.utils.timewindow import now_utc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks: Stripe"])


def _event_field(obj: object, field: str):
    if isinstance(obj, dict):
        return obj.get(field)
    return getattr(obj, field, None)


def _resolve_customer_id(raw_customer: object) -> str | None:
    if raw_customer is None:
        return None
    if isinstance(raw_customer, str):
        return raw_customer
    if isinstance(raw_customer, dict):
        value = raw_customer.get("id")
        return value if isinstance(value, str) else None
    value = getattr(raw_customer, "id", None)
    return value if isinstance(value, str) else None


def _resolve_checkout_company_id(event_object: object) -> int | None:
    metadata = _event_field(event_object, "metadata")
    company_id_raw = _event_field(metadata, "company_id")
    if company_id_raw is None:
        return None
    try:
        return int(company_id_raw)
    except (TypeError, ValueError):
        return None


async def _dispatch_stripe_event(db: AsyncSession, event: object) -> None:
    event_type = _event_field(event, "type")
    if event_type == "checkout.session.completed":
        event_data = _event_field(event, "data")
        event_object = _event_field(event_data, "object")

        subscription_id = _event_field(event_object, "subscription")
        if not isinstance(subscription_id, str):
            subscription_id = _event_field(subscription_id, "id")
        if not isinstance(subscription_id, str):
            raise ValueError("checkout.session.completed missing subscription id")

        customer_id = _resolve_customer_id(_event_field(event_object, "customer"))
        company_id = _resolve_checkout_company_id(event_object)

        company: Company | None = None
        if company_id is not None:
            company_result = await db.execute(
                select(Company).where(Company.id == company_id).limit(1)
            )
            company = company_result.scalar_one_or_none()
        if company is None and customer_id:
            company_result = await db.execute(
                select(Company)
                .where(Company.stripe_customer_id == customer_id)
                .order_by(Company.id.asc())
                .limit(1)
            )
            company = company_result.scalar_one_or_none()
        if company is None:
            raise ValueError(
                "checkout.session.completed could not resolve company "
                f"(event_id={_event_field(event, 'id')}, company_id={company_id}, customer_id={customer_id})"
            )

        resolved_customer_id = customer_id or company.stripe_customer_id
        if not isinstance(resolved_customer_id, str):
            raise ValueError("checkout.session.completed missing customer id")

        stripe_secret_key = settings.STRIPE_SECRET_KEY.strip()
        if not stripe_secret_key:
            raise ValueError("STRIPE_SECRET_KEY missing for checkout.session.completed")

        subscription = stripe.Subscription.retrieve(
            subscription_id,
            expand=["items"],
            api_key=stripe_secret_key,
        )
        persist_status, persisted_subscription_id, persist_message = (
            await _persist_created_subscription(
                db,
                company.id,
                resolved_customer_id,
                subscription,
            )
        )
        sync_result = await reconcile_company_subscription(db, company.id)

        logger.info(
            (
                "stripe.webhook.checkout_completed.persisted "
                "event_id=%s company_id=%s persist_status=%s stripe_subscription_id=%s "
                "reconcile_status=%s target_quantity=%s persist_message=%s"
            ),
            _event_field(event, "id"),
            company.id,
            persist_status,
            persisted_subscription_id,
            sync_result.status,
            sync_result.target_quantity,
            persist_message,
        )
        return

    if event_type == "customer.subscription.updated":
        event_data = _event_field(event, "data")
        event_object = _event_field(event_data, "object")
        subscription_id = _event_field(event_object, "id")
        if not isinstance(subscription_id, str):
            subscription_id = None
        customer_id = _resolve_customer_id(_event_field(event_object, "customer"))

        filters = []
        if subscription_id:
            filters.append(Company.stripe_subscription_id == subscription_id)
        if customer_id:
            filters.append(Company.stripe_customer_id == customer_id)

        if not filters:
            logger.warning(
                "stripe.webhook.subscription_updated.no_identifiers event_id=%s",
                _event_field(event, "id"),
            )
            return

        company_result = await db.execute(
            select(Company)
            .where(or_(*filters))
            .order_by(Company.id.asc())
            .limit(1)
        )
        company = company_result.scalar_one_or_none()
        if company is None:
            logger.warning(
                (
                    "stripe.webhook.subscription_updated.company_not_found "
                    "event_id=%s stripe_subscription_id=%s stripe_customer_id=%s"
                ),
                _event_field(event, "id"),
                subscription_id,
                customer_id,
            )
            return

        sync_result = await reconcile_company_subscription(db, company.id)
        logger.info(
            (
                "stripe.webhook.subscription_updated.reconcile "
                "event_id=%s company_id=%s status=%s target_quantity=%s"
            ),
            _event_field(event, "id"),
            company.id,
            sync_result.status,
            sync_result.target_quantity,
        )
        return

    if event_type == "invoice.payment_succeeded":
        event_data = _event_field(event, "data")
        event_object = _event_field(event_data, "object")
        customer_id = _resolve_customer_id(_event_field(event_object, "customer"))
        logger.info(
            "stripe.webhook.invoice.payment_succeeded event_id=%s customer=%s",
            _event_field(event, "id"),
            customer_id,
        )
        return

    if event_type == "customer.subscription.deleted":
        event_data = _event_field(event, "data")
        event_object = _event_field(event_data, "object")
        subscription_id = _event_field(event_object, "id")
        if not isinstance(subscription_id, str):
            subscription_id = None
        customer_id = _resolve_customer_id(_event_field(event_object, "customer"))

        filters = []
        if subscription_id:
            filters.append(Company.stripe_subscription_id == subscription_id)
        if customer_id:
            filters.append(Company.stripe_customer_id == customer_id)

        if not filters:
            logger.warning(
                "stripe.webhook.subscription_deleted.no_identifiers event_id=%s",
                _event_field(event, "id"),
            )
            return

        company_result = await db.execute(
            select(Company)
            .where(or_(*filters))
            .order_by(Company.id.asc())
            .limit(1)
        )
        company = company_result.scalar_one_or_none()
        if company is None:
            logger.warning(
                (
                    "stripe.webhook.subscription_deleted.company_not_found "
                    "event_id=%s stripe_subscription_id=%s stripe_customer_id=%s"
                ),
                _event_field(event, "id"),
                subscription_id,
                customer_id,
            )
            return

        downgrade_result = await downgrade_company_to_free(db, company.id)
        logger.info(
            (
                "stripe.webhook.subscription_deleted.downgrade "
                "event_id=%s company_id=%s status=%s"
            ),
            _event_field(event, "id"),
            company.id,
            downgrade_result.status,
        )
        return

    if event_type == "invoice.payment_failed":
        event_data = _event_field(event, "data")
        event_object = _event_field(event_data, "object")
        customer_id = _resolve_customer_id(_event_field(event_object, "customer"))
        # Access policy is deferred to a later step (spec section 13).
        logger.warning(
            "stripe.webhook.invoice.payment_failed event_id=%s customer=%s",
            _event_field(event, "id"),
            customer_id,
        )
        return


@router.post("/stripe")
async def receive_stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive Stripe webhook payloads (public endpoint; signature-authenticated)."""
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET.strip()
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe webhook secret is not configured",
        )

    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            webhook_secret,
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    is_checkout_completed = event.type == "checkout.session.completed"

    # C1 scope note: processed_at retry semantics are intentionally enabled
    # only for checkout.session.completed. Other event types keep the
    # existing insert-then-dispatch behavior for compatibility in this step.
    if is_checkout_completed:
        stmt = (
            insert(StripeWebhookEvent)
            .values(event_id=event.id, event_type=event.type)
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        insert_result = await db.execute(stmt)
        if insert_result.rowcount == 0:
            existing_result = await db.execute(
                select(StripeWebhookEvent)
                .where(StripeWebhookEvent.event_id == event.id)
                .limit(1)
            )
            existing = existing_result.scalar_one_or_none()
            # Single idempotency guard: processed_at is set ONLY after a
            # successful dispatch (see below), so a non-null value means this
            # event was already fully processed -> ignore. A null value means a
            # prior attempt never completed; fall through to (re)dispatch.
            if existing is not None and existing.processed_at is not None:
                await db.commit()
                return {"status": "duplicate_ignored"}
            await db.commit()
            logger.info(
                "stripe.webhook.checkout_completed.retry_pending event_id=%s",
                event.id,
            )
        else:
            await db.commit()
            logger.info(
                "stripe.webhook.recorded event_id=%s event_type=%s",
                event.id,
                event.type,
            )

        try:
            await _dispatch_stripe_event(db, event)
        except Exception:
            logger.exception(
                "stripe.webhook.dispatch_failed event_id=%s event_type=%s",
                event.id,
                event.type,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook dispatch failed",
            )

        await db.execute(
            update(StripeWebhookEvent)
            .where(StripeWebhookEvent.event_id == event.id)
            .values(processed_at=now_utc())
        )
        await db.commit()
        return {"status": "recorded", "event_type": event.type}

    stmt = (
        insert(StripeWebhookEvent)
        .values(event_id=event.id, event_type=event.type)
        .on_conflict_do_nothing(index_elements=["event_id"])
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        await db.commit()
        return {"status": "duplicate_ignored"}

    await db.commit()
    logger.info("stripe.webhook.recorded event_id=%s event_type=%s", event.id, event.type)

    try:
        await _dispatch_stripe_event(db, event)
    except Exception:
        logger.exception(
            "stripe.webhook.dispatch_failed event_id=%s event_type=%s",
            event.id,
            event.type,
        )

    return {"status": "recorded", "event_type": event.type}
