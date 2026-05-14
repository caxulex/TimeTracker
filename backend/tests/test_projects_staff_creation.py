# ============================================
# TIME TRACKER - STAFF PROJECT-CREATION PERMISSION TESTS
# --------------------------------------------
# Verifies the 2026-05-14 product decision extended to projects:
# any authenticated user can create a project on a team they are a
# ``TeamMember`` of. Non-admins still cannot create projects on
# teams they do not belong to (403). Admin-only fields
# (``budget_amount``, ``deadline``) are silently dropped when
# submitted by a non-admin.
# ============================================
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Team, TeamMember, User
from app.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def _bypass_blacklist_check(monkeypatch):
    """Skip the Redis-backed JWT blacklist lookup in this suite."""
    async def _fake_check(_jti: str) -> bool:  # noqa: ARG001
        return False

    monkeypatch.setattr(
        "app.dependencies._check_blacklist_or_fail_closed",
        _fake_check,
    )


@pytest_asyncio.fixture
async def staff_team(db_session: AsyncSession, test_user: User) -> Team:
    """Team owned by the regular ``test_user`` with that user as member."""
    team = Team(name="Staff Team", owner_id=test_user.id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(
        TeamMember(team_id=team.id, user_id=test_user.id, role="owner")
    )
    await db_session.commit()
    await db_session.refresh(team)
    return team


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    """A second regular user, on a different team."""
    user = User(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        name="Other User",
        password_hash=AuthService.hash_password("otherpassword123"),
        role="regular_user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_team(db_session: AsyncSession, other_user: User) -> Team:
    """Team the regular ``test_user`` is NOT a member of."""
    team = Team(name="Other Team", owner_id=other_user.id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(
        TeamMember(team_id=team.id, user_id=other_user.id, role="owner")
    )
    await db_session.commit()
    await db_session.refresh(team)
    return team


class TestStaffProjectCreation:
    """Relaxed permission: staff can create projects on their teams."""

    @pytest.mark.asyncio
    async def test_staff_can_create_project_on_own_team(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        staff_team: Team,
    ):
        assert test_user.role == "regular_user"
        response = await client.post(
            "/api/projects",
            json={
                "name": "Staff Created Project",
                "description": "Created by a non-admin user.",
                "color": "#10B981",
                "team_id": staff_team.id,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["name"] == "Staff Created Project"
        assert data["team_id"] == staff_team.id

    @pytest.mark.asyncio
    async def test_staff_cannot_create_project_on_foreign_team(
        self,
        client: AsyncClient,
        auth_headers: dict,
        other_team: Team,
    ):
        response = await client.post(
            "/api/projects",
            json={
                "name": "Should Not Exist",
                "color": "#EF4444",
                "team_id": other_team.id,
            },
            headers=auth_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_staff_budget_and_deadline_silently_dropped(
        self,
        client: AsyncClient,
        auth_headers: dict,
        staff_team: Team,
        db_session: AsyncSession,
    ):
        """Non-admins submitting budget/deadline succeed, but the
        fields are not persisted (backend drops them at
        :func:`create_project`)."""
        response = await client.post(
            "/api/projects",
            json={
                "name": "Budget Probe",
                "color": "#3B82F6",
                "team_id": staff_team.id,
                "budget_amount": 9999.99,
                "deadline": "2099-12-31",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        project_id = response.json()["id"]

        # Verify the row in the DB really has NULL budget/deadline.
        result = await db_session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one()
        assert project.budget_amount is None
        assert project.deadline is None

    @pytest.mark.asyncio
    async def test_admin_budget_and_deadline_persist(
        self,
        client: AsyncClient,
        admin_auth_headers: dict,
        admin_user: User,
        db_session: AsyncSession,
    ):
        """Admin flow must continue to honour budget/deadline."""
        # super_admin can create on any team; spin one up.
        team = Team(name="Admin Team", owner_id=admin_user.id)
        db_session.add(team)
        await db_session.flush()
        db_session.add(
            TeamMember(team_id=team.id, user_id=admin_user.id, role="owner")
        )
        await db_session.commit()
        await db_session.refresh(team)

        response = await client.post(
            "/api/projects",
            json={
                "name": "Admin Budgeted Project",
                "color": "#3B82F6",
                "team_id": team.id,
                "budget_amount": 12345.50,
                "deadline": "2099-12-31",
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["budget_amount"] == 12345.50
        assert data["deadline"] == "2099-12-31"

        project_id = data["id"]
        result = await db_session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one()
        assert float(project.budget_amount) == 12345.50
        assert str(project.deadline) == "2099-12-31"
