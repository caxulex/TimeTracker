from __future__ import annotations

import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import stripe
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Company, StripeWebhookEvent
from app.services.billing_service import SyncResult, SyncStatus


def _fake_event(
    event_id: str = "evt_123",
    event_type: str = "invoice.payment_succeeded",
    data_object: object | None = None,
):
    if data_object is None:
        data_object = {"id": "in_default", "customer": "cus_default"}
    return SimpleNamespace(
        id=event_id,
        type=event_type,
        data=SimpleNamespace(object=data_object),
    )


async def _mk_company(db_session: AsyncSession, label: str) -> Company:
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        name=f"{label} {suffix}",
        slug=f"{label.lower()}-{suffix}",
        email=f"{label.lower()}-{suffix}@example.com",
    )
    db_session.add(company)
    await db_session.flush()
    await db_session.refresh(company)
    return company


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

        reconcile_mock = AsyncMock()
        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ), patch(
            "app.routers.webhooks.stripe.reconcile_company_subscription",
            reconcile_mock,
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
        reconcile_mock.assert_not_called()

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

    @pytest.mark.asyncio
    async def test_subscription_updated_known_company_records_and_reconciles(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        company = await _mk_company(db_session, "WebhookKnown")
        company.subscription_tier = "standard"
        company.stripe_customer_id = "cus_known"
        company.stripe_subscription_id = "sub_known"
        await db_session.commit()

        raw_body = b'{"id":"evt_sub_known","type":"customer.subscription.updated"}'
        fake_event = _fake_event(
            "evt_sub_known",
            "customer.subscription.updated",
            data_object={"id": "sub_known", "customer": "cus_known"},
        )

        reconcile_mock = AsyncMock(
            return_value=SyncResult(
                status=SyncStatus.UPDATED,
                company_id=company.id,
                target_quantity=2,
                stripe_subscription_id="sub_known",
            )
        )
        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ), patch(
            "app.routers.webhooks.stripe.reconcile_company_subscription",
            reconcile_mock,
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "recorded", "event_type": "customer.subscription.updated"}
        reconcile_mock.assert_called_once()
        assert reconcile_mock.await_args.args[1] == company.id

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_sub_known")
        )
        row = rows.scalar_one_or_none()
        assert row is not None
        assert row.event_type == "customer.subscription.updated"

    @pytest.mark.asyncio
    async def test_subscription_updated_unknown_company_records_without_reconcile(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
        caplog,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        raw_body = b'{"id":"evt_sub_unknown","type":"customer.subscription.updated"}'
        fake_event = _fake_event(
            "evt_sub_unknown",
            "customer.subscription.updated",
            data_object={"id": "sub_unknown", "customer": "cus_unknown"},
        )

        reconcile_mock = AsyncMock()
        caplog.set_level(logging.WARNING)
        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ), patch(
            "app.routers.webhooks.stripe.reconcile_company_subscription",
            reconcile_mock,
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "recorded", "event_type": "customer.subscription.updated"}
        reconcile_mock.assert_not_called()
        assert "subscription_updated.company_not_found" in caplog.text

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_sub_unknown")
        )
        assert rows.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_subscription_updated_dispatch_error_is_swallowed_and_record_persists(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
        caplog,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        company = await _mk_company(db_session, "WebhookDispatchFail")
        company.subscription_tier = "standard"
        company.stripe_customer_id = "cus_dispatch"
        company.stripe_subscription_id = "sub_dispatch"
        await db_session.commit()

        raw_body = b'{"id":"evt_sub_dispatch","type":"customer.subscription.updated"}'
        fake_event = _fake_event(
            "evt_sub_dispatch",
            "customer.subscription.updated",
            data_object={"id": "sub_dispatch", "customer": "cus_dispatch"},
        )

        caplog.set_level(logging.ERROR)
        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ), patch(
            "app.routers.webhooks.stripe.reconcile_company_subscription",
            AsyncMock(side_effect=RuntimeError("sync failed")),
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "recorded", "event_type": "customer.subscription.updated"}
        assert "stripe.webhook.dispatch_failed" in caplog.text

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_sub_dispatch")
        )
        assert rows.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_invoice_payment_succeeded_records_and_logs_only(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
        caplog,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        raw_body = b'{"id":"evt_invoice_ok","type":"invoice.payment_succeeded"}'
        fake_event = _fake_event(
            "evt_invoice_ok",
            "invoice.payment_succeeded",
            data_object={"id": "in_123", "customer": "cus_invoice"},
        )

        reconcile_mock = AsyncMock()
        caplog.set_level(logging.INFO)
        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ), patch(
            "app.routers.webhooks.stripe.reconcile_company_subscription",
            reconcile_mock,
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "recorded", "event_type": "invoice.payment_succeeded"}
        reconcile_mock.assert_not_called()
        assert "invoice.payment_succeeded" in caplog.text

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_invoice_ok")
        )
        assert rows.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_duplicate_subscription_updated_short_circuits_before_dispatch(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        db_session.add(
            StripeWebhookEvent(event_id="evt_dup_sub_updated", event_type="customer.subscription.updated")
        )
        await db_session.commit()

        raw_body = b'{"id":"evt_dup_sub_updated","type":"customer.subscription.updated"}'
        fake_event = _fake_event(
            "evt_dup_sub_updated",
            "customer.subscription.updated",
            data_object={"id": "sub_dup", "customer": "cus_dup"},
        )

        reconcile_mock = AsyncMock()
        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ), patch(
            "app.routers.webhooks.stripe.reconcile_company_subscription",
            reconcile_mock,
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "duplicate_ignored"}
        reconcile_mock.assert_not_called()