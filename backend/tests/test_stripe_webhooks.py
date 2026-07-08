from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import stripe
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import StripeWebhookEvent


def _fake_event(event_id: str = "evt_123", event_type: str = "invoice.payment_succeeded"):
    return SimpleNamespace(id=event_id, type=event_type)


class TestStripeWebhook:
    @pytest.mark.asyncio
    async def test_valid_signature_records_new_event(self, client, db_session: AsyncSession, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        raw_body = b'{"id":"evt_1","type":"invoice.payment_succeeded"}'
        fake_event = _fake_event("evt_1", "invoice.payment_succeeded")

        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ) as mocked_construct:
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "recorded", "event_type": "invoice.payment_succeeded"}
        mocked_construct.assert_called_once_with(raw_body, "t=1,v1=test", "whsec_test_secret")

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_1")
        )
        row = rows.scalar_one_or_none()
        assert row is not None
        assert row.event_type == "invoice.payment_succeeded"

    @pytest.mark.asyncio
    async def test_duplicate_event_is_ignored(self, client, db_session: AsyncSession, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        db_session.add(
            StripeWebhookEvent(event_id="evt_dup", event_type="customer.subscription.updated")
        )
        await db_session.commit()

        fake_event = _fake_event("evt_dup", "customer.subscription.updated")
        raw_body = b'{"id":"evt_dup","type":"customer.subscription.updated"}'

        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "duplicate_ignored"}

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_dup")
        )
        assert len(rows.scalars().all()) == 1

    @pytest.mark.asyncio
    async def test_bad_signature_returns_400(self, client, db_session: AsyncSession, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        raw_body = b'{"id":"evt_bad","type":"invoice.payment_failed"}'

        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError(
                "bad sig",
                "t=1,v1=test",
                raw_body,
            ),
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid signature"}

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_bad")
        )
        assert rows.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_malformed_payload_returns_400(self, client, db_session: AsyncSession, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        raw_body = b'{"id":"evt_bad_json","type":'

        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            side_effect=ValueError("malformed payload"),
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid signature"}

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_bad_json")
        )
        assert rows.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_missing_secret_returns_500_without_verification(self, client, db_session: AsyncSession, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        raw_body = b'{"id":"evt_no_secret","type":"some.random.event"}'

        with patch("app.routers.webhooks.stripe.stripe.Webhook.construct_event") as mocked_construct:
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 500
        assert response.json() == {"detail": "Stripe webhook secret is not configured"}
        mocked_construct.assert_not_called()

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_no_secret")
        )
        assert rows.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_unknown_event_type_is_recorded(self, client, db_session: AsyncSession, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        raw_body = b'{"id":"evt_unknown","type":"some.random.event"}'
        fake_event = _fake_event("evt_unknown", "some.random.event")

        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "recorded", "event_type": "some.random.event"}

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_unknown")
        )
        row = rows.scalar_one_or_none()
        assert row is not None
        assert row.event_type == "some.random.event"

    @pytest.mark.asyncio
    async def test_raw_body_is_passed_to_stripe_verifier(self, client, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        raw_body = b'{"id":"evt_raw","type":"invoice.payment_succeeded","nested":{"a":1}}'
        fake_event = _fake_event("evt_raw", "invoice.payment_succeeded")

        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ) as mocked_construct:
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        args, _kwargs = mocked_construct.call_args
        assert args[0] == raw_body