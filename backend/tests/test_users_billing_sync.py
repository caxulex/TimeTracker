import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user
from app.main import app
from app.models import Company, User
from app.services.auth_service import AuthService
from app.services.billing_service import count_company_billable_workers


def _set_billing_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stripe_secret_key: str = "sk_test_abc",
    stripe_price_per_seat_monthly_id: str = "price_standard",
) -> None:
    monkeypatch.setattr(
        "app.services.billing_service.settings",
        SimpleNamespace(
            STRIPE_SECRET_KEY=stripe_secret_key,
            STRIPE_PRICE_PER_SEAT_MONTHLY_ID=stripe_price_per_seat_monthly_id,
        ),
    )


@pytest_asyncio.fixture
async def standard_company(db_session: AsyncSession) -> Company:
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        name=f"Standard Company {suffix}",
        slug=f"standard-company-{suffix}",
        email=f"standard-{suffix}@example.com",
        subscription_tier="standard",
    )
    db_session.add(company)
    await db_session.flush()
    await db_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def standard_company_with_subscription(db_session: AsyncSession) -> Company:
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        name=f"Standard Subscribed Company {suffix}",
        slug=f"standard-subscribed-company-{suffix}",
        email=f"standard-subscribed-{suffix}@example.com",
        subscription_tier="standard",
        stripe_subscription_id=f"sub_{suffix}",
        stripe_customer_id=f"cus_{suffix}",
    )
    db_session.add(company)
    await db_session.flush()
    await db_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def free_company(db_session: AsyncSession) -> Company:
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        name=f"Free Company {suffix}",
        slug=f"free-company-{suffix}",
        email=f"free-{suffix}@example.com",
        subscription_tier="free",
    )
    db_session.add(company)
    await db_session.flush()
    await db_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def unlimited_company(db_session: AsyncSession) -> Company:
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        name=f"Unlimited Company {suffix}",
        slug=f"unlimited-company-{suffix}",
        email=f"unlimited-{suffix}@example.com",
        subscription_tier="unlimited",
    )
    db_session.add(company)
    await db_session.flush()
    await db_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def standard_admin_user(db_session: AsyncSession, standard_company: Company) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"standard-admin-{suffix}@example.com",
        name="Standard Admin",
        password_hash=AuthService.hash_password("adminpassword123"),
        role="company_admin",
        is_active=True,
        company_id=standard_company.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def standard_admin_user_with_subscription(
    db_session: AsyncSession,
    standard_company_with_subscription: Company,
) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"standard-sub-admin-{suffix}@example.com",
        name="Standard Subscribed Admin",
        password_hash=AuthService.hash_password("adminpassword123"),
        role="company_admin",
        is_active=True,
        company_id=standard_company_with_subscription.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def free_admin_user(db_session: AsyncSession, free_company: Company) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"free-admin-{suffix}@example.com",
        name="Free Admin",
        password_hash=AuthService.hash_password("adminpassword123"),
        role="company_admin",
        is_active=True,
        company_id=free_company.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def unlimited_admin_user(db_session: AsyncSession, unlimited_company: Company) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"unlimited-admin-{suffix}@example.com",
        name="Unlimited Admin",
        password_hash=AuthService.hash_password("adminpassword123"),
        role="company_admin",
        is_active=True,
        company_id=unlimited_company.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def platform_super_admin_user(db_session: AsyncSession) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"platform-admin-{suffix}@example.com",
        name="Platform Admin",
        password_hash=AuthService.hash_password("adminpassword123"),
        role="super_admin",
        is_active=True,
        company_id=None,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


async def _add_users(db_session: AsyncSession, *, company_id: int, count: int) -> None:
    for _ in range(count):
        suffix = uuid.uuid4().hex[:8]
        db_session.add(
            User(
                email=f"worker-{suffix}@example.com",
                name=f"Worker {suffix}",
                password_hash=AuthService.hash_password("workerpassword123"),
                role="regular_user",
                is_active=True,
                company_id=company_id,
            )
        )
    await db_session.flush()


