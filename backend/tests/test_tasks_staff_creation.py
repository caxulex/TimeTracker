# ============================================
# TIME TRACKER - STAFF TASK-CREATION PERMISSION TESTS
# --------------------------------------------
# Verifies the 2026-05-14 product decision (option ``a``): any
# authenticated user may create tasks on any project they have
# visibility into per ``GET /api/projects``. Non-admins still cannot
# create tasks on projects they cannot see (403 on cross-team access,
# 404 on a non-existent project id).
# ============================================
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Team, TeamMember, User
from app.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def _bypass_blacklist_check(monkeypatch):
    """Skip the Redis-backed JWT blacklist lookup in this suite.

    The blacklist fail-closed semantics are exercised by
    ``test_blacklist_failclosed_b4.py``; this suite only cares about
    authorization, so we short-circuit the lookup to keep the tests
    independent of Redis availability in dev environments.
    """
    async def _fake_check(_jti: str) -> bool:  # noqa: ARG001
        return False

    monkeypatch.setattr(
        "app.dependencies._check_blacklist_or_fail_closed",
        _fake_check,
    )


@pytest_asyncio.fixture
async def staff_team(db_session: AsyncSession, test_user: User) -> Team:
    """Team owned by the regular ``test_user`` with that user as a member."""
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
async def staff_project(db_session: AsyncSession, staff_team: Team) -> Project:
    project = Project(
        name="Staff Visible Project",
        description="Project the regular user can see.",
        color="#10B981",
        team_id=staff_team.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


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
async def other_project(db_session: AsyncSession, other_user: User) -> Project:
    """Project on a team the regular ``test_user`` is NOT a member of."""
    team = Team(name="Other Team", owner_id=other_user.id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(
        TeamMember(team_id=team.id, user_id=other_user.id, role="owner")
    )
    await db_session.flush()
    project = Project(
        name="Hidden Project",
        description="Not visible to test_user.",
        color="#EF4444",
        team_id=team.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


class TestStaffTaskCreation:
    """The relaxed permission: staff can create on visible projects."""

    @pytest.mark.asyncio
    async def test_staff_can_create_task_on_visible_project(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        staff_project: Project,
    ):
        assert test_user.role == "regular_user"
        response = await client.post(
            "/api/tasks",
            json={
                "name": "Staff Created Task",
                "description": "Created by a non-admin user.",
                "project_id": staff_project.id,
                "status": "TODO",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["name"] == "Staff Created Task"
        assert data["project_id"] == staff_project.id
        assert data["status"] == "TODO"

    @pytest.mark.asyncio
    async def test_staff_cannot_create_task_on_non_visible_project(
        self,
        client: AsyncClient,
        auth_headers: dict,
        other_project: Project,
    ):
        response = await client.post(
            "/api/tasks",
            json={
                "name": "Should Not Exist",
                "project_id": other_project.id,
                "status": "TODO",
            },
            headers=auth_headers,
        )
        # check_project_access conflates "not found" and "no access"
        # into 404 on the create endpoint, matching the existing
        # pattern for unauthorised project access.
        assert response.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_staff_cannot_create_task_on_unknown_project(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        response = await client.post(
            "/api/tasks",
            json={
                "name": "Bogus Project Task",
                "project_id": 999_999,
                "status": "TODO",
            },
            headers=auth_headers,
        )
        assert response.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_admin_creation_still_works(
        self,
        client: AsyncClient,
        admin_auth_headers: dict,
        staff_project: Project,
    ):
        """Admin flow must be unchanged after the relaxation."""
        response = await client.post(
            "/api/tasks",
            json={
                "name": "Admin Created Task",
                "project_id": staff_project.id,
                "status": "TODO",
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["name"] == "Admin Created Task"

    @pytest.mark.asyncio
    async def test_user_created_tasks_have_no_basecamp_mapping(
        self,
        client: AsyncClient,
        auth_headers: dict,
        staff_project: Project,
        db_session: AsyncSession,
    ):
        """Sync safety: user-created tasks must not get a
        ``BasecampTaskMapping`` row, so the autosync job (keyed off
        ``basecamp_todo_id``) leaves them untouched.
        """
        response = await client.post(
            "/api/tasks",
            json={
                "name": "Sync Safety Probe",
                "project_id": staff_project.id,
                "status": "TODO",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        task_id = response.json()["id"]

        from sqlalchemy import select

        from app.models import BasecampTaskMapping

        mapping = await db_session.execute(
            select(BasecampTaskMapping).where(BasecampTaskMapping.task_id == task_id)
        )
        assert mapping.scalar_one_or_none() is None
