from datetime import date

import pytest

from app.ai.services.team_analytics_service import TeamAnalyticsService, TeamVelocity


def _velocity_point(total_hours: float) -> TeamVelocity:
    return TeamVelocity(
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 7),
        total_hours=total_hours,
        hours_per_member=0,
        tasks_completed=0,
        projects_active=0,
        avg_task_duration_hours=0,
        velocity_trend="stable",
        change_percent=0,
    )


def test_compute_measurability_flags_thin_data() -> None:
    flags = TeamAnalyticsService._compute_measurability_flags(
        velocity_history=[_velocity_point(12.0)],
        active_members=1,
        task_count=0,
    )

    velocity_measured, collaboration_measured, workload_balance_measured, task_tracking_measured = flags

    assert velocity_measured is False
    assert collaboration_measured is False
    assert workload_balance_measured is False
    assert task_tracking_measured is False


def test_compute_measurability_flags_measured_data() -> None:
    flags = TeamAnalyticsService._compute_measurability_flags(
        velocity_history=[_velocity_point(12.0), _velocity_point(8.0)],
        active_members=2,
        task_count=5,
    )

    velocity_measured, collaboration_measured, workload_balance_measured, task_tracking_measured = flags

    assert velocity_measured is True
    assert collaboration_measured is True
    assert workload_balance_measured is True
    assert task_tracking_measured is True


def test_determine_current_velocity_trend_uses_not_measured_sentinel_when_unmeasured() -> None:
    trend = TeamAnalyticsService._determine_current_velocity_trend(
        velocity_history=[_velocity_point(12.0)],
        velocity_measured=False,
    )

    assert trend == "not_measured"


def test_determine_current_velocity_trend_returns_real_label_when_measured() -> None:
    trend = TeamAnalyticsService._determine_current_velocity_trend(
        velocity_history=[_velocity_point(10.0), _velocity_point(15.0)],
        velocity_measured=True,
    )

    assert trend == "increasing"


@pytest.mark.asyncio
async def test_generate_ai_insights_respects_unmeasured_axis_flags() -> None:
    service = TeamAnalyticsService(db=None)

    insights, recommendations = await service._generate_ai_insights(
        team_name="Core Team",
        member_metrics=[],
        velocity_history=[_velocity_point(12.0)],
        workload_gini=0.85,
        collaboration_density=0.95,
        velocity_measured=False,
        collaboration_measured=False,
        workload_balance_measured=False,
        task_tracking_measured=False,
    )

    combined = " ".join(insights + recommendations).lower()
    assert "increasing" not in combined
    assert "decreasing" not in combined
    assert "workload is unevenly distributed" not in combined
    assert "collaboration is low" not in combined
    assert "task completion is not tracked" in combined


@pytest.mark.asyncio
async def test_generate_ai_insights_allows_axis_claims_when_measured() -> None:
    service = TeamAnalyticsService(db=None)

    decreasing_point = _velocity_point(8.0)
    decreasing_point.velocity_trend = "decreasing"

    insights, recommendations = await service._generate_ai_insights(
        team_name="Core Team",
        member_metrics=[],
        velocity_history=[_velocity_point(12.0), decreasing_point],
        workload_gini=0.6,
        collaboration_density=0.2,
        velocity_measured=True,
        collaboration_measured=True,
        workload_balance_measured=True,
        task_tracking_measured=True,
    )

    combined = " ".join(insights + recommendations).lower()
    assert "workload is unevenly distributed" in combined
    assert "collaboration is low" in combined
    assert "logged hours have been decreasing recently" in combined
    assert "task completion is not tracked" not in combined
