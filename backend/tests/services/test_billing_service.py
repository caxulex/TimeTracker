from __future__ import annotations

import uuid
import stripe
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Company, User
from app.services.billing_service import (
    CreateSubscriptionStatus,
    SyncResult,
    SyncStatus,
    PricingSummary,
    SwitchStatus,
    downgrade_company_to_free,
    _sync_subscription_to_target,
    can_company_add_worker,
    calculate_monthly_pricing,
    create_standard_subscription,
    count_company_billable_workers,
    reconcile_company_subscription,
    reconcile_all_standard_subscriptions,
    switch_company_to_unlimited,
    sync_company_subscription_quantity,
    _get_company_for_update,
    _resolve_or_create_stripe_customer,
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


async def _mk_user(
    db_session: AsyncSession,
    *,
    email_prefix: str,
    company_id: int | None,
    is_active: bool,
) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"{email_prefix}-{suffix}@example.com",
        password_hash="hashed",
        name=f"{email_prefix}-{suffix}",
        role="regular_user",
        is_active=is_active,
        company_id=company_id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


async def _mk_workers(
    db_session: AsyncSession,
    *,
    company_id: int,
    count: int,
) -> None:
    for idx in range(count):
        await _mk_user(
            db_session,
            email_prefix=f"worker-{idx}",
            company_id=company_id,
            is_active=True,
        )


def _stripe_customer(customer_id: str) -> SimpleNamespace:
    return SimpleNamespace(id=customer_id)


def _stripe_subscription(subscription_id: str, status: str) -> SimpleNamespace:
    return SimpleNamespace(id=subscription_id, status=status)


def _stripe_subscription_with_item(
    subscription_id: str,
    status: str,
    item_id: str,
) -> stripe.stripe_object.StripeObject:
    return stripe.util.convert_to_stripe_object(
        {
            "id": subscription_id,
            "object": "subscription",
            "status": status,
            "items": {
                "object": "list",
                "data": [
                    {
                        "id": item_id,
                        "object": "subscription_item",
                        "quantity": 1,
                    }
                ],
            },
        },
        api_key="sk_test_abc",
    )


def _stripe_subscription_object_with_item(
    *,
    subscription_id: str,
    status: str,
    item_id: str,
) -> stripe.stripe_object.StripeObject:
    return stripe.util.convert_to_stripe_object(
        {
            "id": subscription_id,
            "object": "subscription",
            "status": status,
            "items": {
                "object": "list",
                "data": [
                    {
                        "id": item_id,
                        "object": "subscription_item",
                        "quantity": 1,
                    }
                ],
            },
        },
        api_key="sk_test_abc",
    )


def _set_billing_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stripe_secret_key: str,
    stripe_price_per_seat_monthly_id: str,
    stripe_price_unlimited_monthly_id: str = "",
    stripe_checkout_success_url: str = "https://timetracker.shaemarcus.com/billing",
    stripe_checkout_cancel_url: str = "https://timetracker.shaemarcus.com/billing",
) -> None:
    monkeypatch.setattr(
        "app.services.billing_service.settings",
        SimpleNamespace(
            STRIPE_SECRET_KEY=stripe_secret_key,
            STRIPE_PRICE_PER_SEAT_MONTHLY_ID=stripe_price_per_seat_monthly_id,
            STRIPE_PRICE_UNLIMITED_MONTHLY_ID=stripe_price_unlimited_monthly_id,
            STRIPE_CHECKOUT_SUCCESS_URL=stripe_checkout_success_url,
            STRIPE_CHECKOUT_CANCEL_URL=stripe_checkout_cancel_url,
        ),
    )


@pytest.mark.asyncio
async def test_count_company_billable_workers_three_users(db_session: AsyncSession):
    company = await _mk_company(db_session, "Seat3")
    await _mk_user(db_session, email_prefix="u1", company_id=company.id, is_active=True)
    await _mk_user(db_session, email_prefix="u2", company_id=company.id, is_active=True)
    await _mk_user(db_session, email_prefix="u3", company_id=company.id, is_active=True)

    count = await count_company_billable_workers(db_session, company.id)

    assert count == 3


@pytest.mark.asyncio
async def test_count_company_billable_workers_includes_inactive_users(db_session: AsyncSession):
    company = await _mk_company(db_session, "SeatMix")
    await _mk_user(db_session, email_prefix="active1", company_id=company.id, is_active=True)
    await _mk_user(db_session, email_prefix="active2", company_id=company.id, is_active=True)
    await _mk_user(db_session, email_prefix="inactive1", company_id=company.id, is_active=False)
    await _mk_user(db_session, email_prefix="inactive2", company_id=company.id, is_active=False)

    count = await count_company_billable_workers(db_session, company.id)

    assert count == 4


@pytest.mark.asyncio
async def test_count_company_billable_workers_excludes_platform_users(db_session: AsyncSession):
    company = await _mk_company(db_session, "SeatPlatform")
    await _mk_user(db_session, email_prefix="attached", company_id=company.id, is_active=True)
    await _mk_user(db_session, email_prefix="platform", company_id=None, is_active=True)

    count = await count_company_billable_workers(db_session, company.id)

    assert count == 1


@pytest.mark.asyncio
async def test_count_company_billable_workers_is_tenant_isolated(db_session: AsyncSession):
    company_a = await _mk_company(db_session, "TenantA")
    company_b = await _mk_company(db_session, "TenantB")

    await _mk_user(db_session, email_prefix="a1", company_id=company_a.id, is_active=True)
    await _mk_user(db_session, email_prefix="a2", company_id=company_a.id, is_active=False)
    await _mk_user(db_session, email_prefix="b1", company_id=company_b.id, is_active=True)
    await _mk_user(db_session, email_prefix="b2", company_id=company_b.id, is_active=True)
    await _mk_user(db_session, email_prefix="b3", company_id=company_b.id, is_active=False)

    count_a = await count_company_billable_workers(db_session, company_a.id)
    count_b = await count_company_billable_workers(db_session, company_b.id)

    assert count_a == 2
    assert count_b == 3


@pytest.mark.asyncio
async def test_can_company_add_worker_free_with_two_workers_allowed(db_session: AsyncSession):
    company = await _mk_company(db_session, "GuardFreeTwo")
    await _mk_workers(db_session, company_id=company.id, count=2)

    decision = await can_company_add_worker(db_session, company.id)

    assert decision.allowed is True
    assert decision.reason_code == "allowed"
    assert decision.worker_count == 2
    assert decision.free_limit == 3
    assert decision.subscription_tier == "free"
    assert decision.has_subscription is False


