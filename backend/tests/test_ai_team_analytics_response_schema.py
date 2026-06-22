from datetime import datetime, timezone

from app.ai.schemas import TeamAnalyticsResponse


def _base_payload() -> dict:
    return {
        "success": True,
        "team_id": 7,
        "team_name": "Core Team",
        "period_days": 30,
        "total_members": 4,
        "active_members": 3,
        "total_hours": 120.0,
        "avg_hours_per_member": 30.0,
        "total_projects": 5,
        "total_tasks": 44,
        "member_metrics": [],
        "velocity_history": [],
        "current_velocity_trend": "not_measured",
        "collaboration_edges": [],
        "collaboration_density": 0.0,
        "workload_gini": 0.0,
        "top_contributors": [],
        "underutilized_members": [],
        "ai_insights": [],
        "recommendations": [],
        "generated_at": datetime(2026, 6, 22, tzinfo=timezone.utc),
    }


def test_team_analytics_response_measurability_flags_are_optional_and_omit_safe() -> None:
    response = TeamAnalyticsResponse(**_base_payload())

    assert response.velocity_measured is None
    assert response.collaboration_measured is None
    assert response.workload_balance_measured is None
    assert response.task_tracking_measured is None

    payload = response.model_dump(exclude_none=True)
    assert "velocity_measured" not in payload
    assert "collaboration_measured" not in payload
    assert "workload_balance_measured" not in payload
    assert "task_tracking_measured" not in payload


def test_team_analytics_response_accepts_measurability_flags_when_provided() -> None:
    payload = {
        **_base_payload(),
        "velocity_measured": False,
        "collaboration_measured": False,
        "workload_balance_measured": False,
        "task_tracking_measured": False,
    }

    response = TeamAnalyticsResponse(**payload)

    assert response.velocity_measured is False
    assert response.collaboration_measured is False
    assert response.workload_balance_measured is False
    assert response.task_tracking_measured is False
