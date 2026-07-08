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
from app.services.billing_service import (
    SwitchResult,
    SwitchStatus,
    SyncResult,
    SyncStatus,
)


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

    @pytest.mark.asyncio
    async def test_subscription_deleted_known_company_records_and_downgrades(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        company = await _mk_company(db_session, "WebhookDeleteKnown")
        company.subscription_tier = "standard"
        company.stripe_customer_id = "cus_delete_known"
        company.stripe_subscription_id = "sub_delete_known"
        await db_session.commit()

        raw_body = b'{"id":"evt_sub_deleted_known","type":"customer.subscription.deleted"}'
        fake_event = _fake_event(
            "evt_sub_deleted_known",
            "customer.subscription.deleted",
            data_object={"id": "sub_delete_known", "customer": "cus_delete_known"},
        )

        downgrade_mock = AsyncMock(
            return_value=SwitchResult(
                status=SwitchStatus.DOWNGRADED_TO_FREE,
                company_id=company.id,
                stripe_subscription_id=None,
            )
        )
        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ), patch(
            "app.routers.webhooks.stripe.downgrade_company_to_free",
            downgrade_mock,
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "recorded", "event_type": "customer.subscription.deleted"}
        downgrade_mock.assert_awaited_once_with(db_session, company.id)

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_sub_deleted_known")
        )
        assert rows.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_subscription_deleted_unknown_company_records_without_downgrade(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
        caplog,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        raw_body = b'{"id":"evt_sub_deleted_unknown","type":"customer.subscription.deleted"}'
        fake_event = _fake_event(
            "evt_sub_deleted_unknown",
            "customer.subscription.deleted",
            data_object={"id": "sub_deleted_unknown", "customer": "cus_deleted_unknown"},
        )

        downgrade_mock = AsyncMock()
        caplog.set_level(logging.WARNING)
        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ), patch(
            "app.routers.webhooks.stripe.downgrade_company_to_free",
            downgrade_mock,
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "recorded", "event_type": "customer.subscription.deleted"}
        downgrade_mock.assert_not_called()
        assert "subscription_deleted.company_not_found" in caplog.text

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_sub_deleted_unknown")
        )
        assert rows.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_subscription_deleted_dispatch_error_is_swallowed_and_record_persists(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
        caplog,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        company = await _mk_company(db_session, "WebhookDeleteDispatchFail")
        company.subscription_tier = "standard"
        company.stripe_customer_id = "cus_delete_dispatch"
        company.stripe_subscription_id = "sub_delete_dispatch"
        await db_session.commit()

        raw_body = b'{"id":"evt_sub_deleted_dispatch","type":"customer.subscription.deleted"}'
        fake_event = _fake_event(
            "evt_sub_deleted_dispatch",
            "customer.subscription.deleted",
            data_object={"id": "sub_delete_dispatch", "customer": "cus_delete_dispatch"},
        )

        caplog.set_level(logging.ERROR)
        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ), patch(
            "app.routers.webhooks.stripe.downgrade_company_to_free",
            AsyncMock(side_effect=RuntimeError("downgrade failed")),
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "recorded", "event_type": "customer.subscription.deleted"}
        assert "stripe.webhook.dispatch_failed" in caplog.text

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_sub_deleted_dispatch")
        )
        assert rows.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_subscription_deleted_scopes_to_matching_company_only(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")

        company_a = await _mk_company(db_session, "WebhookDeleteScopeA")
        company_a.subscription_tier = "standard"
        company_a.stripe_customer_id = "cus_scope_a"
        company_a.stripe_subscription_id = "sub_scope_a"

        company_b = await _mk_company(db_session, "WebhookDeleteScopeB")
        company_b.subscription_tier = "unlimited"
        company_b.stripe_customer_id = "cus_scope_b"
        company_b.stripe_subscription_id = "sub_scope_b"
        await db_session.commit()

        raw_body = b'{"id":"evt_sub_deleted_scope","type":"customer.subscription.deleted"}'
        fake_event = _fake_event(
            "evt_sub_deleted_scope",
            "customer.subscription.deleted",
            data_object={"id": "sub_scope_a", "customer": "cus_scope_a"},
        )

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
        assert response.json() == {"status": "recorded", "event_type": "customer.subscription.deleted"}

        await db_session.refresh(company_a)
        await db_session.refresh(company_b)
        assert company_a.subscription_tier == "free"
        assert company_a.stripe_subscription_id is None
        assert company_a.stripe_customer_id == "cus_scope_a"

        assert company_b.subscription_tier == "unlimited"
        assert company_b.stripe_subscription_id == "sub_scope_b"

    @pytest.mark.asyncio
    async def test_invoice_payment_failed_recorded_warning_logged_no_tier_mutation(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
        caplog,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        company = await _mk_company(db_session, "WebhookPaymentFailed")
        company.subscription_tier = "standard"
        company.stripe_customer_id = "cus_fail"
        company.stripe_subscription_id = "sub_fail"
        await db_session.commit()

        raw_body = b'{"id":"evt_payment_failed","type":"invoice.payment_failed"}'
        fake_event = _fake_event(
            "evt_payment_failed",
            "invoice.payment_failed",
            data_object={"id": "in_fail", "customer": "cus_fail"},
        )

        caplog.set_level(logging.WARNING)
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
        assert response.json() == {"status": "recorded", "event_type": "invoice.payment_failed"}
        assert "invoice.payment_failed" in caplog.text

        await db_session.refresh(company)
        assert company.subscription_tier == "standard"
        assert company.stripe_subscription_id == "sub_fail"
        assert company.stripe_customer_id == "cus_fail"

        rows = await db_session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == "evt_payment_failed")
        )
        assert rows.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_duplicate_subscription_deleted_short_circuits_before_dispatch(
        self,
        client,
        db_session: AsyncSession,
        monkeypatch,
    ):
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
        db_session.add(
            StripeWebhookEvent(event_id="evt_dup_sub_deleted", event_type="customer.subscription.deleted")
        )
        await db_session.commit()

        raw_body = b'{"id":"evt_dup_sub_deleted","type":"customer.subscription.deleted"}'
        fake_event = _fake_event(
            "evt_dup_sub_deleted",
            "customer.subscription.deleted",
            data_object={"id": "sub_dup_deleted", "customer": "cus_dup_deleted"},
        )

        downgrade_mock = AsyncMock()
        with patch(
            "app.routers.webhooks.stripe.stripe.Webhook.construct_event",
            return_value=fake_event,
        ), patch(
            "app.routers.webhooks.stripe.downgrade_company_to_free",
            downgrade_mock,
        ):
            response = await client.post(
                "/api/webhooks/stripe",
                content=raw_body,
                headers={"Stripe-Signature": "t=1,v1=test"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "duplicate_ignored"}
        downgrade_mock.assert_not_called()