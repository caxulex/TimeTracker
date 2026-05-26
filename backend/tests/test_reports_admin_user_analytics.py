# ============================================
# Tests for GET /api/reports/admin/users/{user_id}/analytics
#
# Regression coverage for the pagination-shadow bug class: the StaffPage
# analytics view used to derive totals by reducing a paginated
# /api/time list capped at 100 rows, silently undercounting any user
# with more than 100 entries in the queried period. The new endpoint
# aggregates server-side, so > 100 entries in range must produce the
# full SUM(duration_seconds).
# ============================================
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Team, TimeEntry, User


@pytest_asyncio.fixture
async def staff_user(db_session: AsyncSession) -> User:
    """A regular user whose analytics we will query."""
    import uuid
    user = User(
        email=f"staff-{uuid.uuid4().hex[:8]}@example.com",
        name="Staff User",
        password_hash="x",
        role="regular_user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def project_with_team(db_session: AsyncSession, admin_user: User) -> Project:
    team = Team(name="Analytics Team", owner_id=admin_user.id)
    db_session.add(team)
    await db_session.flush()
    project = Project(name="Analytics Project", team_id=team.id, color="#3B82F6")
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


@pytest.mark.asyncio
async def test_user_analytics_aggregates_all_entries_over_pagination_cap(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    staff_user: User,
    project_with_team: Project,
):
    """The whole point of this endpoint: > 100 entries in range must
    aggregate to the full sum, not the first-page sum."""
    # Create 150 entries (> /api/time page-size cap of 100) at 1 hour each.
    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    entries = []
    for i in range(150):
        start = now - timedelta(days=i % 25, hours=i % 8)
        end = start + timedelta(hours=1)
        entries.append(
            TimeEntry(
                user_id=staff_user.id,
                project_id=project_with_team.id,
                start_time=start,
                end_time=end,
                duration_seconds=3600,
                is_running=False,
            )
        )
    db_session.add_all(entries)
    await db_session.flush()

    start_date = (now - timedelta(days=30)).date().isoformat()
    end_date = now.date().isoformat()

    response = await client.get(
        f"/api/reports/admin/users/{staff_user.id}/analytics",
        params={"start_date": start_date, "end_date": end_date},
        headers=admin_auth_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    # Full SUM, not capped at 100.
    assert data["total_entries"] == 150
    assert data["total_seconds"] == 150 * 3600
    assert data["total_hours"] == round(150 * 3600 / 3600, 2)
    assert data["project_count"] == 1
    assert data["days_worked"] >= 1
    assert any(p["entry_count"] == 150 for p in data["projects"])


@pytest.mark.asyncio
async def test_user_analytics_filters_to_date_range(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    staff_user: User,
    project_with_team: Project,
):
    """Entries outside [start_date, end_date] must not be counted."""
    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    in_range = TimeEntry(
        user_id=staff_user.id,
        project_id=project_with_team.id,
        start_time=now - timedelta(days=2, hours=2),
        end_time=now - timedelta(days=2, hours=1),
        duration_seconds=3600,
        is_running=False,
    )
    out_of_range = TimeEntry(
        user_id=staff_user.id,
        project_id=project_with_team.id,
        start_time=now - timedelta(days=60),
        end_time=now - timedelta(days=60) + timedelta(hours=2),
        duration_seconds=7200,
        is_running=False,
    )
    db_session.add_all([in_range, out_of_range])
    await db_session.flush()

    response = await client.get(
        f"/api/reports/admin/users/{staff_user.id}/analytics",
        params={
            "start_date": (now - timedelta(days=7)).date().isoformat(),
            "end_date": now.date().isoformat(),
        },
        headers=admin_auth_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_entries"] == 1
    assert data["total_seconds"] == 3600


@pytest.mark.asyncio
async def test_user_analytics_subtracts_pause_seconds(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    staff_user: User,
    project_with_team: Project,
):
    """duration_seconds is already pause-corrected on /stop (PR #31). The
    aggregator must honor it (not re-derive wall-clock minus pauses)."""
    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    # 2-hour wall clock minus 30min pause stored as 5400s on the closed entry.
    entry = TimeEntry(
        user_id=staff_user.id,
        project_id=project_with_team.id,
        start_time=now - timedelta(days=1, hours=2),
        end_time=now - timedelta(days=1),
        duration_seconds=5400,
        pause_seconds=1800,
        is_running=False,
    )
    db_session.add(entry)
    await db_session.flush()

    response = await client.get(
        f"/api/reports/admin/users/{staff_user.id}/analytics",
        params={
            "start_date": (now - timedelta(days=3)).date().isoformat(),
            "end_date": now.date().isoformat(),
        },
        headers=admin_auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_seconds"] == 5400


@pytest.mark.asyncio
async def test_user_analytics_requires_admin(
    client: AsyncClient,
    auth_headers: dict,
    staff_user: User,
):
    """Non-admin must be rejected."""
    response = await client.get(
        f"/api/reports/admin/users/{staff_user.id}/analytics",
        params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_analytics_404_for_unknown_user(
    client: AsyncClient,
    admin_auth_headers: dict,
):
    response = await client.get(
        "/api/reports/admin/users/999999/analytics",
        params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_analytics_400_when_end_before_start(
    client: AsyncClient,
    admin_auth_headers: dict,
    staff_user: User,
):
    response = await client.get(
        f"/api/reports/admin/users/{staff_user.id}/analytics",
        params={"start_date": "2024-02-15", "end_date": "2024-02-01"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 400
