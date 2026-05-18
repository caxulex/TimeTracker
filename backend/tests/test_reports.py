# ============================================
# TIME TRACKER - REPORTS API TESTS
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
        name="Reports Test Team",
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
async def populated_data(db_session: AsyncSession, test_user: User, test_team: Team):
    """Create test data for reports."""
    # Create project
    project = Project(
        name="Report Test Project",
        team_id=test_team.id,
        color="#3B82F6",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    
    # Create time entries for the past week
    now = datetime.now(timezone.utc)
    entries = []
    for i in range(7):
        day = now - timedelta(days=i)
        entry = TimeEntry(
            user_id=test_user.id,
            project_id=project.id,
            description=f"Work day {i}",
            start_time=day.replace(hour=9, minute=0, second=0, microsecond=0),
            end_time=day.replace(hour=17, minute=0, second=0, microsecond=0),
            duration_seconds=8 * 3600,
            is_running=False,
        )
        entries.append(entry)
    
    db_session.add_all(entries)
    await db_session.flush()
    
    return {"project": project, "entries": entries}


class TestDashboardReport:
    """Test dashboard stats endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_dashboard_stats(
        self, client: AsyncClient, auth_headers: dict, populated_data
    ):
        """Test getting dashboard statistics."""
        response = await client.get("/api/reports/dashboard", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "today_seconds" in data
        assert "week_seconds" in data
        assert "month_seconds" in data


class TestWeeklySummary:
    """Test weekly summary endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_weekly_summary(
        self, client: AsyncClient, auth_headers: dict, populated_data
    ):
        """Test getting weekly summary."""
        response = await client.get("/api/reports/weekly", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_seconds" in data
        assert "daily_breakdown" in data

    @pytest.mark.asyncio
    async def test_weekly_summary_honors_end_date(
        self, client: AsyncClient, auth_headers: dict, populated_data
    ):
        """When end_date is supplied, the window spans the full caller-controlled range."""
        start = "2026-05-01"
        end = "2026-05-15"
        response = await client.get(
            f"/api/reports/weekly?start_date={start}&end_date={end}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["week_start"] == start
        assert data["week_end"] == end
        # 15 days inclusive
        assert len(data["daily_breakdown"]) == 15

    @pytest.mark.asyncio
    async def test_weekly_summary_without_end_date_is_seven_days(
        self, client: AsyncClient, auth_headers: dict, populated_data
    ):
        """Backwards compatibility: omitting end_date keeps the original 7-day window."""
        response = await client.get(
            "/api/reports/weekly?start_date=2026-05-01",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["daily_breakdown"]) == 7
        assert data["week_start"] == "2026-05-01"
        assert data["week_end"] == "2026-05-07"

    @pytest.mark.asyncio
    async def test_weekly_summary_end_before_start_returns_400(
        self, client: AsyncClient, auth_headers: dict, populated_data
    ):
        """end_date before start_date should be rejected."""
        response = await client.get(
            "/api/reports/weekly?start_date=2026-05-15&end_date=2026-05-01",
            headers=auth_headers,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_weekly_summary_range_too_large_returns_400(
        self, client: AsyncClient, auth_headers: dict, populated_data
    ):
        """Ranges exceeding 366 days should be rejected."""
        response = await client.get(
            "/api/reports/weekly?start_date=2024-01-01&end_date=2025-12-31",
            headers=auth_headers,
        )
        assert response.status_code == 400


class TestProjectReport:
    """Test project-based report endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_project_report(
        self, client: AsyncClient, auth_headers: dict, populated_data
    ):
        """Test getting report grouped by project."""
        response = await client.get("/api/reports/by-project", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestExportReport:
    """Test report export endpoint."""
    
    @pytest.mark.asyncio
    async def test_export_csv(
        self, client: AsyncClient, auth_headers: dict, populated_data
    ):
        """Test exporting report as CSV."""
        start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        response = await client.get(
            f"/api/reports/export?start_date={start}&end_date={end}&format=csv",
            headers=auth_headers,
        )
        assert response.status_code == 200
