"""Tests for search + analytics endpoint status codes (PR-D)."""

from datetime import date, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient


# ============================================================
# /search/similar-tasks
# ============================================================

@pytest.mark.asyncio
async def test_search_similar_tasks_422_empty_query(client: AsyncClient, auth_headers: dict):
    """Empty query violates min_length=1 → 422."""
    response = await client.post(
        "/api/ai/search/similar-tasks",
        json={"query": ""},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_similar_tasks_422_limit_out_of_bounds(client: AsyncClient, auth_headers: dict):
    """limit > 50 violates le=50 → 422."""
    response = await client.post(
        "/api/ai/search/similar-tasks",
        json={"query": "valid query", "limit": 51},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_similar_tasks_503_service_exception(client: AsyncClient, auth_headers: dict):
    """Service exception → 503."""
    with patch(
        "app.ai.services.semantic_search_service.SemanticSearchService.search_similar_tasks"
    ) as mock_search:
        mock_search.side_effect = RuntimeError("search exploded")
        response = await client.post(
            "/api/ai/search/similar-tasks",
            json={"query": "some task"},
            headers=auth_headers,
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_search_similar_tasks_200_valid_results(client: AsyncClient, auth_headers: dict):
    """Successful search returns 200+success=true."""
    from app.ai.services.semantic_search_service import SearchResult, SimilarTask

    with patch(
        "app.ai.services.semantic_search_service.SemanticSearchService.search_similar_tasks"
    ) as mock_search:
        mock_search.return_value = SearchResult(
            query="some task",
            results=[],
            search_time_ms=1.5,
            method="keyword",
        )
        response = await client.post(
            "/api/ai/search/similar-tasks",
            json={"query": "some task"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["success"] is True


# ============================================================
# /search/time-suggestions
# ============================================================

@pytest.mark.asyncio
async def test_search_time_suggestions_422_invalid_hour(client: AsyncClient, auth_headers: dict):
    """hour > 23 violates le=23 → 422."""
    response = await client.post(
        "/api/ai/search/time-suggestions",
        json={"hour": 25, "day_of_week": 0},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_time_suggestions_422_invalid_day(client: AsyncClient, auth_headers: dict):
    """day_of_week > 6 violates le=6 → 422."""
    response = await client.post(
        "/api/ai/search/time-suggestions",
        json={"hour": 9, "day_of_week": 7},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_time_suggestions_503_service_exception(client: AsyncClient, auth_headers: dict):
    """Service exception → 503."""
    with patch(
        "app.ai.services.semantic_search_service.SemanticSearchService.get_task_suggestions_for_time"
    ) as mock_suggest:
        mock_suggest.side_effect = RuntimeError("time suggestion exploded")
        response = await client.post(
            "/api/ai/search/time-suggestions",
            json={"hour": 9, "day_of_week": 1},
            headers=auth_headers,
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_search_time_suggestions_200_empty_results(client: AsyncClient, auth_headers: dict):
    """No matching suggestions (empty list) is a valid 200+success=true."""
    with patch(
        "app.ai.services.semantic_search_service.SemanticSearchService.get_task_suggestions_for_time"
    ) as mock_suggest:
        mock_suggest.return_value = []
        response = await client.post(
            "/api/ai/search/time-suggestions",
            json={"hour": 9, "day_of_week": 1},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["success"] is True


# ============================================================
# /analytics/team
# ============================================================

@pytest.mark.asyncio
async def test_analytics_team_422_invalid_period_days(client: AsyncClient, admin_auth_headers: dict):
    """period_days < 7 violates ge=7 → 422."""
    response = await client.post(
        "/api/ai/analytics/team",
        json={"team_id": 1, "period_days": 3},
        headers=admin_auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analytics_team_403_non_admin(client: AsyncClient, auth_headers: dict):
    """Non-admin user → 403 (role dependency)."""
    response = await client.post(
        "/api/ai/analytics/team",
        json={"team_id": 1, "period_days": 30},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_analytics_team_400_team_not_found(client: AsyncClient, admin_auth_headers: dict):
    """Service raises ValueError (team not found) → 400."""
    with patch(
        "app.ai.services.team_analytics_service.TeamAnalyticsService.generate_team_report"
    ) as mock_report:
        mock_report.side_effect = ValueError("Team 999 not found")
        response = await client.post(
            "/api/ai/analytics/team",
            json={"team_id": 999, "period_days": 30},
            headers=admin_auth_headers,
        )
    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_analytics_team_503_service_exception(client: AsyncClient, admin_auth_headers: dict):
    """Unexpected service exception → 503."""
    with patch(
        "app.ai.services.team_analytics_service.TeamAnalyticsService.generate_team_report"
    ) as mock_report:
        mock_report.side_effect = RuntimeError("db connection lost")
        response = await client.post(
            "/api/ai/analytics/team",
            json={"team_id": 1, "period_days": 30},
            headers=admin_auth_headers,
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_analytics_team_200_thin_data_measured_false_keep200(
    client: AsyncClient, admin_auth_headers: dict
):
    """
    KEEP-200: thin-data / one-member team with all measurability flags False
    returns 200+success=true. This guards the Monday "Not tracked" honesty work.

    velocity_measured=False, collaboration_measured=False,
    workload_balance_measured=False, task_tracking_measured=False all flow
    through the SUCCESS return path — they cannot reach the 400/503 branches.
    """
    from app.ai.services.team_analytics_service import TeamAnalyticsReport

    thin_report = TeamAnalyticsReport(
        team_id=1,
        team_name="Solo Team",
        period_days=30,
        total_members=1,
        active_members=1,
        total_hours=0.0,
        avg_hours_per_member=0.0,
        total_projects=0,
        total_tasks=0,
        member_metrics=[],
        velocity_history=[],
        current_velocity_trend="not_measured",
        velocity_measured=False,
        collaboration_edges=[],
        collaboration_density=0.0,
        collaboration_measured=False,
        workload_gini=0.0,
        workload_balance_measured=False,
        top_contributors=[],
        underutilized_members=[],
        task_tracking_measured=False,
        ai_insights=[],
        recommendations=[],
        generated_at=datetime.utcnow(),
    )

    with patch(
        "app.ai.services.team_analytics_service.TeamAnalyticsService.generate_team_report"
    ) as mock_report:
        mock_report.return_value = thin_report
        response = await client.post(
            "/api/ai/analytics/team",
            json={"team_id": 1, "period_days": 30},
            headers=admin_auth_headers,
        )

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["velocity_measured"] is False
    assert body["collaboration_measured"] is False
    assert body["workload_balance_measured"] is False
    assert body["task_tracking_measured"] is False
    assert body["current_velocity_trend"] == "not_measured"


# ============================================================
# /analytics/compare-teams
# ============================================================

@pytest.mark.asyncio
async def test_analytics_compare_teams_422_single_team(client: AsyncClient, admin_auth_headers: dict):
    """team_ids with only 1 element violates min_length=2 → 422."""
    response = await client.post(
        "/api/ai/analytics/compare-teams",
        json={"team_ids": [1], "period_days": 30},
        headers=admin_auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analytics_compare_teams_403_non_admin(client: AsyncClient, auth_headers: dict):
    """Non-admin user → 403 (role dependency)."""
    response = await client.post(
        "/api/ai/analytics/compare-teams",
        json={"team_ids": [1, 2], "period_days": 30},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_analytics_compare_teams_503_service_exception(client: AsyncClient, admin_auth_headers: dict):
    """Unexpected service exception → 503."""
    with patch(
        "app.ai.services.team_analytics_service.TeamAnalyticsService.compare_teams"
    ) as mock_compare:
        mock_compare.side_effect = RuntimeError("compare exploded")
        response = await client.post(
            "/api/ai/analytics/compare-teams",
            json={"team_ids": [1, 2], "period_days": 30},
            headers=admin_auth_headers,
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_analytics_compare_teams_200_valid_comparison(client: AsyncClient, admin_auth_headers: dict):
    """Valid comparison returns 200+success=true."""
    from datetime import datetime as dt

    with patch(
        "app.ai.services.team_analytics_service.TeamAnalyticsService.compare_teams"
    ) as mock_compare:
        mock_compare.return_value = {
            "period_days": 30,
            "teams_compared": 2,
            "comparisons": [],
            "generated_at": dt.utcnow().isoformat(),
        }
        response = await client.post(
            "/api/ai/analytics/compare-teams",
            json={"team_ids": [1, 2], "period_days": 30},
            headers=admin_auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["success"] is True
