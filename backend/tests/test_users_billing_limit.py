import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_current_admin_user
from app.models import Company, User
from app.services.auth_service import AuthService


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
async def subscribed_company(db_session: AsyncSession) -> Company:
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        name=f"Subscribed Company {suffix}",
        slug=f"subscribed-company-{suffix}",
        email=f"subscribed-{suffix}@example.com",
        subscription_tier="standard",
        stripe_subscription_id=f"sub_{suffix}",
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
async def company_admin_user(db_session: AsyncSession, free_company: Company) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"company-admin-{suffix}@example.com",
        name="Company Admin",
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
async def subscribed_company_admin_user(db_session: AsyncSession, subscribed_company: Company) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"subscribed-admin-{suffix}@example.com",
        name="Subscribed Company Admin",
        password_hash=AuthService.hash_password("adminpassword123"),
        role="company_admin",
        is_active=True,
        company_id=subscribed_company.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def unlimited_company_admin_user(db_session: AsyncSession, unlimited_company: Company) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"unlimited-admin-{suffix}@example.com",
        name="Unlimited Company Admin",
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


async def _add_users(
    db_session: AsyncSession,
    *,
    company_id: int,
    count: int,
    is_active: bool = True,
) -> None:
    for _ in range(count):
        suffix = uuid.uuid4().hex[:8]
        db_session.add(
            User(
                email=f"worker-{suffix}@example.com",
                name=f"Worker {suffix}",
                password_hash=AuthService.hash_password("workerpassword123"),
                role="regular_user",
                is_active=is_active,
                company_id=company_id,
            )
        )
    await db_session.flush()


@pytest.mark.asyncio
async def test_create_user_free_company_at_limit_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    company_admin_user: User,
    free_company: Company,
):
    new_email = f"blocked-{uuid.uuid4().hex[:8]}@example.com"

    await _add_users(db_session, company_id=free_company.id, count=2)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: company_admin_user
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Blocked User",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 402, response.text
    assert "free limit of 3 workers" in response.json()["detail"]

    result = await db_session.execute(select(User).where(User.company_id == free_company.id))
    assert len(result.scalars().all()) == 3

    result = await db_session.execute(select(User).where(User.email == new_email))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_create_user_free_company_below_limit_allows_third(
    client: AsyncClient,
    db_session: AsyncSession,
    company_admin_user: User,
    free_company: Company,
):
    await _add_users(db_session, company_id=free_company.id, count=1)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: company_admin_user
    new_email = f"allowed-{uuid.uuid4().hex[:8]}@example.com"
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Allowed Third User",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 201, response.text
    result = await db_session.execute(select(User).where(User.email == new_email))
    created_user = result.scalar_one_or_none()
    assert created_user is not None
    assert created_user.company_id == free_company.id


@pytest.mark.asyncio
async def test_create_user_subscribed_company_allows_over_limit(
    client: AsyncClient,
    db_session: AsyncSession,
    subscribed_company_admin_user: User,
    subscribed_company: Company,
    monkeypatch: pytest.MonkeyPatch,
):
    await _add_users(db_session, company_id=subscribed_company.id, count=5)
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.billing_service.settings",
        SimpleNamespace(
            STRIPE_SECRET_KEY="sk_test_abc",
            STRIPE_PRICE_PER_SEAT_MONTHLY_ID="price_standard",
        ),
    )
    retrieve_mock = MagicMock(
        return_value=SimpleNamespace(items=SimpleNamespace(data=[SimpleNamespace(id="si_subscribed")]))
    )
    modify_mock = MagicMock()
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.retrieve", retrieve_mock)
    monkeypatch.setattr("app.services.billing_service.stripe.Subscription.modify", modify_mock)

    app.dependency_overrides[get_current_admin_user] = lambda: subscribed_company_admin_user
    new_email = f"subscribed-{uuid.uuid4().hex[:8]}@example.com"
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Subscribed User",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 201, response.text
    result = await db_session.execute(select(User).where(User.email == new_email))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_create_user_unlimited_company_allows_any_count(
    client: AsyncClient,
    db_session: AsyncSession,
    unlimited_company_admin_user: User,
    unlimited_company: Company,
):
    await _add_users(db_session, company_id=unlimited_company.id, count=12)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: unlimited_company_admin_user
    new_email = f"unlimited-{uuid.uuid4().hex[:8]}@example.com"
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Unlimited User",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 201, response.text
    result = await db_session.execute(select(User).where(User.email == new_email))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_create_user_super_admin_skips_seat_guard(
    client: AsyncClient,
    db_session: AsyncSession,
    platform_super_admin_user: User,
    free_company: Company,
):
    await _add_users(db_session, company_id=free_company.id, count=3)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: platform_super_admin_user
    new_email = f"platform-{uuid.uuid4().hex[:8]}@example.com"
    try:
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/users",
                json={
                    "email": new_email,
                    "password": "ValidPass123!",
                    "name": "Platform User",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 201, response.text
    result = await db_session.execute(select(User).where(User.email == new_email))
    created_user = result.scalar_one_or_none()
    assert created_user is not None
    assert created_user.company_id is None