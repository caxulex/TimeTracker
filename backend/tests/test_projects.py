# ============================================
# TIME TRACKER - PROJECTS API TESTS
# ============================================
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Project, Team, TeamMember, User
from app.services.auth_service import AuthService


@pytest_asyncio.fixture
async def test_team(db_session: AsyncSession, test_user: User) -> Team:
    """Create a test team."""
    team = Team(
        name="Test Team",
        owner_id=test_user.id,
    )
    db_session.add(team)
    await db_session.flush()
    
    # Add owner as team member
    membership = TeamMember(
        team_id=team.id,
        user_id=test_user.id,
        role="owner",
    )
    db_session.add(membership)
    await db_session.flush()
    await db_session.refresh(team)
    return team


@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession, test_user: User, test_team: Team) -> Project:
    """Create a test project."""
    project = Project(
        name="Test Project",
        description="A test project description",
        color="#3B82F6",
        team_id=test_team.id,
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


def _headers_for(user: User) -> dict[str, str]:
    token = AuthService.create_access_token({"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


async def _make_company(db_session: AsyncSession, name: str) -> Company:
    company = Company(
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{uuid4().hex[:6]}",
        email=f"{uuid4().hex[:8]}@example.com",
    )
    db_session.add(company)
    await db_session.flush()
    return company


async def _make_user(db_session: AsyncSession, company_id: int, role: str = "regular_user") -> User:
    user = User(
        email=f"user-{uuid4().hex[:8]}@example.com",
        name="User",
        password_hash=AuthService.hash_password("testpassword123"),
        role=role,
        is_active=True,
        company_id=company_id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _make_team(db_session: AsyncSession, owner: User, name: str, company_id: int) -> Team:
    team = Team(name=name, owner_id=owner.id, company_id=company_id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=owner.id, role="owner"))
    await db_session.flush()
    return team


async def _make_project(db_session: AsyncSession, team: Team, name: str) -> Project:
    project = Project(name=name, description="", color="#3B82F6", team_id=team.id)
    db_session.add(project)
    await db_session.flush()
    return project


class TestProjectCreate:
    """Test project creation endpoint."""
    
    @pytest.mark.asyncio
    async def test_create_project_success(
        self, client: AsyncClient, auth_headers: dict, test_team: Team
    ):
        """Test successful project creation."""
        response = await client.post(
            "/api/projects",
            json={
                "name": "New Project",
                "description": "A new project",
                "color": "#10B981",
                "team_id": test_team.id,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Project"
        assert data["description"] == "A new project"
        assert data["color"] == "#10B981"
    
    @pytest.mark.asyncio
    async def test_create_project_minimal(
        self, client: AsyncClient, auth_headers: dict, test_team: Team
    ):
        """Test project creation with minimal data."""
        response = await client.post(
            "/api/projects",
            json={"name": "Minimal Project", "team_id": test_team.id},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Project"
    
    @pytest.mark.asyncio
    async def test_create_project_unauthenticated(self, client: AsyncClient):
        """Test project creation without authentication fails."""
        response = await client.post(
            "/api/projects",
            json={"name": "New Project", "team_id": 1},
        )
        # HTTPBearer returns 403 when no credentials
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_project_under_deleted_team_fails(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_team: Team,
    ):
        test_team.deleted_at = datetime.now(timezone.utc)
        await db_session.commit()

        response = await client.post(
            "/api/projects",
            json={
                "name": "Blocked by Deleted Team",
                "team_id": test_team.id,
            },
            headers=auth_headers,
        )
        assert response.status_code == 409
        assert "deleted" in response.json()["detail"].lower()


class TestProjectList:
    """Test project listing endpoint."""
    
    @pytest.mark.asyncio
    async def test_list_projects(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test listing projects."""
        response = await client.get("/api/projects", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
    
    @pytest.mark.asyncio
    async def test_list_projects_unauthenticated(self, client: AsyncClient):
        """Test listing projects without authentication fails."""
        response = await client.get("/api/projects")
        # HTTPBearer returns 403 when no credentials
        assert response.status_code == 403


class TestProjectGet:
    """Test get single project endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_project(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test getting a single project."""
        response = await client.get(
            f"/api/projects/{test_project.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_project.name
        assert data["id"] == test_project.id
    
    @pytest.mark.asyncio
    async def test_get_project_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting a nonexistent project fails."""
        response = await client.get(
            "/api/projects/99999",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestProjectUpdate:
    """Test project update endpoint."""
    
    @pytest.mark.asyncio
    async def test_update_project(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test updating a project."""
        response = await client.put(
            f"/api/projects/{test_project.id}",
            json={
                "name": "Updated Project Name",
                "description": "Updated description",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Project Name"
        assert data["description"] == "Updated description"
    
    @pytest.mark.asyncio
    async def test_update_project_partial(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test partial project update."""
        response = await client.put(
            f"/api/projects/{test_project.id}",
            json={"name": "New Name Only"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name Only"

    @pytest.mark.asyncio
    async def test_move_project_to_deleted_team_fails(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_project: Project,
    ):
        deleted_team = Team(name="Deleted Team", owner_id=test_user.id)
        db_session.add(deleted_team)
        await db_session.flush()
        db_session.add(
            TeamMember(team_id=deleted_team.id, user_id=test_user.id, role="owner")
        )
        deleted_team.deleted_at = datetime.now(timezone.utc)
        await db_session.commit()

        response = await client.put(
            f"/api/projects/{test_project.id}",
            json={"team_id": deleted_team.id},
            headers=auth_headers,
        )
        assert response.status_code == 409
        assert "deleted" in response.json()["detail"].lower()


class TestProjectDelete:
    """Test project deletion endpoint."""
    
    @pytest.mark.asyncio
    async def test_delete_project(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test permanently deleting a project."""
        response = await client.delete(
            f"/api/projects/{test_project.id}",
            headers=auth_headers,
        )
        # API permanently deletes the project and returns 200 with message
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        
        # Verify project is permanently deleted (returns 404)
        get_response = await client.get(
            f"/api/projects/{test_project.id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_list_projects_non_admin_sees_all_company_projects(
    client: AsyncClient,
    db_session: AsyncSession,
):
    company = await _make_company(db_session, "Acme")
    owner = await _make_user(db_session, company_id=company.id)
    member = await _make_user(db_session, company_id=company.id)

    owner_team = await _make_team(db_session, owner, "Engineering", company.id)
    member_team = await _make_team(db_session, member, "Operations", company.id)

    owner_project = await _make_project(db_session, owner_team, "Owned by Engineering")
    member_project = await _make_project(db_session, member_team, "Owned by Operations")
    await db_session.commit()

    response = await client.get("/api/projects", headers=_headers_for(member))
    assert response.status_code == 200
    visible_ids = {row["id"] for row in response.json()["items"]}
    assert owner_project.id in visible_ids
    assert member_project.id in visible_ids


@pytest.mark.asyncio
async def test_list_projects_company_isolation_preserved(
    client: AsyncClient,
    db_session: AsyncSession,
):
    company_a = await _make_company(db_session, "Company A")
    company_b = await _make_company(db_session, "Company B")

    user_a = await _make_user(db_session, company_id=company_a.id)
    user_b = await _make_user(db_session, company_id=company_b.id)

    team_a = await _make_team(db_session, user_a, "A Team", company_a.id)
    team_b = await _make_team(db_session, user_b, "B Team", company_b.id)

    project_a = await _make_project(db_session, team_a, "Project A")
    project_b = await _make_project(db_session, team_b, "Project B")
    await db_session.commit()

    response = await client.get("/api/projects", headers=_headers_for(user_a))
    assert response.status_code == 200
    visible_ids = {row["id"] for row in response.json()["items"]}
    assert project_a.id in visible_ids
    assert project_b.id not in visible_ids


@pytest.mark.asyncio
async def test_create_time_entry_still_requires_team_access(
    client: AsyncClient,
    db_session: AsyncSession,
):
    company = await _make_company(db_session, "Time Access Co")
    project_owner = await _make_user(db_session, company_id=company.id)
    member = await _make_user(db_session, company_id=company.id)

    owner_team = await _make_team(db_session, project_owner, "Owner Team", company.id)
    member_team = await _make_team(db_session, member, "Member Team", company.id)
    project = await _make_project(db_session, owner_team, "Needs Association")
    await db_session.commit()

    list_response = await client.get("/api/projects", headers=_headers_for(member))
    assert list_response.status_code == 200
    assert project.id in {row["id"] for row in list_response.json()["items"]}

    create_timer = await client.post(
        "/api/time/start",
        json={"project_id": project.id, "description": "Should fail before association"},
        headers=_headers_for(member),
    )
    assert create_timer.status_code in (403, 404)
    assert "access denied" in create_timer.json()["detail"].lower()


@pytest.mark.asyncio
async def test_add_to_team_then_create_time_entry(
    client: AsyncClient,
    db_session: AsyncSession,
):
    company = await _make_company(db_session, "Onboarding Co")
    project_owner = await _make_user(db_session, company_id=company.id)
    member = await _make_user(db_session, company_id=company.id)

    owner_team = await _make_team(db_session, project_owner, "Owner Team", company.id)
    member_team = await _make_team(db_session, member, "Member Team", company.id)
    project = await _make_project(db_session, owner_team, "Shared Later")
    await db_session.commit()

    list_response = await client.get("/api/projects", headers=_headers_for(member))
    assert list_response.status_code == 200
    assert project.id in {row["id"] for row in list_response.json()["items"]}

    add_response = await client.post(
        f"/api/projects/{project.id}/teams",
        json={"team_id": member_team.id},
        headers=_headers_for(member),
    )
    assert add_response.status_code == 201

    create_timer = await client.post(
        "/api/time/start",
        json={"project_id": project.id, "description": "Works after add-to-team"},
        headers=_headers_for(member),
    )
    assert create_timer.status_code == 201
