"""Tests for ML anomaly endpoint status codes (PR-C)."""

from datetime import datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ml_anomalies_scan_422_invalid_period_days(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/ai/ml/anomalies/scan",
        json={"period_days": 0},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ml_anomalies_scan_403_permission_other_user(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/ai/ml/anomalies/scan",
        json={"user_id": 999, "period_days": 7},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ml_anomalies_scan_503_service_exception(client: AsyncClient, auth_headers: dict):
    with patch("app.ai.services.ml_anomaly_service.MLAnomalyService.detect_ml_anomalies") as mock_scan:
        mock_scan.side_effect = RuntimeError("scan failed")
        response = await client.post(
            "/api/ai/ml/anomalies/scan",
            json={"period_days": 7},
            headers=auth_headers,
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_ml_burnout_assess_422_invalid_period_days(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/ai/ml/burnout/assess",
        json={"period_days": 6},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ml_burnout_assess_403_permission_other_user(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/ai/ml/burnout/assess",
        json={"user_id": 999, "period_days": 30},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ml_burnout_assess_503_service_exception(client: AsyncClient, auth_headers: dict):
    with patch("app.ai.services.ml_anomaly_service.MLAnomalyService.assess_burnout_risk") as mock_assess:
        mock_assess.side_effect = RuntimeError("burnout failed")
        response = await client.post(
            "/api/ai/ml/burnout/assess",
            json={"period_days": 30},
            headers=auth_headers,
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_ml_burnout_assess_200_insufficient_data_valid_state(client: AsyncClient, auth_headers: dict):
    from app.ai.services.ml_anomaly_service import BurnoutRiskAssessment

    with patch("app.ai.services.ml_anomaly_service.MLAnomalyService.assess_burnout_risk") as mock_assess:
        mock_assess.return_value = BurnoutRiskAssessment(
            user_id=1,
            user_name="Test User",
            risk_level=None,
            risk_score=None,
            factors=[],
            recommendations=["Need more days"],
            trend=None,
            insufficient_data=True,
            min_work_days_threshold=3,
            assessed_at=datetime.utcnow(),
        )
        response = await client.post(
            "/api/ai/ml/burnout/assess",
            json={"period_days": 30},
            headers=auth_headers,
        )
    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["insufficient_data"] is True


@pytest.mark.asyncio
async def test_ml_burnout_team_scan_422_invalid_team_id(client: AsyncClient, admin_auth_headers: dict):
    response = await client.post(
        "/api/ai/ml/burnout/team-scan",
        json={"team_id": "invalid"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ml_burnout_team_scan_403_role_required(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/ai/ml/burnout/team-scan",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ml_burnout_team_scan_503_service_exception(client: AsyncClient, admin_auth_headers: dict):
    with patch("app.ai.services.ml_anomaly_service.MLAnomalyService.scan_team_burnout") as mock_scan:
        mock_scan.side_effect = RuntimeError("team scan failed")
        response = await client.post(
            "/api/ai/ml/burnout/team-scan",
            json={},
            headers=admin_auth_headers,
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_ml_baseline_calculate_422_invalid_period_days(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/ai/ml/baseline/calculate",
        json={"period_days": 181},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ml_baseline_calculate_403_permission_other_user(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/ai/ml/baseline/calculate",
        json={"user_id": 999, "period_days": 30},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ml_baseline_calculate_503_service_exception(client: AsyncClient, auth_headers: dict):
    with patch("app.ai.services.ml_anomaly_service.MLAnomalyService.calculate_user_baseline") as mock_baseline:
        mock_baseline.side_effect = RuntimeError("baseline failed")
        response = await client.post(
            "/api/ai/ml/baseline/calculate",
            json={"period_days": 30},
            headers=auth_headers,
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_ml_baseline_calculate_200_zero_data_points_valid_state(client: AsyncClient, auth_headers: dict):
    from app.ai.services.ml_anomaly_service import UserBaseline

    with patch("app.ai.services.ml_anomaly_service.MLAnomalyService.calculate_user_baseline") as mock_baseline:
        mock_baseline.return_value = UserBaseline(
            user_id=1,
            avg_daily_hours=8.0,
            std_daily_hours=1.5,
            avg_weekly_hours=40.0,
            typical_start_hour=9.0,
            typical_end_hour=17.0,
            preferred_days=[0, 1, 2, 3, 4],
            project_distribution={},
            avg_entry_duration=60.0,
            entries_per_day=3.0,
            calculated_at=datetime.utcnow(),
            data_points=0,
        )
        response = await client.post(
            "/api/ai/ml/baseline/calculate",
            json={"period_days": 30},
            headers=auth_headers,
        )
    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["data_points"] == 0
