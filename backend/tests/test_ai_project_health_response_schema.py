import pytest
from httpx import AsyncClient


class _FakeReportingService:
    def __init__(self, payload: dict):
        self._payload = payload

    async def generate_project_health(self, user_id: int, project_id: int) -> dict:
        result = dict(self._payload)
        result.setdefault("project_id", project_id)
        return result


@pytest.mark.asyncio
async def test_project_health_endpoint_keeps_insufficient_data_fields_when_true(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_get_reporting_service(_db):
        return _FakeReportingService(
            {
                "success": True,
                "enabled": True,
                "project_name": "Aloha",
                "health_score": None,
                "health_status": None,
                "insufficient_data": True,
                "data_thresholds": {"min_hours": 5, "min_tasks": 5},
                "metrics": {
                    "total_hours": 1.1,
                    "this_week_hours": 1.1,
                    "last_week_hours": 0,
                    "activity_trend": "new",
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "task_completion_rate": 0,
                    "contributor_count": 1,
                },
                "insights": [],
                "generated_at": "2026-06-17T12:00:00+00:00",
            }
        )

    monkeypatch.setattr("app.ai.router.get_reporting_service", fake_get_reporting_service)

    response = await client.post(
        "/api/ai/reports/project-health",
        json={"project_id": 128},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_data"] is True
    assert body["data_thresholds"] == {"min_hours": 5, "min_tasks": 5}


@pytest.mark.asyncio
async def test_project_health_endpoint_sparse_round_trip_is_insufficient(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_get_reporting_service(_db):
        return _FakeReportingService(
            {
                "success": True,
                "enabled": True,
                "project_name": "Aloha",
                "health_score": None,
                "health_status": None,
                "insufficient_data": True,
                "data_thresholds": {"min_hours": 5, "min_tasks": 5},
                "metrics": {
                    "total_hours": 1.1,
                    "this_week_hours": 1.1,
                    "last_week_hours": 0,
                    "activity_trend": "new",
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "task_completion_rate": 0,
                    "contributor_count": 1,
                    "days_with_activity": 0,
                },
                "insights": [],
                "generated_at": "2026-06-17T12:00:00+00:00",
            }
        )

    monkeypatch.setattr("app.ai.router.get_reporting_service", fake_get_reporting_service)

    response = await client.post(
        "/api/ai/reports/project-health",
        json={"project_id": 128},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_data"] is True
    assert body["metrics"]["total_hours"] == 1.1
    assert body["metrics"]["total_tasks"] == 0
    assert body["metrics"]["days_with_activity"] == 0


@pytest.mark.asyncio
async def test_project_health_endpoint_keeps_insufficient_data_field_when_false(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_get_reporting_service(_db):
        return _FakeReportingService(
            {
                "success": True,
                "enabled": True,
                "project_name": "Apollo",
                "health_score": 65,
                "health_status": "moderate",
                "insufficient_data": False,
                "data_thresholds": {"min_hours": 5, "min_tasks": 5},
                "metrics": {
                    "total_hours": 15.0,
                    "this_week_hours": 6.0,
                    "last_week_hours": 9.0,
                    "activity_trend": "decreasing",
                    "total_tasks": 5,
                    "completed_tasks": 3,
                    "task_completion_rate": 0.6,
                    "contributor_count": 2,
                },
                "insights": [],
                "generated_at": "2026-06-17T12:00:00+00:00",
            }
        )

    monkeypatch.setattr("app.ai.router.get_reporting_service", fake_get_reporting_service)

    response = await client.post(
        "/api/ai/reports/project-health",
        json={"project_id": 129},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_data"] is False
    assert body["data_thresholds"] == {"min_hours": 5, "min_tasks": 5}
    assert body["health_score"] == 65
    assert body["health_status"] == "moderate"


@pytest.mark.asyncio
async def test_project_health_endpoint_serializes_completion_measured_metric(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_get_reporting_service(_db):
        return _FakeReportingService(
            {
                "success": True,
                "enabled": True,
                "project_name": "Completion Sparse",
                "health_score": 75,
                "health_status": "moderate",
                "insufficient_data": False,
                "data_thresholds": {"min_hours": 5, "min_tasks": 5},
                "metrics": {
                    "total_hours": 12.0,
                    "this_week_hours": 4.0,
                    "last_week_hours": 6.0,
                    "activity_trend": "decreasing",
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "task_completion_rate": 0,
                    "completion_measured": False,
                    "contributor_count": 1,
                },
                "insights": [],
                "generated_at": "2026-06-18T12:00:00+00:00",
            }
        )

    monkeypatch.setattr("app.ai.router.get_reporting_service", fake_get_reporting_service)

    response = await client.post(
        "/api/ai/reports/project-health",
        json={"project_id": 130},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["completion_measured"] is False
