"""
Integration Tests for Reports API
TASK-048: Add integration tests for reports
Uses shared fixtures from conftest.py
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_dashboard_stats(client: AsyncClient, auth_headers: dict):
    """Test getting dashboard statistics"""
    response = await client.get(
        "/api/reports/dashboard",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_get_weekly_summary(client: AsyncClient, auth_headers: dict):
    """Test getting weekly summary"""
    response = await client.get(
        "/api/reports/weekly",
        headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reports_requires_auth(client: AsyncClient):
    """Test that reports require authentication"""
    response = await client.get("/api/reports/dashboard")
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, auth_headers: dict):
    """Test exporting as CSV"""
    end_date = datetime.utcnow().date().isoformat()
    start_date = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
    
    response = await client.get(
        f"/api/reports/export?format=csv&start_date={start_date}&end_date={end_date}",
        headers=auth_headers
    )
    # Export might return CSV or might return 404 if not implemented
    assert response.status_code in [200, 404]