@pytest.mark.asyncio
async def test_create_user_standard_at_three_sync_create_success(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    _set_billing_settings(monkeypatch)
    await _add_users(db_session, company_id=standard_company.id, count=2)
    await db_session.commit()

    customer_create_mock = MagicMock(return_value=SimpleNamespace(id="cus_created"))
    subscription_create_mock = MagicMock(return_value=SimpleNamespace(id="sub_created", status="active"))
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)

    new_email = f"sync-created-{uuid.uuid4().hex[:8]}@example.com"
    app.dependency_overrides[get_current_admin_user] = lambda: standard_admin_user
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Sync Created User",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 201, response.text
    subscription_create_mock.assert_called_once_with(
        customer="cus_created",
        items=[{"price": "price_standard", "quantity": 1}],
        idempotency_key=f"subscription-create-company-{standard_company.id}",
        api_key="sk_test_abc",
    )

    result = await db_session.execute(select(User).where(User.email == new_email))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_create_user_standard_at_three_sync_retriable_fails_closed_no_user(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    _set_billing_settings(monkeypatch)
    await _add_users(db_session, company_id=standard_company.id, count=2)
    await db_session.commit()

    class DummyStripeError(Exception):
        pass

    monkeypatch.setattr("app.services.billing_service.stripe.error.StripeError", DummyStripeError)
    customer_create_mock = MagicMock(side_effect=DummyStripeError("temporary stripe outage"))
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)

    before_count = await count_company_billable_workers(db_session, standard_company.id)

    new_email = f"sync-fail-{uuid.uuid4().hex[:8]}@example.com"
    app.dependency_overrides[get_current_admin_user] = lambda: standard_admin_user
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Sync Fail User",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "Billing update is temporarily unavailable. Please try again shortly."

    result = await db_session.execute(select(User).where(User.email == new_email))
    assert result.scalar_one_or_none() is None

    after_count = await count_company_billable_workers(db_session, standard_company.id)
    assert after_count == before_count


