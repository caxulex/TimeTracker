# ============================================
# TIME TRACKER - PERSONAL REPORT SCOPE REGRESSION TESTS
# ============================================
# Regression guards for the bug where /api/reports/dashboard, /weekly, and
# /by-project returned company-wide / team-wide aggregates instead of the
# authenticated user's personal entries. See fix in routers/reports.py.

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Team, TeamMember, TimeEntry, User
from app.services.auth_service import AuthService


# ----------------------------------------------------------------------
# Local fixtures: two users (A and B) on the same team, each with entries.
# Mirrors the convention used in test_reports.py (db_session, AsyncClient,
# token-based auth headers).
# ----------------------------------------------------------------------


def _auth_headers_for(user: User) -> dict:
    token = AuthService.create_access_token(
        {"sub": str(user.id), "email": user.email}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_a(db_session: AsyncSession) -> User:
    user = User(
        email=f"user-a-{uuid.uuid4().hex[:8]}@example.com",
        name="User A",
        password_hash=AuthService.hash_password("passwordA123"),
        role="regular_user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_b(db_session: AsyncSession) -> User:
    user = User(
        email=f"user-b-{uuid.uuid4().hex[:8]}@example.com",
        name="User B",
        password_hash=AuthService.hash_password("passwordB123"),
        role="regular_user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_a(db_session: AsyncSession) -> User:
    user = User(
        email=f"admin-a-{uuid.uuid4().hex[:8]}@example.com",
        name="Admin A",
        password_hash=AuthService.hash_password("adminA12345"),
        role="super_admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def shared_team(
    db_session: AsyncSession, user_a: User, user_b: User
) -> Team:
    team = Team(name="Shared Team", owner_id=user_a.id)
    db_session.add(team)
    await db_session.flush()
    db_session.add_all(
        [
            TeamMember(team_id=team.id, user_id=user_a.id, role="owner"),
            TeamMember(team_id=team.id, user_id=user_b.id, role="member"),
        ]
    )
    await db_session.flush()
    await db_session.refresh(team)
    return team


@pytest_asyncio.fixture
async def shared_project(
    db_session: AsyncSession, shared_team: Team
) -> Project:
    project = Project(
        name="Shared Project",
        team_id=shared_team.id,
        color="#3B82F6",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


# Each user logs N hours TODAY (UTC) on the shared project. Using 09:00-..
# UTC anchored to today minimizes the chance of straddling local-tz day
# boundaries on most timezones.
USER_A_HOURS_TODAY = 2
USER_B_HOURS_TODAY = 5


@pytest_asyncio.fixture
async def entries_today(
    db_session: AsyncSession,
    user_a: User,
    user_b: User,
    shared_project: Project,
):
    # Build entries that are unambiguously inside "today" in any tz: span
    # noon ± a few hours UTC, which is well within today for all major
    # populated tz offsets when compared via overlap arithmetic.
    today = datetime.now(timezone.utc).replace(
        hour=12, minute=0, second=0, microsecond=0
    )

    a_entry = TimeEntry(
        user_id=user_a.id,
        project_id=shared_project.id,
        description="A's work",
        start_time=today - timedelta(hours=USER_A_HOURS_TODAY),
        end_time=today,
        duration_seconds=USER_A_HOURS_TODAY * 3600,
        is_running=False,
    )
    b_entry = TimeEntry(
        user_id=user_b.id,
        project_id=shared_project.id,
        description="B's work",
        start_time=today - timedelta(hours=USER_B_HOURS_TODAY),
        end_time=today,
        duration_seconds=USER_B_HOURS_TODAY * 3600,
        is_running=False,
    )
    db_session.add_all([a_entry, b_entry])
    await db_session.flush()
    return {"a": a_entry, "b": b_entry}


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_returns_only_current_user_entries(
    client: AsyncClient, user_a: User, user_b: User, entries_today
):
    """/api/reports/dashboard must return ONLY the calling user's seconds."""
    response = await client.get(
        "/api/reports/dashboard", headers=_auth_headers_for(user_a)
    )
    assert response.status_code == 200, response.text
    data = response.json()

    # Only user A's hours should be reflected, not A + B.
    assert data["today_seconds"] == USER_A_HOURS_TODAY * 3600, (
        f"Expected {USER_A_HOURS_TODAY * 3600}s for user A only; "
        f"got {data['today_seconds']}s (would be "
        f"{(USER_A_HOURS_TODAY + USER_B_HOURS_TODAY) * 3600} if leaking)."
    )
    assert data["week_seconds"] == USER_A_HOURS_TODAY * 3600
    assert data["month_seconds"] == USER_A_HOURS_TODAY * 3600


@pytest.mark.asyncio
async def test_weekly_returns_only_current_user_entries(
    client: AsyncClient, user_a: User, user_b: User, entries_today
):
    """/api/reports/weekly must aggregate ONLY the calling user's entries."""
    response = await client.get(
        "/api/reports/weekly", headers=_auth_headers_for(user_a)
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["total_seconds"] == USER_A_HOURS_TODAY * 3600

    daily_total = sum(d["total_seconds"] for d in data["daily_breakdown"])
    assert daily_total == USER_A_HOURS_TODAY * 3600


@pytest.mark.asyncio
async def test_by_project_returns_only_current_user_entries(
    client: AsyncClient,
    user_a: User,
    user_b: User,
    shared_project: Project,
    entries_today,
):
    """/api/reports/by-project must group ONLY the calling user's entries."""
    response = await client.get(
        "/api/reports/by-project", headers=_auth_headers_for(user_a)
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert isinstance(data, list)
    project_rows = [p for p in data if p["project_id"] == shared_project.id]
    assert len(project_rows) == 1, (
        f"Expected exactly one row for shared project; got {data}"
    )
    assert project_rows[0]["total_seconds"] == USER_A_HOURS_TODAY * 3600
    assert project_rows[0]["entry_count"] == 1


@pytest.mark.asyncio
async def test_admin_dashboard_still_returns_all_company_entries(
    client: AsyncClient,
    admin_a: User,
    user_b: User,
    shared_project: Project,
    db_session: AsyncSession,
):
    """Regression guard: /api/reports/admin/dashboard remains company-wide."""
    today = datetime.now(timezone.utc).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    admin_entry = TimeEntry(
        user_id=admin_a.id,
        project_id=shared_project.id,
        description="admin work",
        start_time=today - timedelta(hours=3),
        end_time=today,
        duration_seconds=3 * 3600,
        is_running=False,
    )
    other_entry = TimeEntry(
        user_id=user_b.id,
        project_id=shared_project.id,
        description="user B work",
        start_time=today - timedelta(hours=4),
        end_time=today,
        duration_seconds=4 * 3600,
        is_running=False,
    )
    db_session.add_all([admin_entry, other_entry])
    await db_session.flush()

    response = await client.get(
        "/api/reports/admin/dashboard", headers=_auth_headers_for(admin_a)
    )
    assert response.status_code == 200, response.text
    data = response.json()

    # Both users' time should be aggregated.
    assert data["total_today_seconds"] == 7 * 3600, data
    user_ids_in_response = {row["user_id"] for row in data["by_user"]}
    assert admin_a.id in user_ids_in_response
    assert user_b.id in user_ids_in_response


@pytest.mark.asyncio
async def test_admin_user_personal_dashboard_only_shows_their_data(
    client: AsyncClient,
    admin_a: User,
    user_b: User,
    shared_project: Project,
    db_session: AsyncSession,
):
    """The specific bug: an admin hitting /dashboard (NOT /admin/dashboard)
    must see ONLY their own personal stats, not company-wide aggregates."""
    today = datetime.now(timezone.utc).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    admin_hours = 1
    other_hours = 6
    admin_entry = TimeEntry(
        user_id=admin_a.id,
        project_id=shared_project.id,
        description="admin personal work",
        start_time=today - timedelta(hours=admin_hours),
        end_time=today,
        duration_seconds=admin_hours * 3600,
        is_running=False,
    )
    other_entry = TimeEntry(
        user_id=user_b.id,
        project_id=shared_project.id,
        description="user B work",
        start_time=today - timedelta(hours=other_hours),
        end_time=today,
        duration_seconds=other_hours * 3600,
        is_running=False,
    )
    db_session.add_all([admin_entry, other_entry])
    await db_session.flush()

    response = await client.get(
        "/api/reports/dashboard", headers=_auth_headers_for(admin_a)
    )
    assert response.status_code == 200, response.text
    data = response.json()

    # The bug returned (admin_hours + other_hours) * 3600. Fix returns admin_hours only.
    assert data["today_seconds"] == admin_hours * 3600, (
        f"Admin's personal dashboard leaked other users' time: "
        f"got {data['today_seconds']}s, expected {admin_hours * 3600}s. "
        f"Company-wide would be {(admin_hours + other_hours) * 3600}s."
    )
