# ============================================
# TIME TRACKER - TIME ENTRIES API TESTS
# ============================================
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Project, Team, TeamMember, TimeEntry


@pytest_asyncio.fixture
async def test_team(db_session: AsyncSession, test_user: User) -> Team:
    """Create a test team."""
    team = Team(
        name="Time Entry Test Team",
        owner_id=test_user.id,
    )
    db_session.add(team)
    await db_session.flush()
    
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
    """Create a test project for time entries."""
    project = Project(
        name="Time Test Project",
        description="Project for time entry tests",
        team_id=test_team.id,
        color="#3B82F6",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def test_time_entry(
    db_session: AsyncSession, test_user: User, test_project: Project
) -> TimeEntry:
    """Create a completed test time entry."""
    now = datetime.now(timezone.utc)
    entry = TimeEntry(
        user_id=test_user.id,
        project_id=test_project.id,
        description="Test time entry",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=1),
        duration_seconds=3600,
        is_running=False,
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    return entry


@pytest_asyncio.fixture
async def running_time_entry(
    db_session: AsyncSession, test_user: User, test_project: Project
) -> TimeEntry:
    """Create a running (no end_time) time entry."""
    entry = TimeEntry(
        user_id=test_user.id,
        project_id=test_project.id,
        description="Running time entry",
        start_time=datetime.now(timezone.utc) - timedelta(minutes=30),
        end_time=None,
        duration_seconds=None,
        is_running=True,
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    return entry


class TestTimeEntryCreate:
    """Test time entry creation endpoint."""
    
    @pytest.mark.asyncio
    async def test_create_time_entry_with_duration(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test creating a time entry with duration."""
        response = await client.post(
            "/api/time",
            json={
                "project_id": test_project.id,
                "description": "Working on feature",
                "duration_seconds": 3600,  # 1 hour
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["project_id"] == test_project.id
        assert data["description"] == "Working on feature"
    
    @pytest.mark.asyncio
    async def test_create_time_entry_unauthenticated(
        self, client: AsyncClient, test_project: Project
    ):
        """Test creating time entry without authentication fails."""
        response = await client.post(
            "/api/time",
            json={
                "project_id": test_project.id,
                "description": "Test",
                "duration_seconds": 3600,
            },
        )
        # HTTPBearer returns 403 when no credentials
        assert response.status_code == 403


class TestTimeEntryList:
    """Test time entry listing endpoint."""
    
    @pytest.mark.asyncio
    async def test_list_time_entries(
        self, client: AsyncClient, auth_headers: dict, test_time_entry: TimeEntry
    ):
        """Test listing time entries."""
        response = await client.get("/api/time", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
    
    @pytest.mark.asyncio
    async def test_list_time_entries_with_project_filter(
        self, client: AsyncClient, auth_headers: dict, test_time_entry: TimeEntry,
        test_project: Project
    ):
        """Test listing time entries with project filter."""
        response = await client.get(
            f"/api/time?project_id={test_project.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestTimerOperations:
    """Test timer start/stop endpoints."""
    
    @pytest.mark.asyncio
    async def test_start_timer(
        self, client: AsyncClient, auth_headers: dict, test_project: Project
    ):
        """Test starting a timer."""
        response = await client.post(
            "/api/time/start",
            json={
                "project_id": test_project.id,
                "description": "Starting new task",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_running"] is True
    
    @pytest.mark.asyncio
    async def test_stop_timer(
        self, client: AsyncClient, auth_headers: dict, running_time_entry: TimeEntry
    ):
        """Test stopping a running timer."""
        response = await client.post(
            "/api/time/stop",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is False
        assert data["end_time"] is not None


class TestTimerStatus:
    """Test timer status endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_timer_status_running(
        self, client: AsyncClient, auth_headers: dict, running_time_entry: TimeEntry
    ):
        """Test getting timer status when running."""
        response = await client.get(
            "/api/time/timer",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is True
    
    @pytest.mark.asyncio
    async def test_get_timer_status_not_running(
        self, client: AsyncClient, auth_headers: dict, test_time_entry: TimeEntry
    ):
        """Test getting timer status when not running."""
        response = await client.get(
            "/api/time/timer",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is False


class TestTimeEntryUpdate:
    """Test time entry update endpoint."""
    
    @pytest.mark.asyncio
    async def test_update_time_entry(
        self, client: AsyncClient, auth_headers: dict, test_time_entry: TimeEntry
    ):
        """Test updating a time entry."""
        response = await client.put(
            f"/api/time/{test_time_entry.id}",
            json={"description": "Updated description"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"


class TestTimeEntryDelete:
    """Test time entry deletion endpoint."""
    
    @pytest.mark.asyncio
    async def test_delete_time_entry(
        self, client: AsyncClient, auth_headers: dict, test_time_entry: TimeEntry
    ):
        """Test deleting a time entry."""
        response = await client.delete(
            f"/api/time/{test_time_entry.id}",
            headers=auth_headers,
        )
        # Check for successful deletion (200 or 204)
        assert response.status_code in [200, 204]
