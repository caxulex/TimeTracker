"""
Integration Tests for Teams API
TASK-047: Add integration tests for teams
Uses shared fixtures from conftest.py
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_teams(client: AsyncClient, auth_headers: dict):
    """Test listing teams"""
    response = await client.get(
        "/api/teams",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, (list, dict))


@pytest.mark.asyncio
async def test_create_team(client: AsyncClient, auth_headers: dict):
    """Test creating a team"""
    response = await client.post(
        "/api/teams",
        json={"name": "Integration Test Team", "description": "A test team"},
        headers=auth_headers
    )
    assert response.status_code in [200, 201]
    data = response.json()
    assert data["name"] == "Integration Test Team"


@pytest.mark.asyncio
async def test_teams_requires_auth(client: AsyncClient):
    """Test that teams require authentication"""
    response = await client.get("/api/teams")
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_create_team_requires_name(client: AsyncClient, auth_headers: dict):
    """Test that team creation requires name"""
    response = await client.post(
        "/api/teams",
        json={"description": "No name team"},
        headers=auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_team(client: AsyncClient, auth_headers: dict):
    """Test getting a team that doesn't exist"""
    import uuid
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/teams/{fake_id}",
        headers=auth_headers
    )
    assert response.status_code in [403, 404, 422]


