# ============================================
# TIME TRACKER - B2 race-condition tests
# Verifies the unique partial index + 409 handler behavior so two
# concurrent ``POST /api/time/start`` requests cannot both succeed.
# ============================================
import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_db
from app.main import app
from app.models import Project, Team, TeamMember, User
from app.services.auth_service import AuthService


@pytest_asyncio.fixture
async def race_user(db_session: AsyncSession) -> User:
    """A dedicated user for the race test (own fixture to avoid coupling)."""
    user = User(
        email=f"race-{uuid.uuid4().hex[:8]}@example.com",
        name="Race User",
        password_hash=AuthService.hash_password("racepassword123"),
        role="regular_user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def race_project(db_session: AsyncSession, race_user: User) -> Project:
    team = Team(name=f"Race Team {uuid.uuid4().hex[:6]}", owner_id=race_user.id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=race_user.id, role="owner"))
    project = Project(
        name=f"Race Project {uuid.uuid4().hex[:6]}",
        team_id=team.id,
        color="#3B82F6",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def race_auth_headers(race_user: User) -> dict:
    token = AuthService.create_access_token(
        {"sub": str(race_user.id), "email": race_user.email}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_concurrent_start_timer_returns_one_201_and_one_409(
    db_session: AsyncSession,
    async_engine,
    race_project: Project,
    race_auth_headers: dict,
):
    """B2: two concurrent POST /api/time/start for the same user must be
    serialized by ``ux_time_entries_one_running_per_user``. Exactly one
    request wins (201) and the other receives 409.

    The default ``client`` fixture overrides ``get_db`` to return a single
    shared session, which would serialize requests through SQLAlchemy's
    unit of work and never exercise the DB-level race. This test wires
    up its own override that hands each request a *fresh* AsyncSession
    sourced from the shared test engine, so the two coroutines truly
    contend at the database.
    """
    # The race uses fresh sessions per request, so the user/project
    # fixture state must be committed (not just flushed) so the race
    # sessions can see it. The autouse TRUNCATE fixture wipes this
    # after the test.
    await db_session.commit()

    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            payload = {
                "project_id": race_project.id,
                "description": "B2 race attempt",
            }
            r1, r2 = await asyncio.gather(
                ac.post("/api/time/start", json=payload, headers=race_auth_headers),
                ac.post("/api/time/start", json=payload, headers=race_auth_headers),
            )
    finally:
        app.dependency_overrides.clear()

    statuses = sorted([r1.status_code, r2.status_code])
    # Exactly one winner (201) and exactly one 409 from the DB-constraint
    # IntegrityError handler. The pre-check SELECT in the handler is a fast
    # path for the non-racing common case; under true concurrency both
    # requests pass the SELECT and the partial unique index is the
    # authoritative guard. Asserting 409 specifically (not the looser
    # {400, 409}) verifies that the new constraint + IntegrityError handler
    # are what catches the race.
    assert statuses == [201, 409], (
        f"expected exactly [201, 409], got statuses={statuses}"
    )

    loser = r1 if r1.status_code != 201 else r2
    body = loser.json()
    assert body.get("detail") == "A timer is already running for this user."
