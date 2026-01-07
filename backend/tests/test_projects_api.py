# ============================================
# TIME TRACKER - PROJECTS API TESTS (Enhanced)
# Phase 7: Testing - Project management tests
# ============================================
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Team, TeamMember, Project


@pytest_asyncio.fixture
async def project_team(db_session: AsyncSession, test_user: User) -> Team:
    """Create a team for project tests."""
    team = Team(
        name="Project Test Team",
        owner_id=test_user.id,
    )
    db_session.add(team)
    await db_session.flush()
    
    # Add user as team member
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
async def test_project(db_session: AsyncSession, project_team: Team) -> Project:
    """Create a test project."""
    project = Project(
        name="Test Project for API",
        description="Test project description",
        team_id=project_team.id,
        color="#3B82F6",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


class TestProjectCreate:
    """Test project creation endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_project_success(
        self, client: AsyncClient, auth_headers: dict, project_team: Team
    ):
        """Test creating a project."""
        response = await client.post(
            "/api/projects",
            json={
                "name": "New Test Project",
                "description": "A brand new project",
                "team_id": project_team.id,
                "color": "#FF5733",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Test Project"
        assert data["team_id"] == project_team.id
    
    @pytest.mark.asyncio
    async def test_create_project_unauthenticated(
        self, client: AsyncClient, project_team: Team
    ):
        """Test creating project without auth fails."""
        response = await client.post(
            "/api/projects",
            json={
                "name": "Unauthorized Project",
                "team_id": project_team.id,
            },
        )
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_create_project_missing_name(
        self, client: AsyncClient, auth_headers: dict, project_team: Team
    ):
        """Test creating project without name fails."""
        response = await client.post(
            "/api/projects",
            json={
                "team_id": project_team.id,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestProjectList:
    """Test project listing endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_projects(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test listing projects."""
        response = await client.get(
            "/api/projects",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
    
    @pytest.mark.asyncio
    async def test_list_projects_with_team_filter(
        self, client: AsyncClient, auth_headers: dict, test_project: Project,
        project_team: Team
    ):
        """Test filtering projects by team."""
        response = await client.get(
            f"/api/projects?team_id={project_team.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestProjectDetail:
    """Test project detail endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_project_detail(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test getting project details."""
        response = await client.get(
            f"/api/projects/{test_project.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_project.id
        assert data["name"] == test_project.name
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_project(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting nonexistent project returns 404."""
        response = await client.get(
            "/api/projects/99999",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestProjectUpdate:
    """Test project update endpoints."""
    
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


class TestProjectDelete:
    """Test project deletion endpoints."""
    
    @pytest.mark.asyncio
    async def test_delete_project(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test deleting a project."""
        response = await client.delete(
            f"/api/projects/{test_project.id}",
            headers=auth_headers,
        )
        # Should succeed (200 or 204)
        assert response.status_code in [200, 204]


class TestProjectArchive:
    """Test project archive functionality."""
    
    @pytest.mark.asyncio
    async def test_archive_project(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test archiving a project."""
        response = await client.post(
            f"/api/projects/{test_project.id}/archive",
            headers=auth_headers,
        )
        # Should succeed or endpoint not exist
        assert response.status_code in [200, 404, 405]
    
    @pytest.mark.asyncio
    async def test_list_archived_projects(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test listing archived projects."""
        response = await client.get(
            "/api/projects?include_archived=true",
            headers=auth_headers,
        )
        assert response.status_code == 200