@pytest.mark.asyncio
async def test_create_user_standard_at_three_sync_requires_payment_action_fails_closed(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    _set_billing_settings(monkeypatch)
    await _add_users(db_session, company_id=standard_company.id, count=2)
    await db_session.commit()

    customer_create_mock = MagicMock(return_value=SimpleNamespace(id="cus_incomplete"))
    subscription_create_mock = MagicMock(return_value=SimpleNamespace(id="sub_incomplete", status="incomplete"))
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)

    new_email = f"sync-payment-required-{uuid.uuid4().hex[:8]}@example.com"
    app.dependency_overrides[get_current_admin_user] = lambda: standard_admin_user
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Sync Payment Required",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 402, response.text
    assert response.json()["detail"] == {
        "reason": "payment_action_required",
        "message": "This subscription needs payment completed before adding more workers.",
    }

    result = await db_session.execute(select(User).where(User.email == new_email))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_create_user_free_range_add_skips_stripe_sync(
    client: AsyncClient,
    db_session: AsyncSession,
    free_company: Company,
    free_admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    await _add_users(db_session, company_id=free_company.id, count=1)
    await db_session.commit()

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    new_email = f"free-range-{uuid.uuid4().hex[:8]}@example.com"
    app.dependency_overrides[get_current_admin_user] = lambda: free_admin_user
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Free Range Add",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 201, response.text
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_user_unlimited_add_skips_stripe_sync(
    client: AsyncClient,
    db_session: AsyncSession,
    unlimited_company: Company,
    unlimited_admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    await _add_users(db_session, company_id=unlimited_company.id, count=9)
    await db_session.commit()

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    new_email = f"unlimited-range-{uuid.uuid4().hex[:8]}@example.com"
    app.dependency_overrides[get_current_admin_user] = lambda: unlimited_admin_user
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Unlimited Add",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 201, response.text
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_user_super_admin_skips_stripe_sync(
    client: AsyncClient,
    db_session: AsyncSession,
    platform_super_admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    new_email = f"platform-no-sync-{uuid.uuid4().hex[:8]}@example.com"
    app.dependency_overrides[get_current_admin_user] = lambda: platform_super_admin_user
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Platform Add",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 201, response.text
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_user_standard_over_limit_sync_update_target_three(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company_with_subscription: Company,
    standard_admin_user_with_subscription: User,
    monkeypatch: pytest.MonkeyPatch,
):
    _set_billing_settings(monkeypatch)
    await _add_users(db_session, company_id=standard_company_with_subscription.id, count=4)
    await db_session.commit()

    retrieve_mock = MagicMock(return_value=SimpleNamespace(items=SimpleNamespace(data=[SimpleNamespace(id="si_target")])) )
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    new_email = f"sync-updated-{uuid.uuid4().hex[:8]}@example.com"
    app.dependency_overrides[get_current_admin_user] = lambda: standard_admin_user_with_subscription
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Sync Updated User",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 201, response.text
    modify_mock.assert_called_once_with(
        standard_company_with_subscription.stripe_subscription_id,
        items=[{"id": "si_target", "quantity": 3}],
        proration_behavior="create_prorations",
        idempotency_key=f"subscription-sync-company-{standard_company_with_subscription.id}-qty-3",
        api_key="sk_test_abc",
    )

    result = await db_session.execute(select(User).where(User.email == new_email))
    assert result.scalar_one_or_none() is not None


async def _get_first_regular_user(db_session: AsyncSession, company_id: int) -> User:
    result = await db_session.execute(
        select(User)
        .where(User.company_id == company_id, User.role == "regular_user")
        .order_by(User.id.asc())
    )
    user = result.scalars().first()
    assert user is not None
    return user


@pytest.mark.asyncio
async def test_permanent_delete_standard_company_with_subscription_syncs_quantity_down_and_deletes_user(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company_with_subscription: Company,
    standard_admin_user_with_subscription: User,
    monkeypatch: pytest.MonkeyPatch,
):
    _set_billing_settings(monkeypatch)
    await _add_users(db_session, company_id=standard_company_with_subscription.id, count=4)
    await db_session.commit()

    worker = await _get_first_regular_user(db_session, standard_company_with_subscription.id)

    retrieve_mock = MagicMock(
        return_value=SimpleNamespace(items=SimpleNamespace(data=[SimpleNamespace(id="si_delete_target")]))
    )
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: standard_admin_user_with_subscription
    try:
        response = await client.delete(f"/api/users/{worker.id}/permanent")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    modify_mock.assert_called_once_with(
        standard_company_with_subscription.stripe_subscription_id,
        items=[{"id": "si_delete_target", "quantity": 1}],
        proration_behavior="create_prorations",
        idempotency_key=f"subscription-sync-company-{standard_company_with_subscription.id}-qty-1",
        api_key="sk_test_abc",
    )

    result = await db_session.execute(select(User).where(User.id == worker.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_permanent_delete_standard_company_with_subscription_fail_open_on_stripe_error(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company_with_subscription: Company,
    standard_admin_user_with_subscription: User,
    monkeypatch: pytest.MonkeyPatch,
):
    _set_billing_settings(monkeypatch)
    await _add_users(db_session, company_id=standard_company_with_subscription.id, count=4)
    await db_session.commit()

    worker = await _get_first_regular_user(db_session, standard_company_with_subscription.id)

    class DummyStripeError(Exception):
        pass

    monkeypatch.setattr("app.services.billing_service.stripe.error.StripeError", DummyStripeError)
    retrieve_mock = MagicMock(
        return_value=SimpleNamespace(items=SimpleNamespace(data=[SimpleNamespace(id="si_delete_fail")]))
    )
    modify_mock = MagicMock(side_effect=DummyStripeError("temporary stripe outage"))
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: standard_admin_user_with_subscription
    try:
        response = await client.delete(f"/api/users/{worker.id}/permanent")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    modify_mock.assert_called_once()

    result = await db_session.execute(select(User).where(User.id == worker.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_deactivate_user_does_not_touch_billing(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company_with_subscription: Company,
    standard_admin_user_with_subscription: User,
    monkeypatch: pytest.MonkeyPatch,
):
    await _add_users(db_session, company_id=standard_company_with_subscription.id, count=2)
    await db_session.commit()

    worker = await _get_first_regular_user(db_session, standard_company_with_subscription.id)

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: standard_admin_user_with_subscription
    try:
        response = await client.delete(f"/api/users/{worker.id}")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()

    result = await db_session.execute(select(User).where(User.id == worker.id))
    deactivated_user = result.scalar_one_or_none()
    assert deactivated_user is not None
    assert deactivated_user.is_active is False


@pytest.mark.asyncio
async def test_permanent_delete_free_company_skips_billing_sync(
    client: AsyncClient,
    db_session: AsyncSession,
    free_company: Company,
    free_admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    await _add_users(db_session, company_id=free_company.id, count=2)
    await db_session.commit()

    worker = await _get_first_regular_user(db_session, free_company.id)

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: free_admin_user
    try:
        response = await client.delete(f"/api/users/{worker.id}/permanent")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()

    result = await db_session.execute(select(User).where(User.id == worker.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_permanent_delete_unlimited_company_skips_billing_sync(
    client: AsyncClient,
    db_session: AsyncSession,
    unlimited_company: Company,
    unlimited_admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    await _add_users(db_session, company_id=unlimited_company.id, count=2)
    await db_session.commit()

    worker = await _get_first_regular_user(db_session, unlimited_company.id)

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: unlimited_admin_user
    try:
        response = await client.delete(f"/api/users/{worker.id}/permanent")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()

    result = await db_session.execute(select(User).where(User.id == worker.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_permanent_delete_standard_company_drops_to_zero_noop_zero_with_subscription(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company_with_subscription: Company,
    standard_admin_user_with_subscription: User,
    monkeypatch: pytest.MonkeyPatch,
):
    _set_billing_settings(monkeypatch)
    await _add_users(db_session, company_id=standard_company_with_subscription.id, count=3)
    await db_session.commit()

    worker = await _get_first_regular_user(db_session, standard_company_with_subscription.id)

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: standard_admin_user_with_subscription
    try:
        response = await client.delete(f"/api/users/{worker.id}/permanent")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()

    result = await db_session.execute(select(User).where(User.id == worker.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_permanent_delete_standard_company_without_subscription_skips_billing_sync(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    await _add_users(db_session, company_id=standard_company.id, count=2)
    await db_session.commit()

    worker = await _get_first_regular_user(db_session, standard_company.id)

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: standard_admin_user
    try:
        response = await client.delete(f"/api/users/{worker.id}/permanent")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()

    result = await db_session.execute(select(User).where(User.id == worker.id))
    assert result.scalar_one_or_none() is None
