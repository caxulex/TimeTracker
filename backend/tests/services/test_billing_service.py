from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, User
from app.services.billing_service import (
    PricingSummary,
    calculate_monthly_pricing,
    count_company_billable_workers,
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
