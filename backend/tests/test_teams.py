# ============================================
# TIME TRACKER - TEAMS API TESTS
# ============================================
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_company_filter
from app.models import AuditLog, Project, Team, TeamMember, User
from app.services.team_service import restore_team, soft_delete_team


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

    @pytest.mark.asyncio
    async def test_update_deleted_team_returns_409(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_team: Team,
    ):
        delete_response = await client.delete(
            f"/api/teams/{test_team.id}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 204

        response = await client.put(
            f"/api/teams/{test_team.id}",
            json={"name": "Should Fail"},
            headers=auth_headers,
        )
        assert response.status_code == 409


class TestTeamDelete:
    """Test team soft-deletion endpoint."""
    
    @pytest.mark.asyncio
    async def test_delete_team(
        self, client: AsyncClient, auth_headers: dict
    ):
        """DELETE performs soft-delete and returns 204."""
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
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_team_refused_when_team_has_active_projects(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_team: Team,
    ):
        """Soft-delete must be blocked with 409 when non-archived projects exist."""
        project = Project(
            name="Active Project",
            team_id=test_team.id,
            color="#3B82F6",
            is_archived=False,
        )
        db_session.add(project)
        await db_session.commit()

        response = await client.delete(
            f"/api/teams/{test_team.id}",
            headers=auth_headers,
        )
        assert response.status_code == 409
        body = response.json()
        assert "active" in body["detail"].lower()

        team_row = await db_session.scalar(
            select(Team).where(Team.id == test_team.id)
        )
        assert team_row is not None
        assert team_row.deleted_at is None

    @pytest.mark.asyncio
    async def test_soft_delete_hides_team_from_default_list_and_get(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_team: Team,
    ):
        response = await client.delete(
            f"/api/teams/{test_team.id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

        list_response = await client.get("/api/teams", headers=auth_headers)
        assert list_response.status_code == 200
        ids = {item["id"] for item in list_response.json()["items"]}
        assert test_team.id not in ids

        get_response = await client.get(f"/api/teams/{test_team.id}", headers=auth_headers)
        assert get_response.status_code == 404


class TestTeamRestore:
    @pytest.mark.asyncio
    async def test_restore_team_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_team: Team,
    ):
        delete_response = await client.delete(
            f"/api/teams/{test_team.id}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 204

        restore_response = await client.post(
            f"/api/teams/{test_team.id}/restore",
            headers=auth_headers,
        )
        assert restore_response.status_code == 200
        data = restore_response.json()
        assert data["id"] == test_team.id
        assert data["deleted_at"] is None

    @pytest.mark.asyncio
    async def test_restore_team_not_deleted_returns_400(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_team: Team,
    ):
        restore_response = await client.post(
            f"/api/teams/{test_team.id}/restore",
            headers=auth_headers,
        )
        assert restore_response.status_code == 400


class TestTeamDeletedViews:
    @pytest.mark.asyncio
    async def test_include_deleted_admin_and_regular_behaviors(
        self,
        client: AsyncClient,
        auth_headers: dict,
        admin_auth_headers: dict,
        test_team: Team,
    ):
        delete_response = await client.delete(
            f"/api/teams/{test_team.id}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 204

        admin_list = await client.get(
            "/api/teams?include_deleted=true",
            headers=admin_auth_headers,
        )
        assert admin_list.status_code == 200
        admin_items = admin_list.json()["items"]
        deleted_item = next(item for item in admin_items if item["id"] == test_team.id)
        assert deleted_item["deleted_at"] is not None

        regular_list = await client.get(
            "/api/teams?include_deleted=true",
            headers=auth_headers,
        )
        assert regular_list.status_code == 403

    @pytest.mark.asyncio
    async def test_deleted_endpoint_returns_enriched_rows(
        self,
        client: AsyncClient,
        auth_headers: dict,
        admin_auth_headers: dict,
        test_team: Team,
    ):
        response = await client.request(
            "DELETE",
            f"/api/teams/{test_team.id}",
            json={"reason": "cleanup"},
            headers=auth_headers,
        )
        assert response.status_code == 204

        deleted_response = await client.get(
            "/api/teams/deleted",
            headers=admin_auth_headers,
        )
        assert deleted_response.status_code == 200
        items = deleted_response.json()["items"]
        row = next(item for item in items if item["id"] == test_team.id)
        assert row["deleted_at"] is not None
        assert row["delete_reason"] == "cleanup"
        assert row.get("deleted_by_user_name")


class TestTeamService:
    @pytest.mark.asyncio
    async def test_soft_delete_service_marks_team_and_logs(
        self,
        db_session: AsyncSession,
        test_team: Team,
        test_user: User,
    ):
        ok, error_code = await soft_delete_team(
            team_id=test_team.id,
            company_id=get_company_filter(test_user),
            acting_user_id=test_user.id,
            acting_user_email=test_user.email,
            reason="cleanup",
            db=db_session,
        )
        assert ok is True
        assert error_code is None

        team = await db_session.scalar(select(Team).where(Team.id == test_team.id))
        assert team is not None
        assert team.deleted_at is not None
        assert team.delete_reason == "cleanup"

        log = await db_session.scalar(
            select(AuditLog).where(
                AuditLog.resource_type == "team",
                AuditLog.resource_id == test_team.id,
                AuditLog.action == "team.soft_deleted",
            )
        )
        assert log is not None

    @pytest.mark.asyncio
    async def test_soft_delete_service_has_active_projects_conflict(
        self,
        db_session: AsyncSession,
        test_team: Team,
        test_user: User,
    ):
        db_session.add(Project(name="Active", team_id=test_team.id, color="#3B82F6", is_archived=False))
        await db_session.commit()

        ok, error_code = await soft_delete_team(
            team_id=test_team.id,
            company_id=get_company_filter(test_user),
            acting_user_id=test_user.id,
            acting_user_email=test_user.email,
            reason=None,
            db=db_session,
        )
        assert ok is False
        assert error_code == "has_active_projects"

    @pytest.mark.asyncio
    async def test_restore_service_success_and_not_deleted_case(
        self,
        db_session: AsyncSession,
        test_team: Team,
        test_user: User,
    ):
        ok, error_code = await soft_delete_team(
            team_id=test_team.id,
            company_id=get_company_filter(test_user),
            acting_user_id=test_user.id,
            acting_user_email=test_user.email,
            reason=None,
            db=db_session,
        )
        assert ok is True
        assert error_code is None

        ok, error_code = await restore_team(
            team_id=test_team.id,
            company_id=get_company_filter(test_user),
            acting_user_id=test_user.id,
            acting_user_email=test_user.email,
            db=db_session,
        )
        assert ok is True
        assert error_code is None

        team = await db_session.scalar(select(Team).where(Team.id == test_team.id))
        assert team is not None
        assert team.deleted_at is None

        ok, error_code = await restore_team(
            team_id=test_team.id,
            company_id=get_company_filter(test_user),
            acting_user_id=test_user.id,
            acting_user_email=test_user.email,
            db=db_session,
        )
        assert ok is False
        assert error_code == "not_deleted"
