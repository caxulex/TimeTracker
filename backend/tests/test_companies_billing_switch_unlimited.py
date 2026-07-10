import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
import stripe
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_current_user
from app.main import app
from app.models import Company, User
from app.services.auth_service import AuthService


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


async def _add_workers(
    db_session: AsyncSession,
    *,
    company_id: int,
    count: int,
) -> None:
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
async def standard_company_admin(db_session: AsyncSession, standard_company: Company) -> User:
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
async def free_company_admin(db_session: AsyncSession, free_company: Company) -> User:
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
async def companyless_super_admin(db_session: AsyncSession) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"platform-admin-{suffix}@example.com",
        name="Platform Super Admin",
        password_hash=AuthService.hash_password("adminpassword123"),
        role="super_admin",
        is_active=True,
        company_id=None,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_switch_endpoint_standard_with_subscription_swaps_to_unlimited(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_company_admin: User,
    monkeypatch: pytest.MonkeyPatch,
):
    standard_company.stripe_customer_id = "cus_standard"
    standard_company.stripe_subscription_id = "sub_standard"
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.billing_service.settings",
        SimpleNamespace(
            STRIPE_SECRET_KEY="sk_test_abc",
            STRIPE_PRICE_PER_SEAT_MONTHLY_ID="price_standard",
            STRIPE_PRICE_UNLIMITED_MONTHLY_ID="price_unlimited",
        ),
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_standard",
            status="active",
            item_id="si_standard",
        )
    )
    modify_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_standard",
            status="active",
            item_id="si_standard",
        )
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: standard_company_admin
    try:
        response = await client.post("/api/companies/my-company/billing/switch-to-unlimited")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == "switched"
    assert payload["subscription_tier"] == "unlimited"
    assert payload["stripe_subscription_id"] == "sub_standard"

    modify_mock.assert_called_once_with(
        "sub_standard",
        items=[{"id": "si_standard", "price": "price_unlimited", "quantity": 1}],
        proration_behavior="create_prorations",
        idempotency_key=f"subscription-switch-unlimited-company-{standard_company.id}",
        api_key="sk_test_abc",
    )

    refreshed = await db_session.get(Company, standard_company.id)
    assert refreshed is not None
    assert refreshed.subscription_tier == "unlimited"


@pytest.mark.asyncio
async def test_switch_endpoint_standard_with_subscription_stripe_failure_returns_503(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_company_admin: User,
    monkeypatch: pytest.MonkeyPatch,
):
    standard_company.stripe_customer_id = "cus_standard"
    standard_company.stripe_subscription_id = "sub_standard"
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.billing_service.settings",
        SimpleNamespace(
            STRIPE_SECRET_KEY="sk_test_abc",
            STRIPE_PRICE_PER_SEAT_MONTHLY_ID="price_standard",
            STRIPE_PRICE_UNLIMITED_MONTHLY_ID="price_unlimited",
        ),
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_standard",
            status="active",
            item_id="si_standard",
        )
    )
    modify_mock = MagicMock(side_effect=stripe.error.StripeError("modify failed"))
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: standard_company_admin
    try:
        response = await client.post("/api/companies/my-company/billing/switch-to-unlimited")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 503, response.text

    refreshed = await db_session.get(Company, standard_company.id)
    assert refreshed is not None
    assert refreshed.subscription_tier == "standard"


