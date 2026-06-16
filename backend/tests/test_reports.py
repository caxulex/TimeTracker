# ============================================
# TIME TRACKER - REPORTS API TESTS
# ============================================
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Team, TeamMember, TimeEntry, User
from app.routers.reports import get_team_analytics
from app.services.team_service import soft_delete_team


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


class TestAdminTeamAnalyticsList:
    """Test admin team analytics list filtering behavior."""

    @pytest.mark.asyncio
    async def test_admin_teams_includes_active_team(
        self,
        admin_user: User,
        db_session: AsyncSession,
    ):
        """Active teams should be visible in /api/reports/admin/teams."""
        active_team = Team(
            name="Active Team",
            owner_id=admin_user.id,
            company_id=admin_user.company_id,
        )
        db_session.add(active_team)
        await db_session.flush()

        db_session.add(
            TeamMember(team_id=active_team.id, user_id=admin_user.id, role="owner")
        )

        project = Project(
            name="Active Team Project",
            team_id=active_team.id,
            color="#3B82F6",
        )
        db_session.add(project)
        await db_session.flush()

        now = datetime.now(timezone.utc)
        db_session.add(
            TimeEntry(
                user_id=admin_user.id,
                project_id=project.id,
                description="active team entry",
                start_time=now - timedelta(hours=2),
                end_time=now - timedelta(hours=1),
                duration_seconds=3600,
                is_running=False,
            )
        )
        await db_session.commit()

        data = await get_team_analytics(db=db_session, current_user=admin_user, tz="UTC")
        names = [item.team_name for item in data]
        assert "Active Team" in names

    @pytest.mark.asyncio
    async def test_admin_teams_excludes_soft_deleted_team(
        self,
        admin_user: User,
        db_session: AsyncSession,
    ):
        """Soft-deleted teams should not be visible in /api/reports/admin/teams."""
        active_team = Team(
            name="Visible Team",
            owner_id=admin_user.id,
            company_id=admin_user.company_id,
        )
        deleted_team = Team(
            name="Soft Delete Test Team",
            owner_id=admin_user.id,
            company_id=admin_user.company_id,
        )
        db_session.add_all([active_team, deleted_team])
        await db_session.flush()

        db_session.add_all(
            [
                TeamMember(team_id=active_team.id, user_id=admin_user.id, role="owner"),
                TeamMember(team_id=deleted_team.id, user_id=admin_user.id, role="owner"),
            ]
        )
        await db_session.commit()

        ok, error_code = await soft_delete_team(
            team_id=deleted_team.id,
            company_id=admin_user.company_id,
            acting_user_id=admin_user.id,
            acting_user_email=admin_user.email,
            reason="test soft delete",
            db=db_session,
        )
        assert ok is True
        assert error_code is None

        deleted_at = (
            await db_session.execute(select(Team.deleted_at).where(Team.id == deleted_team.id))
        ).scalar_one()
        assert deleted_at is not None

        active_ids_query = (
            await db_session.execute(select(Team.id).where(Team.deleted_at.is_(None)))
        ).scalars().all()
        assert deleted_team.id not in active_ids_query

        data = await get_team_analytics(db=db_session, current_user=admin_user, tz="UTC")
        ids = [item.team_id for item in data]
        assert active_team.id in ids
        assert deleted_team.id not in ids


class TestTeamTimesheetPauseAware:
    """Integration test: team-timesheet must exclude pause time (fix lives in helpers)."""

    @pytest.mark.asyncio
    async def test_team_timesheet_subtracts_pause_seconds(
        self,
        client: AsyncClient,
        admin_auth_headers: dict,
        admin_user: User,
        db_session: AsyncSession,
    ):
        """Entry with a 1h48m break should display 4:46 (duration_seconds), not 6:34 (wall-clock).

        Reproduces production case (user_id=7 Laura on 2026-05-20) at the test level.
        """
        # Use a fixed past day to avoid timezone/today edge cases.
        day = datetime(2026, 5, 20, tzinfo=timezone.utc)
        # 09:00 -> 15:34 wall-clock = 6h34m = 23640s; 1h48m pause = 6480s.
        # Stored duration = 23640 - 6480 = 17160s = 4h46m.
        entry = TimeEntry(
            user_id=admin_user.id,
            description="With long lunch",
            start_time=day.replace(hour=9, minute=0, second=0, microsecond=0),
            end_time=day.replace(hour=15, minute=34, second=0, microsecond=0),
            duration_seconds=17160,
            pause_seconds=6480,
            is_running=False,
        )
        db_session.add(entry)
        await db_session.flush()

        response = await client.get(
            "/api/reports/team-timesheet?start_date=2026-05-20&end_date=2026-05-20",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Find the admin row
        row = next(u for u in data["users"] if u["user_id"] == admin_user.id)
        assert row["total_seconds"] == 17160
        assert row["total_formatted"] == "4:46"

        # Per-day cell matches
        cell = next(d for d in row["daily_hours"] if d["date"] == "2026-05-20")
        assert cell["seconds"] == 17160
        assert cell["formatted"] == "4:46"

        # Grand total should be pause-corrected
        assert data["grand_total_seconds"] == 17160


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
