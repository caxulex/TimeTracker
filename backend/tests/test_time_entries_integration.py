"""
Integration Tests for Time Entries API
TASK-046: Add integration tests for time entries
Uses shared fixtures from conftest.py
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_timer_status(client: AsyncClient, auth_headers: dict):
    """Test getting timer status"""
    response = await client.get(
        "/api/time/timer",
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_time_entries(client: AsyncClient, auth_headers: dict):
    """Test listing time entries"""
    response = await client.get(
        "/api/time",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, (list, dict))


@pytest.mark.asyncio
async def test_time_entry_requires_auth(client: AsyncClient):
    """Test that time entries require authentication"""
    response = await client.get("/api/time")
    assert response.status_code in [401, 403]


@pytest.mark.asyncio 
async def test_timer_requires_auth(client: AsyncClient):
    """Test that timer endpoints require authentication"""
    response = await client.post("/api/time/start", json={})
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_stop_timer_when_not_running(client: AsyncClient, auth_headers: dict):
    """Test stopping timer when none is running"""
    response = await client.post(
        "/api/time/stop",
        headers=auth_headers
    )
    # Should return error or empty response
    assert response.status_code in [200, 400, 404]
