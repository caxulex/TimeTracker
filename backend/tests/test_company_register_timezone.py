"""Tests for ``CompanyRegister`` timezone field (Prompt 4a follow-up).

The 4a pass added a ``timezone`` field + IANA validator to ``CompanyRegister``
so create-side and update-side rules cannot drift. These tests pin that
behaviour:

1. POST with a valid IANA zone -> 201, company stored with that zone.
2. POST with a bogus zone string -> 422 (validator rejects at API edge).
3. POST without ``timezone`` -> 201, defaults to ``"UTC"``.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company


def _payload(**overrides) -> dict:
    """Build a minimally-valid CompanyRegister body. Slug is randomized so
    parallel test invocations do not collide on the unique ``slug``/email
    columns.
    """
    suffix = uuid.uuid4().hex[:8]
    body = {
        "company_name": f"Acme {suffix}",
        "company_slug": f"acme-{suffix}",
        "admin_email": f"admin-{suffix}@example.com",
        "admin_password": "Password123!",
        "admin_name": "Admin User",
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_register_with_valid_iana_timezone_persists_it(
    client: AsyncClient, db_session: AsyncSession
):
    body = _payload(timezone="America/Los_Angeles")
    resp = await client.post("/api/companies/register", json=body)
    assert resp.status_code == 201, resp.text

    result = await db_session.execute(
        select(Company).where(Company.slug == body["company_slug"])
    )
    company = result.scalar_one()
    assert company.timezone == "America/Los_Angeles"


@pytest.mark.asyncio
async def test_register_with_invalid_timezone_returns_422(client: AsyncClient):
    body = _payload(timezone="Not/A/Real/Zone")
    resp = await client.post("/api/companies/register", json=body)
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    # Pydantic v2 returns a list of error dicts; assert the offending field
    # is ``timezone`` so a different validator firing wouldn't accidentally
    # green this test.
    fields = [tuple(err.get("loc", ())) for err in detail]
    assert any("timezone" in loc for loc in fields), detail


@pytest.mark.asyncio
async def test_register_without_timezone_defaults_to_utc(
    client: AsyncClient, db_session: AsyncSession
):
    body = _payload()
    assert "timezone" not in body
    resp = await client.post("/api/companies/register", json=body)
    assert resp.status_code == 201, resp.text

    result = await db_session.execute(
        select(Company).where(Company.slug == body["company_slug"])
    )
    company = result.scalar_one()
    assert company.timezone == "UTC"
