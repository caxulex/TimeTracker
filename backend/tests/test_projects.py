# ============================================
# TIME TRACKER - PROJECTS API TESTS
# ============================================
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Project, Team, TeamMember


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


class TestProjectDelete:
    """Test project deletion (archive) endpoint."""
    
    @pytest.mark.asyncio
    async def test_delete_project(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test archiving a project."""
        response = await client.delete(
            f"/api/projects/{test_project.id}",
            headers=auth_headers,
        )
        # API archives the project and returns 200 with message
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        
        # Verify project is archived (still accessible but archived flag is true)
        get_response = await client.get(
            f"/api/projects/{test_project.id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["is_archived"] is True
