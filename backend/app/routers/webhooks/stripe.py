"""Stripe webhook router.

Signature verification, event idempotency, and safe event dispatch (subscription.updated -> reconcile; payment_succeeded -> log).
"""

from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Company, StripeWebhookEvent
from app.services.billing_service import reconcile_company_subscription

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


async def _dispatch_stripe_event(db: AsyncSession, event: object) -> None:
    event_type = _event_field(event, "type")
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
