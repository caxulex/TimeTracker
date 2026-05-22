# ============================================
# TIME TRACKER - TEAMS API TESTS
# ============================================
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Project, Team, TeamMember, TimeEntry, User


@pytest_asyncio.fixture
async def test_team(db_session: AsyncSession, test_user: User) -> Team:
    """Create a test team."""
    team = Team(
        name="Test Team",
        owner_id=test_user.id,
    )
    db_session.add(team)
    await db_session.flush()
    
    # Add owner as admin member
    member = TeamMember(
        team_id=team.id,
        user_id=test_user.id,
        role="owner",
    )
    db_session.add(member)
    await db_session.flush()
    await db_session.refresh(team)
    
    return team


class TestTeamCreate:
    """Test team creation endpoint."""
    
    @pytest.mark.asyncio
    async def test_create_team_success(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test successful team creation."""
        response = await client.post(
            "/api/teams",
            json={
                "name": "New Team",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Team"
    
    @pytest.mark.asyncio
    async def test_create_team_unauthenticated(self, client: AsyncClient):
        """Test team creation without authentication fails."""
        response = await client.post(
            "/api/teams",
            json={"name": "New Team"},
        )
        # HTTPBearer returns 403 when no credentials
        assert response.status_code == 403


class TestTeamList:
    """Test team listing endpoint."""
    
    @pytest.mark.asyncio
    async def test_list_teams(
        self, client: AsyncClient, auth_headers: dict, test_team: Team
    ):
        """Test listing teams."""
        response = await client.get("/api/teams", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)


class TestTeamGet:
    """Test get single team endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_team(
        self, client: AsyncClient, auth_headers: dict, test_team: Team
    ):
        """Test getting a single team."""
        response = await client.get(
            f"/api/teams/{test_team.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_team.name
    
    @pytest.mark.asyncio
    async def test_get_team_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting a nonexistent team fails."""
        response = await client.get(
            "/api/teams/99999",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestTeamUpdate:
    """Test team update endpoint."""
    
    @pytest.mark.asyncio
    async def test_update_team(
        self, client: AsyncClient, auth_headers: dict, test_team: Team
    ):
        """Test updating a team."""
        response = await client.put(
            f"/api/teams/{test_team.id}",
            json={
                "name": "Updated Team Name",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Team Name"


class TestTeamDelete:
    """Test team deletion endpoint."""
    
    @pytest.mark.asyncio
    async def test_delete_team(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test deleting a team (create one without members for clean deletion)."""
        # First create a team
        create_response = await client.post(
            "/api/teams",
            json={"name": "Team To Delete"},
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        team_id = create_response.json()["id"]
        
        # Then delete it
        response = await client.delete(
            f"/api/teams/{team_id}",
            headers=auth_headers,
        )
        # Check for successful deletion (200 or 204)
        assert response.status_code in [200, 204]

    @pytest.mark.asyncio
    async def test_delete_team_refused_when_projects_have_time_entries(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_team: Team,
    ):
        """Team delete must be refused (400) when a project in the team has time entries."""
        # Create a project in the team with a time entry attached
        project = Project(
            name="Project With Entries",
            team_id=test_team.id,
            color="#3B82F6",
        )
        db_session.add(project)
        await db_session.flush()

        start = datetime.now(timezone.utc) - timedelta(hours=1)
        entry = TimeEntry(
            user_id=test_user.id,
            project_id=project.id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            duration_seconds=1800,
            is_running=False,
        )
        db_session.add(entry)
        await db_session.commit()

        response = await client.delete(
            f"/api/teams/{test_team.id}",
            headers=auth_headers,
        )
        assert response.status_code == 400
        body = response.json()
        assert "time entries" in body["detail"].lower()
        # Message communicates the count of blocking projects
        assert "1" in body["detail"]

        # Team and project must still exist
        team_still_there = await db_session.scalar(
            select(func.count()).select_from(Team).where(Team.id == test_team.id)
        )
        assert team_still_there == 1
        project_still_there = await db_session.scalar(
            select(func.count()).select_from(Project).where(Project.id == project.id)
        )
        assert project_still_there == 1

    @pytest.mark.asyncio
    async def test_delete_team_with_empty_projects_writes_per_project_audit_logs(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_team: Team,
    ):
        """Team delete succeeds when projects exist but have no time entries, and writes a per-project audit log."""
        project_a = Project(name="Proj A", team_id=test_team.id, color="#3B82F6")
        project_b = Project(name="Proj B", team_id=test_team.id, color="#3B82F6")
        db_session.add_all([project_a, project_b])
        await db_session.commit()
        project_a_id = project_a.id
        project_b_id = project_b.id

        response = await client.delete(
            f"/api/teams/{test_team.id}",
            headers=auth_headers,
        )
        assert response.status_code in [200, 204]

        # Per-project DELETE audit log rows must exist for each cascaded project
        rows = (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.resource_type == "project",
                    AuditLog.action == "DELETE",
                    AuditLog.resource_id.in_([project_a_id, project_b_id]),
                )
            )
        ).scalars().all()
        logged_ids = {r.resource_id for r in rows}
        assert logged_ids == {project_a_id, project_b_id}
        for row in rows:
            assert row.user_id == test_user.id
            assert "Cascaded delete from team" in (row.details or "")

        # Team-level DELETE audit log is still written
        team_log = (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.resource_type == "team",
                    AuditLog.action == "DELETE",
                    AuditLog.resource_id == test_team.id,
                )
            )
        ).scalar_one_or_none()
        assert team_log is not None
