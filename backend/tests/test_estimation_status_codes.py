"""
Tests for task estimation endpoint status codes (PR-B).

Verifies HTTP status codes are correct:
- 422 for invalid input
- 503 for service/runtime failures
- 400 for precondition failures (insufficient data for training)
- 403 for permission violations
- 200 for valid successes, including thin-data/fallback states
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.models import User


@pytest.mark.asyncio
async def test_estimation_task_200_fallback_estimate_valid(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User
):
    """POST /api/ai/estimation/task with fallback estimate returns 200 (valid success)."""
    # Fallback estimate happens when user has no history
    # The service gracefully returns a default estimate (method="fallback")
    # This is NOT an error — it's a valid 200 response
    from app.ai.services.task_estimation_service import DurationEstimate
    
    with patch("app.ai.services.task_estimation_service.TaskEstimationService.estimate_duration") as mock_estimate:
        mock_estimate.return_value = DurationEstimate(
            estimated_minutes=60,
            confidence=0.3,
            range_min=30,
            range_max=120,
            method="fallback",
            factors=[{"name": "Default", "description": "No history"}],
            similar_tasks=[]
        )
        response = await client.post(
            "/api/ai/estimation/task",
            json={"description": "Valid task"},
            headers=auth_headers
        )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["method"] == "fallback"


@pytest.mark.asyncio
async def test_estimation_batch_200_successful_batch(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User
):
    """POST /api/ai/estimation/batch with valid tasks returns 200."""
    from app.ai.services.task_estimation_service import DurationEstimate
    
    with patch("app.ai.services.task_estimation_service.TaskEstimationService.estimate_batch") as mock_batch:
        mock_batch.return_value = [
            DurationEstimate(
                estimated_minutes=60,
                confidence=0.8,
                range_min=45,
                range_max=90,
                method="historical",
                factors=[],
                similar_tasks=[]
            ),
            DurationEstimate(
                estimated_minutes=30,
                confidence=0.7,
                range_min=20,
                range_max=45,
                method="historical",
                factors=[],
                similar_tasks=[]
            )
        ]
        response = await client.post(
            "/api/ai/estimation/batch",
            json={
                "tasks": [
                    {"description": "Task 1"},
                    {"description": "Task 2"}
                ]
            },
            headers=auth_headers
        )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(response.json()["estimates"]) == 2


@pytest.mark.asyncio
async def test_estimation_train_200_successful_training(
    client: AsyncClient,
    admin_auth_headers: dict,
    admin_user: User
):
    """POST /api/ai/estimation/train returns 200 on successful training."""
    
    with patch("app.ai.services.task_estimation_service.TaskEstimationService.train_model") as mock_train:
        from datetime import datetime
        mock_train.return_value = {
            "success": True,
            "samples_used": 100,
            "mae_minutes": 15.5,
            "rmse_minutes": 22.3,
            "trained_at": datetime.utcnow().isoformat()
        }
        response = await client.post(
            "/api/ai/estimation/train",
            json={"period_days": 180},
            headers=admin_auth_headers
        )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["samples_used"] == 100


@pytest.mark.asyncio
async def test_estimation_profile_200_default_profile_sparse_history(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User
):
    """GET /api/ai/estimation/profile returns 200 with default profile for sparse history."""
    # User with no time entries gets a default profile — this is valid 200, not an error
    from app.ai.services.task_estimation_service import UserPerformanceProfile
    from datetime import datetime
    
    with patch("app.ai.services.task_estimation_service.TaskEstimationService.get_user_profile") as mock_profile:
        mock_profile.return_value = UserPerformanceProfile(
            user_id=test_user.id,
            avg_task_duration=60.0,
            task_completion_rate=0.0,
            speed_factor=1.0,
            preferred_task_types=[],
            peak_performance_hours=[9, 10, 11, 14, 15],
            task_count=0,
            calculated_at=datetime.utcnow()
        )
        response = await client.get(
            "/api/ai/estimation/profile",
            headers=auth_headers
        )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["task_count"] == 0


@pytest.mark.asyncio
async def test_estimation_stats_200_model_not_trained_available(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User
):
    """GET /api/ai/estimation/stats returns 200 even with model_trained=false (valid status)."""
    # model_trained=false and ml_available=false are NOT errors — they're informational status
    # This must remain 200 to honestly report the service state
    with patch("app.ai.services.task_estimation_service.TaskEstimationService.get_estimation_stats") as mock_stats:
        mock_stats.return_value = {
            "model_trained": False,
            "ml_available": False,
            "cached_profiles": 0,
            "min_samples_required": 50,
            "tfidf_features": 0
        }
        response = await client.get(
            "/api/ai/estimation/stats",
            headers=auth_headers
        )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["model_trained"] is False
    assert response.json()["ml_available"] is False


@pytest.mark.asyncio
async def test_estimation_task_422_invalid_description_empty(client, auth_headers, test_user):
    response = await client.post('/api/ai/estimation/task', json={'description': ''}, headers=auth_headers)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_estimation_task_422_invalid_scheduled_hour(client, auth_headers, test_user):
    response = await client.post('/api/ai/estimation/task', json={'description': 'Valid task', 'scheduled_hour': 25}, headers=auth_headers)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_estimation_task_503_service_exception(client, auth_headers, test_user):
    with patch('app.ai.services.task_estimation_service.TaskEstimationService.estimate_duration') as m: m.side_effect = RuntimeError('fail'); response = await client.post('/api/ai/estimation/task', json={'description': 'task'}, headers=auth_headers)
    assert response.status_code == 503

@pytest.mark.asyncio
async def test_estimation_batch_422_empty(client, auth_headers, test_user):
    response = await client.post('/api/ai/estimation/batch', json={'tasks': []}, headers=auth_headers)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_estimation_batch_503(client, auth_headers, test_user):
    with patch('app.ai.services.task_estimation_service.TaskEstimationService.estimate_batch') as m: m.side_effect = RuntimeError('fail'); response = await client.post('/api/ai/estimation/batch', json={'tasks': [{'description': 'task'}]}, headers=auth_headers)
    assert response.status_code == 503

@pytest.mark.asyncio
async def test_estimation_train_403(client, auth_headers, test_user):
    response = await client.post('/api/ai/estimation/train', json={'period_days': 180}, headers=auth_headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_estimation_train_503(client, admin_auth_headers, admin_user):
    with patch('app.ai.services.task_estimation_service.TaskEstimationService.train_model') as m: m.return_value = {'success': False, 'error': 'ML libraries not installed'}; response = await client.post('/api/ai/estimation/train', json={'period_days': 180}, headers=admin_auth_headers)
    assert response.status_code == 503

@pytest.mark.asyncio
async def test_estimation_train_400(client, admin_auth_headers, admin_user):
    with patch('app.ai.services.task_estimation_service.TaskEstimationService.train_model') as m: m.return_value = {'success': False, 'error': 'Insufficient data'}; response = await client.post('/api/ai/estimation/train', json={'period_days': 180}, headers=admin_auth_headers)
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_estimation_profile_403(client, auth_headers, test_user):
    response = await client.get('/api/ai/estimation/profile?user_id=999', headers=auth_headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_estimation_profile_503(client, auth_headers, test_user):
    with patch('app.ai.services.task_estimation_service.TaskEstimationService.get_user_profile') as m: m.side_effect = RuntimeError('fail'); response = await client.get('/api/ai/estimation/profile', headers=auth_headers)
    assert response.status_code == 503

@pytest.mark.asyncio
async def test_estimation_stats_503(client, auth_headers, test_user):
    with patch('app.ai.services.task_estimation_service.TaskEstimationService.get_estimation_stats') as m: m.side_effect = RuntimeError('fail'); response = await client.get('/api/ai/estimation/stats', headers=auth_headers)
    assert response.status_code == 503