@pytest.mark.asyncio
async def test_switch_endpoint_standard_with_subscription_requires_payment_action_returns_402(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_company_admin: User,
    monkeypatch: pytest.MonkeyPatch,
):
    standard_company.stripe_customer_id = "cus_standard"
    standard_company.stripe_subscription_id = "sub_standard"
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.billing_service.settings",
        SimpleNamespace(
            STRIPE_SECRET_KEY="sk_test_abc",
            STRIPE_PRICE_PER_SEAT_MONTHLY_ID="price_standard",
            STRIPE_PRICE_UNLIMITED_MONTHLY_ID="price_unlimited",
        ),
    )

    retrieve_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_standard",
            status="incomplete",
            item_id="si_standard",
        )
    )
    modify_mock = MagicMock(
        return_value=_stripe_subscription_object_with_item(
            subscription_id="sub_standard",
            status="incomplete",
            item_id="si_standard",
        )
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: standard_company_admin
    try:
        response = await client.post("/api/companies/my-company/billing/switch-to-unlimited")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 402, response.text
    assert response.json() == {
        "detail": {
            "reason": "payment_action_required",
            "message": "Stripe subscription requires payment action.",
        }
    }

    refreshed = await db_session.get(Company, standard_company.id)
    assert refreshed is not None
    assert refreshed.subscription_tier == "standard"


@pytest.mark.asyncio
async def test_switch_endpoint_standard_without_subscription_is_comped(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_company_admin: User,
    monkeypatch: pytest.MonkeyPatch,
):
    standard_company.stripe_customer_id = "cus_standard"
    standard_company.stripe_subscription_id = None
    await db_session.flush()

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: standard_company_admin
    try:
        response = await client.post("/api/companies/my-company/billing/switch-to-unlimited")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "switched_comped"
    assert payload["subscription_tier"] == "unlimited"
    assert payload["stripe_subscription_id"] is None

    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_switch_endpoint_free_with_workers_creates_unlimited_subscription(
    client: AsyncClient,
    db_session: AsyncSession,
    free_company: Company,
    free_company_admin: User,
    monkeypatch: pytest.MonkeyPatch,
):
    await _add_workers(db_session, company_id=free_company.id, count=4)
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.billing_service.settings",
        SimpleNamespace(
            STRIPE_SECRET_KEY="sk_test_abc",
            STRIPE_PRICE_PER_SEAT_MONTHLY_ID="price_standard",
            STRIPE_PRICE_UNLIMITED_MONTHLY_ID="price_unlimited",
        ),
    )

    customer_create_mock = MagicMock(return_value=SimpleNamespace(id="cus_unlimited"))
    subscription_create_mock = MagicMock(
        return_value=SimpleNamespace(id="sub_unlimited", status="active")
    )
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: free_company_admin
    try:
        response = await client.post("/api/companies/my-company/billing/switch-to-unlimited")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "switched"
    assert payload["subscription_tier"] == "unlimited"
    assert payload["stripe_subscription_id"] == "sub_unlimited"


@pytest.mark.asyncio
async def test_switch_endpoint_already_unlimited_is_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_company_admin: User,
    monkeypatch: pytest.MonkeyPatch,
):
    standard_company.subscription_tier = "unlimited"
    standard_company.stripe_customer_id = "cus_unlimited"
    standard_company.stripe_subscription_id = "sub_unlimited"
    await db_session.flush()

    customer_create_mock = MagicMock()
    subscription_create_mock = MagicMock()
    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Customer.create", customer_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.create", subscription_create_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: standard_company_admin
    try:
        response = await client.post("/api/companies/my-company/billing/switch-to-unlimited")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "already_unlimited"
    assert payload["subscription_tier"] == "unlimited"
    assert payload["stripe_subscription_id"] == "sub_unlimited"

    customer_create_mock.assert_not_called()
    subscription_create_mock.assert_not_called()
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_switch_endpoint_requires_admin(
    client: AsyncClient,
    test_user: User,
):
    app.dependency_overrides[get_current_user] = lambda: test_user
    try:
        response = await client.post("/api/companies/my-company/billing/switch-to-unlimited")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Not enough permissions"


@pytest.mark.asyncio
async def test_switch_endpoint_companyless_super_admin_gets_404(
    client: AsyncClient,
    companyless_super_admin: User,
):
    app.dependency_overrides[get_current_admin_user] = lambda: companyless_super_admin
    try:
        response = await client.post("/api/companies/my-company/billing/switch-to-unlimited")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "User is not associated with a company"


@pytest.mark.asyncio
async def test_switch_endpoint_scoped_to_current_users_company_only(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    suffix_a = uuid.uuid4().hex[:8]
    company_a = Company(
        name=f"Company A {suffix_a}",
        slug=f"company-a-{suffix_a}",
        email=f"company-a-{suffix_a}@example.com",
        subscription_tier="standard",
    )
    db_session.add(company_a)

    suffix_b = uuid.uuid4().hex[:8]
    company_b = Company(
        name=f"Company B {suffix_b}",
        slug=f"company-b-{suffix_b}",
        email=f"company-b-{suffix_b}@example.com",
        subscription_tier="standard",
        stripe_customer_id="cus_b",
        stripe_subscription_id="sub_b",
    )
    db_session.add(company_b)
    await db_session.flush()

    admin = User(
        email=f"admin-a-{uuid.uuid4().hex[:8]}@example.com",
        name="Admin A",
        password_hash=AuthService.hash_password("adminpassword123"),
        role="company_admin",
        is_active=True,
        company_id=company_a.id,
    )
    db_session.add(admin)
    await db_session.commit()

    retrieve_mock = MagicMock()
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: admin
    try:
        response = await client.post("/api/companies/my-company/billing/switch-to-unlimited")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text

    company_a_refreshed = await db_session.get(Company, company_a.id)
    company_b_refreshed = await db_session.get(Company, company_b.id)
    assert company_a_refreshed is not None
    assert company_b_refreshed is not None
    assert company_a_refreshed.subscription_tier == "unlimited"
    assert company_b_refreshed.subscription_tier == "standard"
    assert company_b_refreshed.stripe_subscription_id == "sub_b"
    retrieve_mock.assert_not_called()
    modify_mock.assert_not_called()