@pytest.mark.asyncio
async def test_can_company_add_worker_free_with_three_workers_blocked(db_session: AsyncSession):
    company = await _mk_company(db_session, "GuardFreeThree")
    await _mk_workers(db_session, company_id=company.id, count=3)

    decision = await can_company_add_worker(db_session, company.id)

    assert decision.allowed is False
    assert decision.reason_code == "blocked_free_limit"
    assert decision.worker_count == 3
    assert "Deactivated users still count" in decision.message
    assert "DELETED to reclaim a slot" in decision.message
    assert "upgrade to a paid plan" in decision.message


@pytest.mark.asyncio
async def test_can_company_add_worker_inactive_users_still_block(db_session: AsyncSession):
    company = await _mk_company(db_session, "GuardInactiveCounts")
    await _mk_user(db_session, email_prefix="active-a", company_id=company.id, is_active=True)
    await _mk_user(db_session, email_prefix="active-b", company_id=company.id, is_active=True)
    await _mk_user(db_session, email_prefix="inactive", company_id=company.id, is_active=False)

    decision = await can_company_add_worker(db_session, company.id)

    assert decision.allowed is False
    assert decision.reason_code == "blocked_free_limit"
    assert decision.worker_count == 3


@pytest.mark.asyncio
async def test_can_company_add_worker_subscribed_company_allowed(db_session: AsyncSession):
    company = await _mk_company(db_session, "GuardSubscribed")
    company.subscription_tier = "standard"
    company.stripe_subscription_id = "sub_guard_standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=5)

    decision = await can_company_add_worker(db_session, company.id)

    assert decision.allowed is True
    assert decision.reason_code == "allowed"
    assert decision.worker_count == 5
    assert decision.subscription_tier == "standard"
    assert decision.has_subscription is True


@pytest.mark.asyncio
async def test_can_company_add_worker_unlimited_tier_allowed(db_session: AsyncSession):
    company = await _mk_company(db_session, "GuardUnlimited")
    company.subscription_tier = "unlimited"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=25)

    decision = await can_company_add_worker(db_session, company.id)

    assert decision.allowed is True
    assert decision.reason_code == "allowed"
    assert decision.worker_count == 25
    assert decision.subscription_tier == "unlimited"


@pytest.mark.asyncio
async def test_can_company_add_worker_company_not_found(db_session: AsyncSession):
    decision = await can_company_add_worker(db_session, 999999)

    assert decision.allowed is False
    assert decision.reason_code == "company_not_found"
    assert decision.worker_count == 0
    assert decision.free_limit == 3
    assert decision.has_subscription is False


@pytest.mark.asyncio
async def test_can_company_add_worker_free_boundary_third_allowed_fourth_blocked(
    db_session: AsyncSession,
):
    company = await _mk_company(db_session, "GuardBoundary")
    await _mk_workers(db_session, company_id=company.id, count=2)

    third_decision = await can_company_add_worker(db_session, company.id)
    assert third_decision.allowed is True
    assert third_decision.reason_code == "allowed"
    assert third_decision.worker_count == 2

    await _mk_user(db_session, email_prefix="third", company_id=company.id, is_active=True)

    fourth_decision = await can_company_add_worker(db_session, company.id)
    assert fourth_decision.allowed is False
    assert fourth_decision.reason_code == "blocked_free_limit"
    assert fourth_decision.worker_count == 3


def _assert_pricing(
    result: PricingSummary,
    *,
    expected_over_free: int,
    expected_cost_dollars: int,
    expected_recommend: bool,
) -> None:
    assert result.seats_over_free == expected_over_free
    assert result.per_seat_monthly_cost_dollars == expected_cost_dollars
    assert result.should_recommend_unlimited is expected_recommend


@pytest.mark.parametrize("workers", [0, 1, 2, 3])
def test_calculate_monthly_pricing_free_range(workers: int):
    result = calculate_monthly_pricing(workers)
    _assert_pricing(
        result,
        expected_over_free=0,
        expected_cost_dollars=0,
        expected_recommend=False,
    )


def test_calculate_monthly_pricing_four_workers():
    result = calculate_monthly_pricing(4)
    _assert_pricing(
        result,
        expected_over_free=1,
        expected_cost_dollars=5,
        expected_recommend=False,
    )


def test_calculate_monthly_pricing_thirteen_workers_break_even_not_recommended():
    result = calculate_monthly_pricing(13)
    _assert_pricing(
        result,
        expected_over_free=10,
        expected_cost_dollars=50,
        expected_recommend=False,
    )


def test_calculate_monthly_pricing_fourteen_workers_recommended():
    result = calculate_monthly_pricing(14)
    _assert_pricing(
        result,
        expected_over_free=11,
        expected_cost_dollars=55,
        expected_recommend=True,
    )


def test_calculate_monthly_pricing_large_number():
    result = calculate_monthly_pricing(100)
    _assert_pricing(
        result,
        expected_over_free=97,
        expected_cost_dollars=485,
        expected_recommend=True,
    )


@pytest.mark.asyncio
async def test_create_standard_subscription_happy_path(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    company = await _mk_company(db_session, "StripeHappy")
    await _mk_workers(db_session, company_id=company.id, count=6)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create = MagicMock(return_value=_stripe_customer("cus_123"))
    subscription_create = MagicMock(return_value=_stripe_subscription("sub_123", "active"))
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create)

    result = await create_standard_subscription(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == CreateSubscriptionStatus.CREATED
    assert result.seats_over_free == 3
    assert result.stripe_customer_id == "cus_123"
    assert result.stripe_subscription_id == "sub_123"
    assert company.stripe_customer_id == "cus_123"
    assert company.stripe_subscription_id == "sub_123"
    assert company.subscription_tier == "standard"

    customer_create.assert_called_once()
    subscription_create.assert_called_once()
    sub_kwargs = subscription_create.call_args.kwargs
    assert sub_kwargs["items"] == [{"price": "price_standard", "quantity": 3}]
    assert sub_kwargs["idempotency_key"] == f"subscription-create-company-{company.id}"


@pytest.mark.asyncio
async def test_create_standard_subscription_empty_default_pm_keeps_customer_create_kwargs_unchanged(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "StripeDefaultPmEmpty")
    await _mk_workers(db_session, company_id=company.id, count=4)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create = MagicMock(return_value=_stripe_customer("cus_default_pm_empty"))
    subscription_create = MagicMock(return_value=_stripe_subscription("sub_default_pm_empty", "active"))
    payment_method_attach = MagicMock()
    customer_modify = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create)
    monkeypatch.setattr("app.services.billing_service.stripe.PaymentMethod.attach", payment_method_attach)
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.modify", customer_modify)

    result = await create_standard_subscription(db_session, company.id)

    assert result.status == CreateSubscriptionStatus.CREATED
    customer_create.assert_called_once()
    create_kwargs = customer_create.call_args.kwargs
    assert "payment_method" not in create_kwargs
    assert "invoice_settings" not in create_kwargs
    payment_method_attach.assert_not_called()
    customer_modify.assert_not_called()


