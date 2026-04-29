# ============================================
# B29: list_time_entries authorization tightening
# ============================================
# A non-admin requesting ?user_id=<stranger> (no shared team) used to
# silently get an empty 200. It now returns 403.
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Team, TeamMember, TimeEntry, User
from app.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def _bypass_blacklist_for_b29(monkeypatch):
    """Skip the live Redis blacklist round-trip in this file.

    The real ``_check_blacklist_or_fail_closed`` makes a TCP call which
    is the documented Windows async-redis flake (errno 22). The check
    has its own coverage in ``test_blacklist_failclosed_b4.py``; for
    B29 authorization assertions we just need a non-blacklisted token.
    """

    async def _ok(_jti: str) -> bool:
        return False

    monkeypatch.setattr("app.dependencies._check_blacklist_or_fail_closed", _ok)


@pytest_asyncio.fixture
async def shared_team(db_session: AsyncSession, test_user: User) -> Team:
    team = Team(
        name=f"B29 team {uuid.uuid4().hex[:6]}",
        owner_id=test_user.id,
    )
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=test_user.id, role="owner"))
    await db_session.flush()
    await db_session.refresh(team)
    return team


@pytest_asyncio.fixture
async def teammate(db_session: AsyncSession, shared_team: Team) -> User:
    user = User(
        email=f"teammate-{uuid.uuid4().hex[:8]}@example.com",
        name="Teammate",
        password_hash=AuthService.hash_password("password123"),
        role="regular_user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(TeamMember(team_id=shared_team.id, user_id=user.id, role="member"))
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def stranger(db_session: AsyncSession) -> User:
    user = User(
        email=f"stranger-{uuid.uuid4().hex[:8]}@example.com",
        name="Stranger",
        password_hash=AuthService.hash_password("password123"),
        role="regular_user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def shared_project(
    db_session: AsyncSession, shared_team: Team
) -> Project:
    project = Project(
        name="B29 project",
        team_id=shared_team.id,
        color="#000000",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


async def _make_entry(
    db_session: AsyncSession, user: User, project: Project
) -> TimeEntry:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    entry = TimeEntry(
        user_id=user.id,
        project_id=project.id,
        start_time=now - timedelta(hours=1),
        end_time=now,
        duration_seconds=3600,
        is_running=False,
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    return entry


@pytest.mark.asyncio
async def test_b29_self_lookup_returns_200(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    shared_project: Project,
    db_session: AsyncSession,
):
    await _make_entry(db_session, test_user, shared_project)
    response = await client.get(
        f"/api/time?user_id={test_user.id}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


@pytest.mark.asyncio
async def test_b29_teammate_lookup_returns_200(
    client: AsyncClient,
    auth_headers: dict,
    teammate: User,
    shared_project: Project,
    db_session: AsyncSession,
):
    await _make_entry(db_session, teammate, shared_project)
    response = await client.get(
        f"/api/time?user_id={teammate.id}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


@pytest.mark.asyncio
async def test_b29_stranger_lookup_returns_403(
    client: AsyncClient,
    auth_headers: dict,
    shared_team: Team,  # ensure requester is in some team
    stranger: User,
):
    response = await client.get(
        f"/api/time?user_id={stranger.id}", headers=auth_headers
    )
    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_b29_admin_can_query_any_user(
    client: AsyncClient,
    admin_auth_headers: dict,
    stranger: User,
):
    response = await client.get(
        f"/api/time?user_id={stranger.id}", headers=admin_auth_headers
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_b29_no_user_id_param_unchanged(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    shared_project: Project,
    db_session: AsyncSession,
):
    await _make_entry(db_session, test_user, shared_project)
    response = await client.get("/api/time", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1
