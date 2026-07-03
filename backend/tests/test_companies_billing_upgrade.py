import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_current_user
from app.main import app
from app.models import Company, User
from app.services.auth_service import AuthService


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
async def standard_company_admin(
    db_session: AsyncSession,
    standard_company: Company,
) -> User:
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
async def test_upgrade_free_company_below_limit_flips_to_standard_without_stripe(
    client: AsyncClient,
    db_session: AsyncSession,
    free_company: Company,
    free_company_admin: User,
):
    await _add_workers(db_session, company_id=free_company.id, count=1)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: free_company_admin
    try:
        response = await client.post("/api/companies/my-company/billing/upgrade")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == "upgraded"
    assert payload["subscription_tier"] == "standard"
    assert payload["stripe_subscription_id"] is None
    assert payload["requires_payment_action"] is False
    assert payload["message"] == (
        "you can now add workers beyond the free limit; $5/month per worker "
        "beyond 3, billed when you add them"
    )

    result = await db_session.execute(select(Company).where(Company.id == free_company.id))
    company = result.scalar_one()
    assert company.subscription_tier == "standard"
    assert company.stripe_subscription_id is None


@pytest.mark.asyncio
async def test_upgrade_e2e_loop_unblocks_third_add_after_flip(
    client: AsyncClient,
    db_session: AsyncSession,
    free_company: Company,
    free_company_admin: User,
):
    await _add_workers(db_session, company_id=free_company.id, count=2)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: free_company_admin
    try:
        blocked_email = f"blocked-{uuid.uuid4().hex[:8]}@example.com"
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            blocked_response = await client.post(
                "/api/users",
                json={
                    "email": blocked_email,
                    "password": "ValidPass123!",
                    "name": "Blocked User",
                    "role": "regular_user",
                },
            )

        assert blocked_response.status_code == 402, blocked_response.text

        upgrade_response = await client.post("/api/companies/my-company/billing/upgrade")
        assert upgrade_response.status_code == 200, upgrade_response.text
        assert upgrade_response.json()["subscription_tier"] == "standard"
        assert upgrade_response.json()["stripe_subscription_id"] is None

        allowed_email = f"allowed-{uuid.uuid4().hex[:8]}@example.com"
        with patch("app.routers.users.email_service.send_welcome_email", new_callable=AsyncMock):
            create_response = await client.post(
                "/api/users",
                json={
                    "email": allowed_email,
                    "password": "ValidPass123!",
                    "name": "Allowed User",
                    "role": "regular_user",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert create_response.status_code == 201, create_response.text

    result = await db_session.execute(select(Company).where(Company.id == free_company.id))
    company = result.scalar_one()
    assert company.subscription_tier == "standard"
    assert company.stripe_subscription_id is None

    result = await db_session.execute(
        select(User).where(User.email.in_([blocked_email, allowed_email]))
    )
    created_emails = {user.email for user in result.scalars().all()}
    assert blocked_email not in created_emails
    assert allowed_email in created_emails


@pytest.mark.asyncio
async def test_upgrade_already_standard_is_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_company_admin: User,
):
    await _add_workers(db_session, company_id=standard_company.id, count=1)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: standard_company_admin
    try:
        response = await client.post("/api/companies/my-company/billing/upgrade")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == "already_upgraded"
    assert payload["subscription_tier"] == "standard"
    assert payload["message"] == "already on a paid tier"

    result = await db_session.execute(select(Company).where(Company.id == standard_company.id))
    company = result.scalar_one()
    assert company.subscription_tier == "standard"
    assert company.stripe_subscription_id is None


@pytest.mark.asyncio
async def test_upgrade_free_company_over_limit_returns_unexpected_state_without_mutating(
    client: AsyncClient,
    db_session: AsyncSession,
    free_company: Company,
    free_company_admin: User,
):
    await _add_workers(db_session, company_id=free_company.id, count=4)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: free_company_admin
    try:
        response = await client.post("/api/companies/my-company/billing/upgrade")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 500, response.text
    payload = response.json()
    assert payload["success"] is False
    assert payload["status"] == "unexpected_state"
    assert payload["subscription_tier"] == "free"
    assert payload["stripe_subscription_id"] is None
    assert payload["message"] == (
        "Company has more workers than the free tier allows without an active "
        "subscription; seat-based billing is required (not yet available)."
    )

    result = await db_session.execute(select(Company).where(Company.id == free_company.id))
    company = result.scalar_one()
    assert company.subscription_tier == "free"
    assert company.stripe_subscription_id is None


@pytest.mark.asyncio
async def test_upgrade_requires_admin_and_company_membership(
    client: AsyncClient,
    db_session: AsyncSession,
    free_company: Company,
    test_user: User,
    companyless_super_admin: User,
):
    await _add_workers(db_session, company_id=free_company.id, count=1)
    await db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: test_user
    try:
        forbidden_response = await client.post("/api/companies/my-company/billing/upgrade")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert forbidden_response.status_code == 403, forbidden_response.text
    assert forbidden_response.json()["detail"] == "Not enough permissions"

    app.dependency_overrides[get_current_admin_user] = lambda: companyless_super_admin
    try:
        missing_company_response = await client.post(
            "/api/companies/my-company/billing/upgrade"
        )
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert missing_company_response.status_code == 404, missing_company_response.text
    assert missing_company_response.json()["detail"] == "User is not associated with a company"