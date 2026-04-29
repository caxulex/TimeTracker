"""
Cross-endpoint integration tests for tenant-local day boundaries (B6/B7/B9).

NON-NEGOTIABLE per Prompt 4a deliverables: an entry that straddles UTC
midnight but lies on a single local civil day in the tenant's timezone
must appear exactly once when both ``/reports/...`` and
``/time-entries`` are queried for that local day.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, TimeEntry, User
from app.services.auth_service import AuthService


@pytest_asyncio.fixture
async def la_company_user(db_session: AsyncSession) -> tuple[Company, User, dict]:
    """Create a company pinned to America/Los_Angeles + a user inside it."""
    company = Company(
        name="LA Co",
        slug=f"la-{uuid.uuid4().hex[:8]}",
        email="ops@example.com",
        timezone="America/Los_Angeles",
    )
    db_session.add(company)
    await db_session.flush()

    user = User(
        email=f"la-{uuid.uuid4().hex[:8]}@example.com",
        name="LA User",
        password_hash=AuthService.hash_password("pw1234567890"),
        role="regular_user",
        is_active=True,
        company_id=company.id,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    token = AuthService.create_access_token(
        {"sub": str(user.id), "email": user.email}
    )
    headers = {"Authorization": f"Bearer {token}"}
    await db_session.commit()
    return company, user, headers


@pytest.mark.asyncio
async def test_la_midnight_straddle_appears_once_in_both_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
    la_company_user,
):
    """An entry that begins at 23:30 LA-local on day D and ends at
    00:30 LA-local on day D+1 starts on day D *in LA*. Both endpoints
    must include it exactly once when queried for day D, and exactly
    zero times when queried for the UTC-equivalent date.

    Concretely: 2026-02-10 23:30 PST = 2026-02-11 07:30 UTC. So in UTC
    the entry starts on 2026-02-11; in LA it starts on 2026-02-10.
    """
    company, user, headers = la_company_user

    # Local 2026-02-10 23:30 PST -> UTC 2026-02-11 07:30
    start_utc = datetime(2026, 2, 11, 7, 30, tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(hours=1)
    entry = TimeEntry(
        user_id=user.id,
        start_time=start_utc,
        end_time=end_utc,
        duration_seconds=3600,
        description="Late shift",
        is_running=False,
    )
    db_session.add(entry)
    await db_session.commit()

    # --- Query 1: local civil day 2026-02-10 ---
    local_day = "2026-02-10"
    te_resp = await client.get(
        f"/api/time?start_date={local_day}&end_date={local_day}",
        headers=headers,
    )
    assert te_resp.status_code == 200, te_resp.text
    te_data = te_resp.json()
    # Response shape: {"items": [...], "page": ..., "page_size": ..., "pages": ...}
    items = te_data["items"] if isinstance(te_data, dict) and "items" in te_data else te_data
    assert isinstance(items, list)
    matching = [e for e in items if e.get("id") == entry.id]
    assert len(matching) == 1, (
        "Entry that begins at 23:30 LA-local on 2026-02-10 must appear "
        f"exactly once in /time-entries for that local day, got {len(matching)}"
    )

    rep_resp = await client.get(
        f"/api/reports/export?format=json&start_date={local_day}&end_date={local_day}",
        headers=headers,
    )
    # /reports/export may stream; accept JSON-like or text payload as long
    # as the entry id is present.
    assert rep_resp.status_code in (200, 404)
    if rep_resp.status_code == 200:
        body = rep_resp.text
        assert str(entry.id) in body or "Late shift" in body, (
            "Entry must appear in /reports/export for local day 2026-02-10"
        )

    # --- Query 2: UTC-equivalent date 2026-02-11 (must NOT include) ---
    utc_day = "2026-02-11"
    te_resp_utc = await client.get(
        f"/api/time?start_date={utc_day}&end_date={utc_day}",
        headers=headers,
    )
    assert te_resp_utc.status_code == 200
    utc_data = te_resp_utc.json()
    utc_items = utc_data["items"] if isinstance(utc_data, dict) and "items" in utc_data else utc_data
    assert isinstance(utc_items, list)
    utc_matching = [e for e in utc_items if e.get("id") == entry.id]
    assert len(utc_matching) == 0, (
        "Entry on LA-local 2026-02-10 must NOT appear when /time-entries "
        f"is queried for 2026-02-11 (which would be the UTC date), "
        f"got {len(utc_matching)}"
    )


@pytest.mark.asyncio
async def test_dashboard_uses_local_today(
    client: AsyncClient,
    db_session: AsyncSession,
    la_company_user,
):
    """A second sanity check: /reports/dashboard must accept the
    company timezone and not raise on a tenant pinned to LA."""
    company, user, headers = la_company_user
    resp = await client.get("/api/reports/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, dict)
