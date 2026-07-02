import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin_user, get_current_user
from app.main import app
from app.models import Company, User
from app.services.auth_service import AuthService
from app.services.billing_service import calculate_monthly_pricing


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
async def unlimited_company_admin(db_session: AsyncSession, unlimited_company: Company) -> User:
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
async def test_billing_status_free_under_limit(
    client: AsyncClient,
    db_session: AsyncSession,
    free_company: Company,
    free_company_admin: User,
):
    # 2 total workers including the admin user.
    await _add_workers(db_session, company_id=free_company.id, count=1)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: free_company_admin
    try:
        response = await client.get("/api/companies/my-company/billing/status")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["worker_count"] == 2
    assert payload["free_limit"] == 3
    assert payload["seats_over_free"] == 0
    assert payload["per_seat_monthly_cost_dollars"] == 0
    assert payload["should_recommend_unlimited"] is False
    assert payload["subscription_tier"] == "free"
    assert payload["has_subscription"] is False
    assert payload["is_at_or_over_free_limit"] is False
    assert payload["would_block_next_add"] is False


@pytest.mark.asyncio
async def test_billing_status_free_at_limit_would_block_next_add(
    client: AsyncClient,
    db_session: AsyncSession,
    free_company: Company,
    free_company_admin: User,
):
    # 3 total workers including the admin user.
    await _add_workers(db_session, company_id=free_company.id, count=2)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: free_company_admin
    try:
        response = await client.get("/api/companies/my-company/billing/status")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["worker_count"] == 3
    assert payload["is_at_or_over_free_limit"] is True
    assert payload["would_block_next_add"] is True


@pytest.mark.asyncio
async def test_billing_status_standard_subscription_over_limit_not_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    standard_company: Company,
    standard_company_admin: User,
):
    # 5 total workers including the admin user.
    await _add_workers(db_session, company_id=standard_company.id, count=4)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: standard_company_admin
    try:
        response = await client.get("/api/companies/my-company/billing/status")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["worker_count"] == 5
    assert payload["subscription_tier"] == "standard"
    assert payload["has_subscription"] is True
    assert payload["would_block_next_add"] is False


@pytest.mark.asyncio
async def test_billing_status_unlimited_never_blocks_next_add(
    client: AsyncClient,
    db_session: AsyncSession,
    unlimited_company: Company,
    unlimited_company_admin: User,
):
    await _add_workers(db_session, company_id=unlimited_company.id, count=11)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: unlimited_company_admin
    try:
        response = await client.get("/api/companies/my-company/billing/status")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["worker_count"] == 12
    assert payload["subscription_tier"] == "unlimited"
    assert payload["would_block_next_add"] is False


@pytest.mark.asyncio
async def test_billing_status_pricing_parity_with_service_calculation(
    client: AsyncClient,
    db_session: AsyncSession,
    free_company: Company,
    free_company_admin: User,
):
    # 14 total workers including the admin user.
    await _add_workers(db_session, company_id=free_company.id, count=13)
    await db_session.commit()

    app.dependency_overrides[get_current_admin_user] = lambda: free_company_admin
    try:
        response = await client.get("/api/companies/my-company/billing/status")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 200, response.text
    payload = response.json()

    expected = calculate_monthly_pricing(payload["worker_count"])
    assert payload["seats_over_free"] == expected.seats_over_free
    assert (
        payload["per_seat_monthly_cost_dollars"]
        == expected.per_seat_monthly_cost_dollars
    )
    assert payload["should_recommend_unlimited"] is expected.should_recommend_unlimited
    assert payload["worker_count"] == 14
    assert payload["should_recommend_unlimited"] is True


@pytest.mark.asyncio
async def test_billing_status_non_admin_forbidden(
    client: AsyncClient,
    test_user: User,
):
    app.dependency_overrides[get_current_user] = lambda: test_user
    try:
        response = await client.get("/api/companies/my-company/billing/status")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Not enough permissions"


@pytest.mark.asyncio
async def test_billing_status_admin_with_no_company_gets_404(
    client: AsyncClient,
    companyless_super_admin: User,
):
    app.dependency_overrides[get_current_admin_user] = lambda: companyless_super_admin
    try:
        response = await client.get("/api/companies/my-company/billing/status")
    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "User is not associated with a company"