@pytest.mark.asyncio
async def test_create_standard_subscription_zero_seats_noop(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    company = await _mk_company(db_session, "StripeNoSeats")
    await _mk_workers(db_session, company_id=company.id, count=3)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create = MagicMock()
    subscription_create = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create)

    result = await create_standard_subscription(db_session, company.id)

    assert result.status == CreateSubscriptionStatus.NOOP_ZERO_SEATS
    customer_create.assert_not_called()
    subscription_create.assert_not_called()


@pytest.mark.asyncio
async def test_create_standard_subscription_already_subscribed_transaction_a_noop(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "StripeAlreadyA")
    company.stripe_customer_id = "cus_existing"
    company.stripe_subscription_id = "sub_existing"
    await db_session.commit()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create = MagicMock()
    subscription_create = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create)

    result = await create_standard_subscription(db_session, company.id)

    assert result.status == CreateSubscriptionStatus.NOOP_ALREADY_SUBSCRIBED
    assert result.stripe_subscription_id == "sub_existing"
    customer_create.assert_not_called()
    subscription_create.assert_not_called()


@pytest.mark.asyncio
async def test_create_standard_subscription_overlap_recheck_transaction_b_noop_no_overwrite(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "StripeOverlap")
    await _mk_workers(db_session, company_id=company.id, count=6)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create = MagicMock(return_value=_stripe_customer("cus_abc"))
    subscription_create = MagicMock(return_value=_stripe_subscription("sub_created", "active"))
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create)

    original_get_company_for_update = _get_company_for_update
    call_count = 0

    async def fake_get_company_for_update(db: AsyncSession, company_id: int) -> Company | None:
        nonlocal call_count
        call_count += 1
        company_row = await original_get_company_for_update(db, company_id)
        if call_count == 2 and company_row is not None:
            company_row.stripe_subscription_id = "sub_written_by_other_worker"
            company_row.stripe_customer_id = "cus_written_by_other_worker"
        return company_row

    monkeypatch.setattr("app.services.billing_service._get_company_for_update", fake_get_company_for_update)

    result = await create_standard_subscription(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == CreateSubscriptionStatus.NOOP_ALREADY_SUBSCRIBED
    assert result.stripe_subscription_id == "sub_written_by_other_worker"
    assert company.stripe_subscription_id == "sub_written_by_other_worker"
    assert company.stripe_customer_id == "cus_written_by_other_worker"
    customer_create.assert_called_once()
    subscription_create.assert_called_once()


@pytest.mark.asyncio
async def test_create_standard_subscription_missing_config_before_stripe_calls(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "StripeMissingConfig")
    await _mk_workers(db_session, company_id=company.id, count=6)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="",
        stripe_price_per_seat_monthly_id="",
    )

    customer_create = MagicMock()
    subscription_create = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create)

    result = await create_standard_subscription(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == CreateSubscriptionStatus.CONFIG_ERROR
    assert company.stripe_customer_id is None
    assert company.stripe_subscription_id is None
    customer_create.assert_not_called()
    subscription_create.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("subscription_status", ["incomplete", "past_due"])
async def test_create_standard_subscription_requires_payment_action_persists_ids_keeps_free_tier(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    subscription_status: str,
):
    company = await _mk_company(db_session, "StripeNeedsAction")
    await _mk_workers(db_session, company_id=company.id, count=6)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    monkeypatch.setattr(
        "app.services.billing_service.stripe.Customer.create",
        MagicMock(return_value=_stripe_customer("cus_pending")),
    )
    monkeypatch.setattr(
        "app.services.billing_service.stripe.Subscription.create",
        MagicMock(return_value=_stripe_subscription("sub_pending", subscription_status)),
    )

    result = await create_standard_subscription(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == CreateSubscriptionStatus.REQUIRES_PAYMENT_ACTION
    assert result.stripe_subscription_status == subscription_status
    assert company.stripe_customer_id == "cus_pending"
    assert company.stripe_subscription_id == "sub_pending"
    assert company.subscription_tier == "free"


@pytest.mark.asyncio
async def test_create_standard_subscription_stripe_timeout_returns_retriable_no_db_mutation(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "StripeTimeout")
    await _mk_workers(db_session, company_id=company.id, count=6)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    monkeypatch.setattr(
        "app.services.billing_service.stripe.Customer.create",
        MagicMock(side_effect=TimeoutError("stripe timeout")),
    )
    subscription_create = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create)

    result = await create_standard_subscription(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == CreateSubscriptionStatus.RETRIABLE_ERROR
    assert company.stripe_customer_id is None
    assert company.stripe_subscription_id is None
    assert company.subscription_tier == "free"
    subscription_create.assert_not_called()


@pytest.mark.asyncio
async def test_create_standard_subscription_retry_uses_same_idempotency_keys(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "StripeRetryKeys")
    await _mk_workers(db_session, company_id=company.id, count=6)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create = MagicMock(return_value=_stripe_customer("cus_retry"))
    subscription_create = MagicMock(return_value=_stripe_subscription("sub_retry", "active"))
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create)

    first = await create_standard_subscription(db_session, company.id)
    assert first.status == CreateSubscriptionStatus.CREATED

    company.stripe_customer_id = None
    company.stripe_subscription_id = None
    company.subscription_tier = "free"
    await db_session.commit()

    second = await create_standard_subscription(db_session, company.id)
    assert second.status == CreateSubscriptionStatus.CREATED

    assert customer_create.call_count == 2
    assert subscription_create.call_count == 2
    customer_keys = [call.kwargs["idempotency_key"] for call in customer_create.call_args_list]
    subscription_keys = [call.kwargs["idempotency_key"] for call in subscription_create.call_args_list]
    assert customer_keys == [
        f"customer-create-company-{company.id}",
        f"customer-create-company-{company.id}",
    ]
    assert subscription_keys == [
        f"subscription-create-company-{company.id}",
        f"subscription-create-company-{company.id}",
    ]


@pytest.mark.asyncio
async def test_company_row_lock_blocks_second_session_then_proceeds(db_session: AsyncSession):
    company = await _mk_company(db_session, "LockCompany")
    await db_session.commit()

    session_factory = async_sessionmaker(
        db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with session_factory() as session_one, session_factory() as session_two:
        async with session_one.begin():
            locked_company = await _get_company_for_update(session_one, company.id)
            assert locked_company is not None

            await session_two.begin()
            await session_two.execute(text("SET LOCAL lock_timeout = '250ms'"))

            with pytest.raises(Exception) as exc_info:
                await _get_company_for_update(session_two, company.id)

            error_text = str(exc_info.value).lower()
            assert (
                "lock timeout" in error_text
                or "locknotavailable" in error_text
                or "candados" in error_text
            )
            await session_two.rollback()

        async with session_two.begin():
            acquired_after_release = await _get_company_for_update(session_two, company.id)
            assert acquired_after_release is not None
            assert acquired_after_release.id == company.id


@pytest.mark.asyncio
async def test_sync_company_subscription_quantity_standard_target_one_no_subscription_created(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SyncCreate")
    company.subscription_tier = "standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=4)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create_mock = MagicMock(return_value=_stripe_customer("cus_created_sync"))
    subscription_create_mock = MagicMock(return_value=_stripe_subscription("sub_created_sync", "active"))
    # C1: the create path now introspects the customer's payment method. Mock a
    # chargeable card present so this test exercises the direct-create path it asserts.
    customer_retrieve_mock = MagicMock(
        return_value=stripe.util.convert_to_stripe_object(
            {"id": "cus_created_sync", "invoice_settings": {"default_payment_method": {"id": "pm_x", "type": "card"}}},
            api_key="sk_test_abc",
        )
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.retrieve", customer_retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)

    result = await sync_company_subscription_quantity(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SyncStatus.CREATED
    assert result.target_quantity == 1
    assert result.stripe_subscription_id == "sub_created_sync"
    subscription_create_mock.assert_called_once_with(
        customer="cus_created_sync",
        items=[{"price": "price_standard", "quantity": 1}],
        idempotency_key=f"subscription-create-company-{company.id}",
        api_key="sk_test_abc",
    )
    assert company.stripe_subscription_id == "sub_created_sync"


@pytest.mark.asyncio
async def test_sync_subscription_create_branch_no_pm_returns_checkout_required(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SyncCheckoutNoPM")
    company.subscription_tier = "standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=4)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
        stripe_checkout_success_url="https://example.test/billing?checkout=success",
        stripe_checkout_cancel_url="https://example.test/billing?checkout=cancel",
    )

    customer_create_mock = MagicMock(return_value=_stripe_customer("cus_checkout"))
    customer_retrieve_mock = MagicMock(
        return_value=stripe.util.convert_to_stripe_object(
            {
                "id": "cus_checkout",
                "invoice_settings": {"default_payment_method": None},
            },
            api_key="sk_test_abc",
        )
    )
    payment_method_list_mock = MagicMock(return_value={"data": []})
    checkout_create_mock = MagicMock(
        return_value=stripe.util.convert_to_stripe_object(
            {"id": "cs_test_1", "url": "https://checkout.stripe.test/session/cs_test_1"},
            api_key="sk_test_abc",
        )
    )
    subscription_create_mock = MagicMock()

    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.retrieve", customer_retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.PaymentMethod.list", payment_method_list_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.checkout.Session.create", checkout_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)

    result = await sync_company_subscription_quantity(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SyncStatus.CHECKOUT_REQUIRED
    assert result.target_quantity == 1
    assert result.checkout_url == "https://checkout.stripe.test/session/cs_test_1"
    subscription_create_mock.assert_not_called()
    checkout_create_mock.assert_called_once_with(
        mode="subscription",
        customer="cus_checkout",
        line_items=[{"price": "price_standard", "quantity": 1}],
        metadata={"company_id": str(company.id)},
        subscription_data={"metadata": {"company_id": str(company.id)}},
        success_url="https://example.test/billing?checkout=success",
        cancel_url="https://example.test/billing?checkout=cancel",
        idempotency_key=f"checkout-session-company-{company.id}",
        api_key="sk_test_abc",
    )
    assert company.stripe_subscription_id is None


@pytest.mark.asyncio
async def test_sync_subscription_create_branch_pm_lookup_failure_routes_to_checkout(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    # Safety: if PM introspection fails (transient Stripe error), fail TOWARD
    # Checkout, never toward Subscription.create. Creating a subscription for a
    # possibly-cardless customer produces a stuck "incomplete" subscription.
    company = await _mk_company(db_session, "SyncCheckoutPMLookupFail")
    company.subscription_tier = "standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=4)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
        stripe_checkout_success_url="https://example.test/billing?checkout=success",
        stripe_checkout_cancel_url="https://example.test/billing?checkout=cancel",
    )

    customer_create_mock = MagicMock(return_value=_stripe_customer("cus_lookupfail"))
    customer_retrieve_mock = MagicMock(
        side_effect=stripe.error.APIConnectionError("network blip")
    )
    checkout_create_mock = MagicMock(
        return_value=stripe.util.convert_to_stripe_object(
            {"id": "cs_test_fail", "url": "https://checkout.stripe.test/session/cs_test_fail"},
            api_key="sk_test_abc",
        )
    )
    # Give a valid return so that IF the code wrongly calls Subscription.create
    # (the fail-open regression), the test fails CLEANLY on the assertions below
    # rather than on a downstream DB error from persisting a MagicMock id.
    subscription_create_mock = MagicMock(
        return_value=_stripe_subscription("sub_should_not_be_used", "active")
    )

    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.retrieve", customer_retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.checkout.Session.create", checkout_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)

    result = await sync_company_subscription_quantity(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SyncStatus.CHECKOUT_REQUIRED
    assert result.checkout_url == "https://checkout.stripe.test/session/cs_test_fail"
    subscription_create_mock.assert_not_called()
    assert company.stripe_subscription_id is None


@pytest.mark.asyncio
async def test_sync_subscription_create_branch_pm_present_uses_direct_subscription_create(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SyncCheckoutPMPresent")
    company.subscription_tier = "standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=4)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create_mock = MagicMock(return_value=_stripe_customer("cus_pm_present"))
    customer_retrieve_mock = MagicMock(
        return_value=stripe.util.convert_to_stripe_object(
            {
                "id": "cus_pm_present",
                "invoice_settings": {
                    "default_payment_method": {
                        "id": "pm_card_present",
                        "type": "card",
                    }
                },
            },
            api_key="sk_test_abc",
        )
    )
    payment_method_list_mock = MagicMock(return_value={"data": []})
    checkout_create_mock = MagicMock()
    subscription_create_mock = MagicMock(return_value=_stripe_subscription("sub_pm_present", "active"))

    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.retrieve", customer_retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.PaymentMethod.list", payment_method_list_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.checkout.Session.create", checkout_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)

    result = await sync_company_subscription_quantity(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SyncStatus.CREATED
    assert result.target_quantity == 1
    assert result.stripe_subscription_id == "sub_pm_present"
    checkout_create_mock.assert_not_called()
    subscription_create_mock.assert_called_once_with(
        customer="cus_pm_present",
        items=[{"price": "price_standard", "quantity": 1}],
        idempotency_key=f"subscription-create-company-{company.id}",
        api_key="sk_test_abc",
    )
    assert company.stripe_subscription_id == "sub_pm_present"


@pytest.mark.asyncio
async def test_sync_company_subscription_quantity_standard_target_two_has_subscription_updated(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SyncUpdate")
    company.subscription_tier = "standard"
    company.stripe_subscription_id = "sub_sync_update"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=5)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_sync_update",
            status="active",
            item_id="si_sync",
        )
    )
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await sync_company_subscription_quantity(db_session, company.id)

    assert result.status == SyncStatus.UPDATED
    assert result.target_quantity == 2
    assert result.stripe_subscription_id == "sub_sync_update"
    retrieve_mock.assert_called_once_with(
        "sub_sync_update",
        expand=["items"],
        api_key="sk_test_abc",
    )
    modify_mock.assert_called_once_with(
        "sub_sync_update",
        items=[{"id": "si_sync", "quantity": 2}],
        proration_behavior="create_prorations",
        idempotency_key=f"subscription-sync-company-{company.id}-qty-2",
        api_key="sk_test_abc",
    )


@pytest.mark.asyncio
async def test_sync_subscription_to_target_update_uses_dict_access_for_real_stripe_object_items(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "HelperUpdateStripeObject")
    company.subscription_tier = "standard"
    company.stripe_subscription_id = "sub_helper_update_obj"
    await db_session.flush()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    subscription_obj = _stripe_subscription_object_with_item(
        subscription_id="sub_helper_update_obj",
        status="active",
        item_id="si_test",
    )
    retrieve_mock = MagicMock(return_value=subscription_obj)
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await _sync_subscription_to_target(db_session, company.id, 2)

    assert result.status == SyncStatus.UPDATED
    retrieve_mock.assert_called_once_with(
        "sub_helper_update_obj",
        expand=["items"],
        api_key="sk_test_abc",
    )
    modify_mock.assert_called_once_with(
        "sub_helper_update_obj",
        items=[{"id": "si_test", "quantity": 2}],
        proration_behavior="create_prorations",
        idempotency_key=f"subscription-sync-company-{company.id}-qty-2",
        api_key="sk_test_abc",
    )


@pytest.mark.asyncio
async def test_sync_company_subscription_quantity_standard_target_zero_with_subscription_noop_warning(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    company = await _mk_company(db_session, "SyncZeroWithSub")
    company.subscription_tier = "standard"
    company.stripe_subscription_id = "sub_zero"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=3)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    with caplog.at_level("WARNING"):
        result = await sync_company_subscription_quantity(db_session, company.id)

    assert result.status == SyncStatus.NOOP_ZERO_WITH_SUBSCRIPTION
    assert result.target_quantity == 0
    assert result.stripe_subscription_id == "sub_zero"
    assert "target quantity is zero" in caplog.text
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_sync_company_subscription_quantity_standard_target_zero_no_subscription_noop(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SyncZeroNoSub")
    company.subscription_tier = "standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=3)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    result = await sync_company_subscription_quantity(db_session, company.id)

    assert result.status == SyncStatus.NOOP_NOTHING_TO_DO
    assert result.target_quantity == 0
    assert result.stripe_subscription_id is None


@pytest.mark.asyncio
async def test_sync_company_subscription_quantity_free_tier_noop_not_standard(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SyncFree")
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=7)

    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await sync_company_subscription_quantity(db_session, company.id)

    assert result.status == SyncStatus.NOOP_NOT_STANDARD
    assert result.target_quantity == 4
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_sync_company_subscription_quantity_unlimited_tier_noop_not_standard(
    db_session: AsyncSession,
):
    company = await _mk_company(db_session, "SyncUnlimited")
    company.subscription_tier = "unlimited"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=15)

    result = await sync_company_subscription_quantity(db_session, company.id)

    assert result.status == SyncStatus.NOOP_NOT_STANDARD
    assert result.target_quantity == 12


@pytest.mark.asyncio
async def test_sync_company_subscription_quantity_company_not_found(db_session: AsyncSession):
    result = await sync_company_subscription_quantity(db_session, 999999)

    assert result.status == SyncStatus.COMPANY_NOT_FOUND
    assert result.target_quantity == 0


@pytest.mark.asyncio
async def test_sync_company_subscription_quantity_missing_config_before_stripe_calls(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SyncMissingConfig")
    company.subscription_tier = "standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=4)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="",
        stripe_price_per_seat_monthly_id="",
    )

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await sync_company_subscription_quantity(db_session, company.id)

    assert result.status == SyncStatus.CONFIG_ERROR
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_sync_company_subscription_quantity_stripe_error_on_modify_returns_retriable_no_db_mutation(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SyncStripeModifyError")
    company.subscription_tier = "standard"
    company.stripe_customer_id = "cus_keep"
    company.stripe_subscription_id = "sub_keep"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=6)
    await db_session.commit()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_keep",
            status="active",
            item_id="si_keep",
        )
    )
    modify_mock = MagicMock(side_effect=stripe.error.StripeError("modify failed"))
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    before_state = (
        company.subscription_tier,
        company.stripe_customer_id,
        company.stripe_subscription_id,
    )

    result = await sync_company_subscription_quantity(db_session, company.id)
    await db_session.refresh(company)

    after_state = (
        company.subscription_tier,
        company.stripe_customer_id,
        company.stripe_subscription_id,
    )

    assert result.status == SyncStatus.RETRIABLE_ERROR
    assert before_state == after_state


@pytest.mark.asyncio
async def test_sync_company_subscription_quantity_idempotency_key_stability_same_target(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SyncStableKey")
    company.subscription_tier = "standard"
    company.stripe_subscription_id = "sub_stable"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=5)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_stable",
            status="active",
            item_id="si_stable",
        )
    )
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    first = await sync_company_subscription_quantity(db_session, company.id)
    second = await sync_company_subscription_quantity(db_session, company.id)

    assert first.status == SyncStatus.UPDATED
    assert second.status == SyncStatus.UPDATED
    assert modify_mock.call_count == 2
    keys = [call.kwargs["idempotency_key"] for call in modify_mock.call_args_list]
    assert keys == [
        f"subscription-sync-company-{company.id}-qty-2",
        f"subscription-sync-company-{company.id}-qty-2",
    ]


@pytest.mark.asyncio
async def test_reconcile_all_standard_subscriptions_three_standard_companies(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company_created = await _mk_company(db_session, "ReconCreate")
    company_created.subscription_tier = "standard"

    company_updated = await _mk_company(db_session, "ReconUpdate")
    company_updated.subscription_tier = "standard"
    company_updated.stripe_subscription_id = "sub_recon_update"

    company_noop = await _mk_company(db_session, "ReconNoop")
    company_noop.subscription_tier = "standard"

    await db_session.flush()

    await _mk_workers(db_session, company_id=company_created.id, count=4)
    await _mk_workers(db_session, company_id=company_updated.id, count=5)
    await _mk_workers(db_session, company_id=company_noop.id, count=3)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create_mock = MagicMock(return_value=_stripe_customer("cus_recon_created"))
    subscription_create_mock = MagicMock(return_value=_stripe_subscription("sub_recon_created", "active"))
    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_recon_update",
            status="active",
            item_id="si_recon",
        )
    )
    modify_mock = MagicMock()
    # C1: created company's create path introspects the PM. Mock a chargeable card
    # so it takes direct-create (update company uses Subscription.retrieve, unaffected).
    customer_retrieve_mock = MagicMock(
        return_value=stripe.util.convert_to_stripe_object(
            {"id": "cus_recon_created", "invoice_settings": {"default_payment_method": {"id": "pm_x", "type": "card"}}},
            api_key="sk_test_abc",
        )
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.retrieve", customer_retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    results = await reconcile_all_standard_subscriptions(db_session)

    assert len(results) == 3
    by_company: dict[int, SyncResult] = {result.company_id: result for result in results}

    assert by_company[company_created.id].status == SyncStatus.CREATED
    assert by_company[company_created.id].target_quantity == 1
    assert by_company[company_updated.id].status == SyncStatus.UPDATED
    assert by_company[company_updated.id].target_quantity == 2
    assert by_company[company_noop.id].status == SyncStatus.NOOP_NOTHING_TO_DO
    assert by_company[company_noop.id].target_quantity == 0


@pytest.mark.asyncio
async def test_reconcile_all_standard_subscriptions_only_standard_tier_processed(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    standard_company = await _mk_company(db_session, "ReconOnlyStandard")
    standard_company.subscription_tier = "standard"
    standard_company.stripe_subscription_id = "sub_only_standard"

    free_company = await _mk_company(db_session, "ReconFree")

    unlimited_company = await _mk_company(db_session, "ReconUnlimited")
    unlimited_company.subscription_tier = "unlimited"

    await db_session.flush()
    await _mk_workers(db_session, company_id=standard_company.id, count=4)
    await _mk_workers(db_session, company_id=free_company.id, count=6)
    await _mk_workers(db_session, company_id=unlimited_company.id, count=10)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_only_standard",
            status="active",
            item_id="si_only",
        )
    )
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    results = await reconcile_all_standard_subscriptions(db_session)

    assert len(results) == 1
    assert results[0].company_id == standard_company.id
    assert results[0].status == SyncStatus.UPDATED
    retrieve_mock.assert_called_once()
    modify_mock.assert_called_once()


@pytest.mark.asyncio
async def test_reconcile_company_subscription_known_standard_delegates_to_sync_path(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "ReconSingleDelegates")
    company.subscription_tier = "standard"
    await db_session.flush()

    expected = SyncResult(
        status=SyncStatus.UPDATED,
        company_id=company.id,
        target_quantity=2,
        stripe_subscription_id="sub_single_delegate",
    )

    sync_mock = AsyncMock(return_value=expected)
    monkeypatch.setattr("app.services.billing_service.sync_company_subscription_quantity", sync_mock)

    result = await reconcile_company_subscription(db_session, company.id)

    assert result == expected
    sync_mock.assert_awaited_once_with(db_session, company.id)


@pytest.mark.asyncio
async def test_reconcile_company_subscription_company_not_found_returns_not_found(
    db_session: AsyncSession,
):
    result = await reconcile_company_subscription(db_session, 999999)

    assert result.status == SyncStatus.COMPANY_NOT_FOUND
    assert result.company_id == 999999
    assert result.target_quantity == 0


@pytest.mark.asyncio
async def test_reconcile_company_subscription_uses_same_sync_call_as_reconcile_all(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "ReconSingleSamePath")
    company.subscription_tier = "standard"
    await db_session.flush()

    seen_company_ids: list[int] = []

    async def _fake_sync(_db: AsyncSession, company_id: int) -> SyncResult:
        seen_company_ids.append(company_id)
        return SyncResult(
            status=SyncStatus.NOOP_NOTHING_TO_DO,
            company_id=company_id,
            target_quantity=0,
        )

    monkeypatch.setattr("app.services.billing_service.sync_company_subscription_quantity", _fake_sync)

    single = await reconcile_company_subscription(db_session, company.id)
    all_results = await reconcile_all_standard_subscriptions(db_session)

    assert single.status == SyncStatus.NOOP_NOTHING_TO_DO
    assert [result.company_id for result in all_results] == [company.id]
    assert seen_company_ids == [company.id, company.id]


@pytest.mark.asyncio
async def test_downgrade_company_to_free_standard_clears_subscription_keeps_customer(
    db_session: AsyncSession,
):
    company = await _mk_company(db_session, "DowngradeStandard")
    company.subscription_tier = "standard"
    company.stripe_customer_id = "cus_keep"
    company.stripe_subscription_id = "sub_clear"
    await db_session.flush()

    result = await downgrade_company_to_free(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SwitchStatus.DOWNGRADED_TO_FREE
    assert company.subscription_tier == "free"
    assert company.stripe_subscription_id is None
    assert company.stripe_customer_id == "cus_keep"


@pytest.mark.asyncio
async def test_downgrade_company_to_free_already_free_noop_no_mutation(
    db_session: AsyncSession,
):
    company = await _mk_company(db_session, "DowngradeAlreadyFree")
    company.subscription_tier = "free"
    company.stripe_customer_id = "cus_free"
    company.stripe_subscription_id = None
    await db_session.flush()

    result = await downgrade_company_to_free(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SwitchStatus.NOOP_ALREADY_FREE
    assert company.subscription_tier == "free"
    assert company.stripe_subscription_id is None
    assert company.stripe_customer_id == "cus_free"


@pytest.mark.asyncio
async def test_downgrade_company_to_free_not_found(
    db_session: AsyncSession,
):
    result = await downgrade_company_to_free(db_session, 999999)

    assert result.status == SwitchStatus.COMPANY_NOT_FOUND
    assert result.company_id == 999999


@pytest.mark.asyncio
async def test_downgrade_company_to_free_unlimited_downgrades_and_clears_subscription(
    db_session: AsyncSession,
):
    company = await _mk_company(db_session, "DowngradeUnlimited")
    company.subscription_tier = "unlimited"
    company.stripe_customer_id = "cus_unlimited"
    company.stripe_subscription_id = "sub_unlimited"
    await db_session.flush()

    result = await downgrade_company_to_free(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SwitchStatus.DOWNGRADED_TO_FREE
    assert company.subscription_tier == "free"
    assert company.stripe_subscription_id is None
    assert company.stripe_customer_id == "cus_unlimited"


@pytest.mark.asyncio
async def test_sync_subscription_to_target_explicit_one_standard_no_subscription_created(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "HelperCreate")
    company.subscription_tier = "standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=4)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create_mock = MagicMock(return_value=_stripe_customer("cus_helper_created"))
    subscription_create_mock = MagicMock(return_value=_stripe_subscription("sub_helper_created", "active"))
    customer_retrieve_mock = MagicMock(
        return_value=stripe.util.convert_to_stripe_object(
            {"id": "cus_helper_created", "invoice_settings": {"default_payment_method": {"id": "pm_x", "type": "card"}}},
            api_key="sk_test_abc",
        )
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.retrieve", customer_retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)

    result = await _sync_subscription_to_target(db_session, company.id, 1)
    await db_session.refresh(company)

    assert result.status == SyncStatus.CREATED
    assert result.target_quantity == 1
    subscription_create_mock.assert_called_once_with(
        customer="cus_helper_created",
        items=[{"price": "price_standard", "quantity": 1}],
        idempotency_key=f"subscription-create-company-{company.id}",
        api_key="sk_test_abc",
    )
    assert company.stripe_subscription_id == "sub_helper_created"


@pytest.mark.asyncio
async def test_sync_subscription_to_target_explicit_two_standard_with_subscription_updated(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "HelperUpdate")
    company.subscription_tier = "standard"
    company.stripe_subscription_id = "sub_helper_update"
    await db_session.flush()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_helper_update",
            status="active",
            item_id="si_helper",
        )
    )
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await _sync_subscription_to_target(db_session, company.id, 2)

    assert result.status == SyncStatus.UPDATED
    assert result.target_quantity == 2
    modify_mock.assert_called_once_with(
        "sub_helper_update",
        items=[{"id": "si_helper", "quantity": 2}],
        proration_behavior="create_prorations",
        idempotency_key=f"subscription-sync-company-{company.id}-qty-2",
        api_key="sk_test_abc",
    )


@pytest.mark.asyncio
async def test_sync_subscription_to_target_uses_explicit_target_not_live_count(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "HelperDecoupled")
    company.subscription_tier = "standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=3)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    customer_create_mock = MagicMock(return_value=_stripe_customer("cus_helper_decoupled"))
    subscription_create_mock = MagicMock(return_value=_stripe_subscription("sub_helper_decoupled", "active"))
    customer_retrieve_mock = MagicMock(
        return_value=stripe.util.convert_to_stripe_object(
            {"id": "cus_helper_decoupled", "invoice_settings": {"default_payment_method": {"id": "pm_x", "type": "card"}}},
            api_key="sk_test_abc",
        )
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.retrieve", customer_retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)

    result = await _sync_subscription_to_target(db_session, company.id, 1)
    await db_session.refresh(company)

    assert result.status == SyncStatus.CREATED
    assert result.target_quantity == 1
    subscription_create_mock.assert_called_once_with(
        customer="cus_helper_decoupled",
        items=[{"price": "price_standard", "quantity": 1}],
        idempotency_key=f"subscription-create-company-{company.id}",
        api_key="sk_test_abc",
    )
    assert company.stripe_subscription_id == "sub_helper_decoupled"


@pytest.mark.asyncio
async def test_sync_subscription_to_target_zero_with_subscription_noop(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "HelperZeroWithSub")
    company.subscription_tier = "standard"
    company.stripe_subscription_id = "sub_helper_zero"
    await db_session.flush()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    result = await _sync_subscription_to_target(db_session, company.id, 0)

    assert result.status == SyncStatus.NOOP_ZERO_WITH_SUBSCRIPTION
    assert result.target_quantity == 0


@pytest.mark.asyncio
async def test_sync_subscription_to_target_non_standard_tier_noop(
    db_session: AsyncSession,
):
    company = await _mk_company(db_session, "HelperFreeNoop")
    await db_session.flush()

    result = await _sync_subscription_to_target(db_session, company.id, 2)

    assert result.status == SyncStatus.NOOP_NOT_STANDARD
    assert result.target_quantity == 2


@pytest.mark.asyncio
async def test_sync_subscription_to_target_stripe_error_returns_retriable(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "HelperStripeError")
    company.subscription_tier = "standard"
    company.stripe_subscription_id = "sub_helper_error"
    await db_session.flush()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_helper_error",
            status="active",
            item_id="si_error",
        )
    )
    modify_mock = MagicMock(side_effect=stripe.error.StripeError("modify failed"))
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await _sync_subscription_to_target(db_session, company.id, 2)
    await db_session.refresh(company)

    assert result.status == SyncStatus.RETRIABLE_ERROR
    assert company.stripe_subscription_id == "sub_helper_error"


@pytest.mark.asyncio
async def test_sync_subscription_to_target_missing_config_returns_config_error(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "HelperConfig")
    company.subscription_tier = "standard"
    company.stripe_subscription_id = "sub_helper_config"
    await db_session.flush()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="",
        stripe_price_per_seat_monthly_id="",
    )

    result = await _sync_subscription_to_target(db_session, company.id, 2)

    assert result.status == SyncStatus.CONFIG_ERROR


@pytest.mark.asyncio
async def test_switch_company_to_unlimited_standard_with_subscription_swaps_price_and_flips_tier(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SwitchStandard")
    company.subscription_tier = "standard"
    company.stripe_customer_id = "cus_standard"
    company.stripe_subscription_id = "sub_standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=6)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
        stripe_price_unlimited_monthly_id="price_unlimited",
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_standard",
            status="active",
            item_id="si_standard",
        )
    )
    modify_mock = MagicMock(
        return_value=_stripe_subscription_with_item("sub_standard", "active", "si_standard")
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await switch_company_to_unlimited(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SwitchStatus.SWITCHED
    assert result.stripe_subscription_id == "sub_standard"
    assert company.subscription_tier == "unlimited"
    assert company.stripe_customer_id == "cus_standard"
    assert company.stripe_subscription_id == "sub_standard"
    retrieve_mock.assert_called_once_with(
        "sub_standard",
        expand=["items"],
        api_key="sk_test_abc",
    )
    modify_mock.assert_called_once_with(
        "sub_standard",
        items=[
            {
                "id": "si_standard",
                "price": "price_unlimited",
                "quantity": 1,
            }
        ],
        proration_behavior="create_prorations",
        idempotency_key=f"subscription-switch-unlimited-company-{company.id}",
        api_key="sk_test_abc",
    )


def test_stripe_subscription_items_attr_collision_regression_guard_real_stripe_object():
    subscription_obj = _stripe_subscription_object_with_item(
        subscription_id="sub_guard",
        status="active",
        item_id="si_guard",
    )

    attr_items = getattr(subscription_obj, "items", None)
    old_attr_path_items = getattr(attr_items, "data", [])
    dict_path_items = subscription_obj["items"]["data"]

    assert old_attr_path_items == []
    assert dict_path_items[0]["id"] == "si_guard"


@pytest.mark.asyncio
async def test_switch_company_to_unlimited_standard_with_subscription_modify_error_returns_retriable_and_stays_standard(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SwitchModifyError")
    company.subscription_tier = "standard"
    company.stripe_customer_id = "cus_standard"
    company.stripe_subscription_id = "sub_standard"
    await db_session.flush()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
        stripe_price_unlimited_monthly_id="price_unlimited",
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_with_item("sub_standard", "active", "si_standard")
    )
    modify_mock = MagicMock(side_effect=stripe.error.StripeError("modify failed"))
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    before_state = (
        company.subscription_tier,
        company.stripe_customer_id,
        company.stripe_subscription_id,
    )

    result = await switch_company_to_unlimited(db_session, company.id)
    await db_session.refresh(company)

    after_state = (
        company.subscription_tier,
        company.stripe_customer_id,
        company.stripe_subscription_id,
    )

    assert result.status == SwitchStatus.RETRIABLE_ERROR
    assert before_state == after_state
    retrieve_mock.assert_called_once()
    modify_mock.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("subscription_status", ["incomplete", "past_due"])
async def test_switch_company_to_unlimited_standard_with_subscription_requires_payment_action(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    subscription_status: str,
):
    company = await _mk_company(db_session, "SwitchNeedsAction")
    company.subscription_tier = "standard"
    company.stripe_customer_id = "cus_standard"
    company.stripe_subscription_id = "sub_standard"
    await db_session.flush()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
        stripe_price_unlimited_monthly_id="price_unlimited",
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_with_item("sub_standard", subscription_status, "si_standard")
    )
    modify_mock = MagicMock(
        return_value=_stripe_subscription_with_item("sub_standard", subscription_status, "si_standard")
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await switch_company_to_unlimited(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SwitchStatus.REQUIRES_PAYMENT_ACTION
    assert result.stripe_subscription_id == "sub_standard"
    assert company.subscription_tier == "standard"
    assert company.stripe_customer_id == "cus_standard"
    assert company.stripe_subscription_id == "sub_standard"


@pytest.mark.asyncio
async def test_switch_company_to_unlimited_standard_without_subscription_is_comped(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SwitchCompedStandard")
    company.subscription_tier = "standard"
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=2)

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await switch_company_to_unlimited(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SwitchStatus.SWITCHED_COMPED
    assert company.subscription_tier == "unlimited"
    assert company.stripe_subscription_id is None
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_switch_company_to_unlimited_free_with_workers_creates_unlimited_subscription(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SwitchFreeCreate")
    await db_session.flush()
    await _mk_workers(db_session, company_id=company.id, count=4)

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
        stripe_price_unlimited_monthly_id="price_unlimited",
    )

    customer_create_mock = MagicMock(return_value=_stripe_customer("cus_unlimited"))
    subscription_create_mock = MagicMock(
        return_value=_stripe_subscription("sub_unlimited", "active")
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)

    result = await switch_company_to_unlimited(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SwitchStatus.SWITCHED
    assert result.stripe_subscription_id == "sub_unlimited"
    assert company.subscription_tier == "unlimited"
    assert company.stripe_customer_id == "cus_unlimited"
    assert company.stripe_subscription_id == "sub_unlimited"
    customer_create_mock.assert_called_once_with(
        name=company.name,
        email=company.email,
        metadata={"company_id": str(company.id)},
        idempotency_key=f"customer-create-company-{company.id}",
        api_key="sk_test_abc",
    )
    subscription_create_mock.assert_called_once_with(
        customer="cus_unlimited",
        items=[{"price": "price_unlimited", "quantity": 1}],
        idempotency_key=f"subscription-create-company-{company.id}",
        api_key="sk_test_abc",
    )


@pytest.mark.asyncio
async def test_switch_company_to_unlimited_free_with_zero_workers_is_comped(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SwitchFreeZero")
    await db_session.flush()

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await switch_company_to_unlimited(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SwitchStatus.SWITCHED_COMPED
    assert company.subscription_tier == "unlimited"
    assert company.stripe_customer_id is None
    assert company.stripe_subscription_id is None
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_switch_company_to_unlimited_already_unlimited_is_noop(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SwitchAlreadyUnlimited")
    company.subscription_tier = "unlimited"
    company.stripe_customer_id = "cus_unlimited"
    company.stripe_subscription_id = "sub_unlimited"
    await db_session.flush()

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await switch_company_to_unlimited(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SwitchStatus.NOOP_ALREADY_UNLIMITED
    assert company.subscription_tier == "unlimited"
    assert company.stripe_customer_id == "cus_unlimited"
    assert company.stripe_subscription_id == "sub_unlimited"
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_switch_company_to_unlimited_company_not_found(db_session: AsyncSession):
    result = await switch_company_to_unlimited(db_session, 999999)

    assert result.status == SwitchStatus.COMPANY_NOT_FOUND
    assert result.company_id == 999999


@pytest.mark.asyncio
async def test_switch_company_to_unlimited_missing_config_before_stripe_calls(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SwitchMissingConfig")
    company.subscription_tier = "standard"
    company.stripe_customer_id = "cus_standard"
    company.stripe_subscription_id = "sub_standard"
    await db_session.flush()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="",
        stripe_price_per_seat_monthly_id="",
        stripe_price_unlimited_monthly_id="",
    )

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    result = await switch_company_to_unlimited(db_session, company.id)
    await db_session.refresh(company)

    assert result.status == SwitchStatus.CONFIG_ERROR
    assert company.subscription_tier == "standard"
    assert company.stripe_customer_id == "cus_standard"
    assert company.stripe_subscription_id == "sub_standard"
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_switch_company_to_unlimited_idempotency_key_stability_same_target(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    company = await _mk_company(db_session, "SwitchStableKey")
    company.subscription_tier = "standard"
    company.stripe_customer_id = "cus_stable"
    company.stripe_subscription_id = "sub_stable"
    await db_session.flush()

    _set_billing_settings(
        monkeypatch,
        stripe_secret_key="sk_test_abc",
        stripe_price_per_seat_monthly_id="price_standard",
        stripe_price_unlimited_monthly_id="price_unlimited",
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_with_item("sub_stable", "active", "si_stable")
    )
    modify_mock = MagicMock(
        return_value=_stripe_subscription_with_item("sub_stable", "active", "si_stable")
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    first = await switch_company_to_unlimited(db_session, company.id)
    assert first.status == SwitchStatus.SWITCHED

    company.subscription_tier = "standard"
    await db_session.commit()

    second = await switch_company_to_unlimited(db_session, company.id)
    assert second.status == SwitchStatus.SWITCHED

    assert modify_mock.call_count == 2
    keys = [call.kwargs["idempotency_key"] for call in modify_mock.call_args_list]
    assert keys == [
        f"subscription-switch-unlimited-company-{company.id}",
        f"subscription-switch-unlimited-company-{company.id}",
    ]
