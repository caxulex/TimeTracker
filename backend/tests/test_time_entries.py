# ============================================
# TIME TRACKER - TIME ENTRIES API TESTS
# ============================================
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Project, Team, TeamMember, TimeEntry, WorkSession


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
    """Create a running (no end_time) time entry with an active work session."""
    # First create an active work session (required for timer to be considered running)
    work_session = WorkSession(
        user_id=test_user.id,
        company_id=test_user.company_id,
        start_time=datetime.now(timezone.utc) - timedelta(hours=1),
        status="active",
    )
    db_session.add(work_session)
    await db_session.flush()
    
    # Now create the running time entry linked to the session
    entry = TimeEntry(
        user_id=test_user.id,
        project_id=test_project.id,
        work_session_id=work_session.id,
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


class TestStopAndSwitchHonorPauseSeconds:
    """
    Regression tests for the pause_seconds bug where /stop and /switch
    persisted duration_seconds without subtracting accumulated break time.

    See PR fix/stop-endpoint-honor-pause-seconds.
    """

    @pytest_asyncio.fixture
    async def running_entry_with_pause(
        self, db_session: AsyncSession, test_user: User, test_project: Project
    ) -> TimeEntry:
        """Running entry started 1h ago, with 600s of accumulated pause time
        (i.e. user took a 10-minute break that has already ended)."""
        now = datetime.now(timezone.utc)
        work_session = WorkSession(
            user_id=test_user.id,
            company_id=test_user.company_id,
            start_time=now - timedelta(hours=2),
            status="active",
        )
        db_session.add(work_session)
        await db_session.flush()

        entry = TimeEntry(
            user_id=test_user.id,
            project_id=test_project.id,
            work_session_id=work_session.id,
            description="Entry with pause",
            start_time=now - timedelta(hours=1),
            end_time=None,
            duration_seconds=None,
            is_running=True,
            is_paused=False,
            paused_at=None,
            pause_seconds=600,
        )
        db_session.add(entry)
        await db_session.flush()
        await db_session.refresh(entry)
        return entry

    @pytest.mark.asyncio
    async def test_stop_subtracts_pause_seconds(
        self,
        client: AsyncClient,
        auth_headers: dict,
        running_entry_with_pause: TimeEntry,
    ):
        """Stopping a 1h timer with 600s pause should yield ~3000s duration."""
        response = await client.post("/api/time/stop", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Wall clock ~3600s, pause 600s → expect ~3000s. Allow small jitter
        # for execution time between fixture creation and request handling.
        assert 2990 <= data["duration_seconds"] <= 3010, (
            f"Expected ~3000s (3600 - 600), got {data['duration_seconds']}"
        )

    @pytest.mark.asyncio
    async def test_stop_with_zero_pause_unchanged(
        self,
        client: AsyncClient,
        auth_headers: dict,
        running_time_entry: TimeEntry,
    ):
        """Entries with pause_seconds=0 should still record full wall-clock duration."""
        # The running_time_entry fixture has pause_seconds default (0) and a
        # 30-minute start offset.
        response = await client.post("/api/time/stop", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Wall clock ~1800s, no pause → ~1800s.
        assert 1790 <= data["duration_seconds"] <= 1810, (
            f"Expected ~1800s with no pause, got {data['duration_seconds']}"
        )

    @pytest.mark.asyncio
    async def test_stop_clamps_when_pause_exceeds_wallclock(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        test_project: Project,
    ):
        """Defensive: pause_seconds > wall-clock should clamp to 0, not go negative."""
        now = datetime.now(timezone.utc)
        work_session = WorkSession(
            user_id=test_user.id,
            company_id=test_user.company_id,
            start_time=now - timedelta(hours=1),
            status="active",
        )
        db_session.add(work_session)
        await db_session.flush()

        entry = TimeEntry(
            user_id=test_user.id,
            project_id=test_project.id,
            work_session_id=work_session.id,
            description="Corrupt pause",
            start_time=now - timedelta(seconds=60),
            end_time=None,
            duration_seconds=None,
            is_running=True,
            is_paused=False,
            pause_seconds=99999,  # absurd, larger than wall-clock
        )
        db_session.add(entry)
        await db_session.flush()

        response = await client.post("/api/time/stop", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["duration_seconds"] == 0

    @pytest.mark.asyncio
    async def test_switch_subtracts_pause_seconds_from_old_entry(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        running_entry_with_pause: TimeEntry,
        test_team: Team,
    ):
        """Switching tasks must finalize the old entry honoring its pause_seconds."""
        # Need a second project to switch to.
        other_project = Project(
            name="Other Project",
            description="Switch target",
            team_id=test_team.id,
            color="#10B981",
        )
        db_session.add(other_project)
        await db_session.flush()
        await db_session.refresh(other_project)

        old_entry_id = running_entry_with_pause.id

        response = await client.post(
            "/api/time/switch",
            json={
                "project_id": other_project.id,
                "description": "Switched task",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Reload the old entry from the DB and verify duration honors pause.
        # Note: expire_all() is sync on AsyncSession (no await).
        db_session.expire_all()
        old_entry = await db_session.get(TimeEntry, old_entry_id)
        assert old_entry is not None
        assert old_entry.is_running is False
        assert old_entry.duration_seconds is not None
        assert 2990 <= old_entry.duration_seconds <= 3010, (
            f"Expected ~3000s (3600 - 600) on old entry, got {old_entry.duration_seconds}"
        )
