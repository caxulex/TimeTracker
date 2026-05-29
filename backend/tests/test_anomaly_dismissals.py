"""Tests for anomaly dismissal persistence (PR fix/anomaly-dismissal-persistence).

The legacy ``dismiss_anomaly`` only logged usage analytics; the row
never persisted and the listing endpoint always re-served dismissed
anomalies. These tests pin the new behaviour:

* Dismissals persist to ``anomaly_dismissals``.
* Re-dismissing the same ``(company, target_user, anomaly_type)``
  upserts a single row.
* Dismissals filter the admin listing path.
* Dismissals are scoped per company.
* An audit-log entry is written for every dismissal.
* The endpoint surfaces a service failure as HTTP 500 instead of a
  silent ``{"success": false}``.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.services.anomaly_service import AnomalyService
from app.models import AnomalyDismissal, AuditLog, Company, User
from app.services.auth_service import AuthService


class _StubRedis:
    async def exists(self, _key: str) -> int:
        return 0

    async def ping(self) -> bool:
        return True


@pytest_asyncio.fixture(autouse=True)
async def _stub_token_blacklist_redis():
    from app.services import token_blacklist as _tb_module

    _tb_module.token_blacklist._redis = _StubRedis()
    yield
    _tb_module.token_blacklist._redis = None


@pytest_asyncio.fixture
async def company_a(db_session: AsyncSession) -> Company:
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        name=f"Company A {suffix}",
        slug=f"company-a-{suffix}",
        email=f"a-{suffix}@example.com",
        status="active",
    )
    db_session.add(company)
    await db_session.flush()
    await db_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def company_b(db_session: AsyncSession) -> Company:
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        name=f"Company B {suffix}",
        slug=f"company-b-{suffix}",
        email=f"b-{suffix}@example.com",
        status="active",
    )
    db_session.add(company)
    await db_session.flush()
    await db_session.refresh(company)
    return company


async def _make_user(
    db_session: AsyncSession,
    company: Company,
    role: str = "regular_user",
) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"user-{suffix}@example.com",
        name=f"User {suffix}",
        password_hash=AuthService.hash_password("TestPass123!"),
        role=role,
        is_active=True,
        company_id=company.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_a(db_session: AsyncSession, company_a: Company) -> User:
    return await _make_user(db_session, company_a, role="admin")


@pytest_asyncio.fixture
async def target_a(db_session: AsyncSession, company_a: Company) -> User:
    return await _make_user(db_session, company_a, role="regular_user")


@pytest_asyncio.fixture
async def admin_b(db_session: AsyncSession, company_b: Company) -> User:
    return await _make_user(db_session, company_b, role="admin")


@pytest_asyncio.fixture
async def target_b(db_session: AsyncSession, company_b: Company) -> User:
    return await _make_user(db_session, company_b, role="regular_user")


async def _service(db_session: AsyncSession) -> AnomalyService:
    # Bypass the cache + feature manager plumbing; we only exercise
    # dismissal storage / filtering, not full scans.
    return AnomalyService(db_session, cache_manager=None)


@pytest.mark.asyncio
async def test_anomaly_dismissal_persists(
    db_session: AsyncSession,
    company_a: Company,
    admin_a: User,
    target_a: User,
):
    service = await _service(db_session)
    ok = await service.dismiss_anomaly(
        user_id=target_a.id,
        anomaly_type="extended_day",
        dismissed_by=admin_a.id,
        company_id=company_a.id,
        dismissed_by_email=admin_a.email,
        reason="Approved overtime",
    )
    assert ok is True

    rows = (
        await db_session.execute(
            select(AnomalyDismissal).where(
                AnomalyDismissal.company_id == company_a.id
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.target_user_id == target_a.id
    assert row.anomaly_type == "extended_day"
    assert row.dismissed_by_user_id == admin_a.id
    assert row.reason == "Approved overtime"
    assert row.dismissed_at is not None


@pytest.mark.asyncio
async def test_anomaly_dismissal_upsert(
    db_session: AsyncSession,
    company_a: Company,
    admin_a: User,
    target_a: User,
):
    service = await _service(db_session)
    await service.dismiss_anomaly(
        user_id=target_a.id,
        anomaly_type="extended_day",
        dismissed_by=admin_a.id,
        company_id=company_a.id,
        dismissed_by_email=admin_a.email,
        reason="first",
    )
    first_row = (
        await db_session.execute(select(AnomalyDismissal))
    ).scalar_one()
    first_dismissed_at = first_row.dismissed_at

    # Re-dismiss the same (company, target, type) with a different
    # reason. We expect a single row whose dismissed_at moved forward.
    await service.dismiss_anomaly(
        user_id=target_a.id,
        anomaly_type="extended_day",
        dismissed_by=admin_a.id,
        company_id=company_a.id,
        dismissed_by_email=admin_a.email,
        reason="second",
    )

    rows = (
        await db_session.execute(select(AnomalyDismissal))
    ).scalars().all()
    assert len(rows) == 1
    await db_session.refresh(rows[0])
    assert rows[0].reason == "second"
    assert rows[0].dismissed_at >= first_dismissed_at


@pytest.mark.asyncio
async def test_anomaly_dismissal_filters_listing(
    db_session: AsyncSession,
    company_a: Company,
    admin_a: User,
    target_a: User,
):
    """The helpers that ``scan_all_users`` uses to filter the listing
    must exclude dismissed (target_user_id, anomaly_type) tuples."""
    service = await _service(db_session)
    await service.dismiss_anomaly(
        user_id=target_a.id,
        anomaly_type="extended_day",
        dismissed_by=admin_a.id,
        company_id=company_a.id,
        dismissed_by_email=admin_a.email,
    )

    fake_anomalies = [
        {"user_id": target_a.id, "type": "extended_day", "severity": "warning"},
        {"user_id": target_a.id, "type": "burnout_risk", "severity": "critical"},
    ]
    dismissed = await service._get_dismissed_keys(company_a.id)
    assert (target_a.id, "extended_day") in dismissed

    filtered = service._filter_dismissed(fake_anomalies, dismissed)
    assert len(filtered) == 1
    assert filtered[0]["type"] == "burnout_risk"


@pytest.mark.asyncio
async def test_anomaly_dismissal_per_company(
    db_session: AsyncSession,
    company_a: Company,
    company_b: Company,
    admin_a: User,
    target_a: User,
    target_b: User,
):
    service = await _service(db_session)
    await service.dismiss_anomaly(
        user_id=target_a.id,
        anomaly_type="extended_day",
        dismissed_by=admin_a.id,
        company_id=company_a.id,
        dismissed_by_email=admin_a.email,
    )

    keys_a = await service._get_dismissed_keys(company_a.id)
    keys_b = await service._get_dismissed_keys(company_b.id)
    assert (target_a.id, "extended_day") in keys_a
    assert keys_b == set()


@pytest.mark.asyncio
async def test_anomaly_dismissal_audit_log(
    db_session: AsyncSession,
    company_a: Company,
    admin_a: User,
    target_a: User,
):
    service = await _service(db_session)
    await service.dismiss_anomaly(
        user_id=target_a.id,
        anomaly_type="extended_day",
        dismissed_by=admin_a.id,
        company_id=company_a.id,
        dismissed_by_email=admin_a.email,
        reason="approved",
    )

    logs = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "anomaly_dismissal"
            )
        )
    ).scalars().all()
    assert len(logs) == 1
    entry = logs[0]
    assert entry.action == "CREATE"
    assert entry.user_id == admin_a.id
    assert entry.user_email == admin_a.email
    assert entry.details and "extended_day" in entry.details
    assert f"target_user_id={target_a.id}" in entry.details


@pytest.mark.asyncio
async def test_anomaly_dismissal_endpoint_500_on_failure(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_a: User,
):
    """When the service raises (or returns False), the endpoint must
    return HTTP 500 instead of the legacy ``{"success": false}``."""
    from app.ai import router as ai_router

    token = AuthService.create_access_token(
        {"sub": str(admin_a.id), "email": admin_a.email}
    )
    headers = {"Authorization": f"Bearer {token}"}

    class _BoomService:
        async def dismiss_anomaly(self, **_kwargs):
            raise RuntimeError("simulated persistence failure")

    async def _override_get_anomaly_service(_db):
        return _BoomService()

    original = ai_router.get_anomaly_service
    ai_router.get_anomaly_service = _override_get_anomaly_service
    try:
        response = await client.post(
            "/api/ai/anomalies/dismiss",
            headers=headers,
            json={
                "user_id": 999,
                "anomaly_type": "extended_day",
            },
        )
    finally:
        ai_router.get_anomaly_service = original

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_anomaly_dismissal_endpoint_500_on_service_returning_false(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_a: User,
):
    """If the service returns ``False`` (e.g. DB error swallowed),
    the endpoint must surface 500, not 200."""
    from app.ai import router as ai_router

    token = AuthService.create_access_token(
        {"sub": str(admin_a.id), "email": admin_a.email}
    )
    headers = {"Authorization": f"Bearer {token}"}

    class _FalseService:
        async def dismiss_anomaly(self, **_kwargs):
            return False

    async def _override(_db):
        return _FalseService()

    original = ai_router.get_anomaly_service
    ai_router.get_anomaly_service = _override
    try:
        response = await client.post(
            "/api/ai/anomalies/dismiss",
            headers=headers,
            json={
                "user_id": 999,
                "anomaly_type": "extended_day",
            },
        )
    finally:
        ai_router.get_anomaly_service = original

    assert response.status_code == 500
