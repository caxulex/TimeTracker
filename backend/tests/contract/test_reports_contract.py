# ============================================
# CONTRACT TESTS — Report / Dashboard endpoints
#
# Validates GET /api/reports/dashboard → DashboardStats
# Validates GET /api/reports/weekly → WeeklySummary
#
# References:
#   frontend/src/types/index.ts: DashboardStats, WeeklySummary, DailySummary
# ============================================
import pytest

from .conftest import validate_dashboard_stats_shape, validate_weekly_summary_shape


class TestDashboardStatsContract:
    """GET /api/reports/dashboard must match DashboardStats interface."""

    def test_dashboard_stats_complete(self):
        stats = {
            "today_seconds": 28800,
            "week_seconds": 144000,
            "month_seconds": 576000,
            "active_projects": 3,
            "running_timer": None,
        }
        validate_dashboard_stats_shape(stats)

    def test_dashboard_stats_with_running_timer(self):
        stats = {
            "today_seconds": 3600,
            "week_seconds": 3600,
            "month_seconds": 3600,
            "active_projects": 1,
            "running_timer": {
                "id": 1,
                "user_id": 1,
                "start_time": "2025-01-15T09:00:00Z",
                "end_time": None,
            },
        }
        validate_dashboard_stats_shape(stats)

    def test_dashboard_stats_with_float_seconds(self):
        stats = {
            "today_seconds": 28800.5,
            "week_seconds": 144000.0,
            "month_seconds": 576000,
            "active_projects": 3,
        }
        validate_dashboard_stats_shape(stats)

    def test_dashboard_rejects_missing_today_seconds(self):
        stats = {"week_seconds": 144000, "month_seconds": 576000, "active_projects": 3}
        with pytest.raises(AssertionError, match="today_seconds"):
            validate_dashboard_stats_shape(stats)

    def test_dashboard_rejects_wrong_type_active_projects(self):
        stats = {
            "today_seconds": 0,
            "week_seconds": 0,
            "month_seconds": 0,
            "active_projects": "three",
        }
        with pytest.raises(AssertionError):
            validate_dashboard_stats_shape(stats)


class TestWeeklySummaryContract:
    """GET /api/reports/weekly must match WeeklySummary interface."""

    def test_weekly_summary_complete(self):
        summary = {
            "week_start": "2025-01-13",
            "week_end": "2025-01-19",
            "total_seconds": 144000,
            "total_hours": 40.0,
            "daily_breakdown": [
                {"date": "2025-01-13", "total_seconds": 28800, "entry_count": 3},
                {"date": "2025-01-14", "total_seconds": 28800, "entry_count": 2},
                {"date": "2025-01-15", "total_seconds": 28800, "entry_count": 4},
                {"date": "2025-01-16", "total_seconds": 28800, "entry_count": 3},
                {"date": "2025-01-17", "total_seconds": 28800, "entry_count": 5},
                {"date": "2025-01-18", "total_seconds": 0, "entry_count": 0},
                {"date": "2025-01-19", "total_seconds": 0, "entry_count": 0},
            ],
        }
        validate_weekly_summary_shape(summary)

    def test_weekly_summary_empty_week(self):
        summary = {
            "week_start": "2025-01-13",
            "week_end": "2025-01-19",
            "total_seconds": 0,
            "total_hours": 0.0,
            "daily_breakdown": [],
        }
        validate_weekly_summary_shape(summary)

    def test_weekly_rejects_missing_daily_breakdown(self):
        summary = {
            "week_start": "2025-01-13",
            "week_end": "2025-01-19",
            "total_seconds": 0,
            "total_hours": 0.0,
        }
        with pytest.raises(AssertionError, match="daily_breakdown"):
            validate_weekly_summary_shape(summary)

    def test_daily_breakdown_rejects_wrong_entry_count_type(self):
        summary = {
            "week_start": "2025-01-13",
            "week_end": "2025-01-19",
            "total_seconds": 100,
            "total_hours": 0.03,
            "daily_breakdown": [
                {"date": "2025-01-13", "total_seconds": 100, "entry_count": "three"},
            ],
        }
        with pytest.raises(AssertionError):
            validate_weekly_summary_shape(summary)
