from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Company, User
from app.services.billing_service import (
    CreateSubscriptionStatus,
    PricingSummary,
    calculate_monthly_pricing,
    create_standard_subscription,
    count_company_billable_workers,
    _get_company_for_update,
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


def _set_billing_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stripe_secret_key: str,
    stripe_price_per_seat_monthly_id: str,
) -> None:
    monkeypatch.setattr(
        "app.services.billing_service.settings",
        SimpleNamespace(
            STRIPE_SECRET_KEY=stripe_secret_key,
            STRIPE_PRICE_PER_SEAT_MONTHLY_ID=stripe_price_per_seat_monthly_id,
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
