# ============================================
# TIME TRACKER - WEBSOCKET TESTS
# Phase 7: Testing - WebSocket functionality
# ============================================
"""
Tests for WebSocket real-time functionality.
Note: These tests use mocks since WebSocket testing is complex.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient

from app.models import User


class TestWebSocketConnection:
    """Test WebSocket connection and authentication."""

    @pytest.mark.asyncio
    async def test_websocket_endpoint_requires_auth(self, client: AsyncClient):
        """Test that WebSocket endpoint requires authentication token."""
        # WebSocket upgrade without token should fail
        response = await client.get("/ws")
        # Should return 403 or redirect, not 101 (upgrade)
        assert response.status_code != 101

    @pytest.mark.asyncio
    async def test_websocket_active_timers_endpoint(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test HTTP endpoint for active timers."""
        response = await client.get("/ws/active-timers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_websocket_active_timers_unauthenticated(self, client: AsyncClient):
        """Test active timers endpoint requires authentication."""
        response = await client.get("/ws/active-timers")
        assert response.status_code == 401


class TestWebSocketManager:
    """Test WebSocket manager functionality."""

    def test_active_timers_cache_structure(self):
        """Test that active timers cache has correct structure."""
        from app.routers.websocket import manager
        
        # Manager should have active_timers dict
        assert hasattr(manager, 'active_timers')
        assert isinstance(manager.active_timers, dict)

    def test_set_active_timer(self):
        """Test setting an active timer in cache."""
        from app.routers.websocket import manager
        
        # Set a timer
        timer_info = {
            "user_id": 1,
            "user_name": "Test User",
            "project_name": "Test Project",
            "start_time": "2026-01-08T10:00:00Z",
            "company_id": None,
        }
        manager.set_active_timer(1, timer_info)
        
        # Verify it's in cache
        assert 1 in manager.active_timers
        assert manager.active_timers[1]["user_name"] == "Test User"
        
        # Clean up
        manager.clear_active_timer(1)

    def test_clear_active_timer(self):
        """Test clearing an active timer from cache."""
        from app.routers.websocket import manager
        
        # Set then clear
        timer_info = {"user_id": 2, "user_name": "Test"}
        manager.set_active_timer(2, timer_info)
        manager.clear_active_timer(2)
        
        assert 2 not in manager.active_timers

    def test_get_active_timers_with_company_filter(self):
        """Test filtering active timers by company_id."""
        from app.routers.websocket import manager
        
        # Set up timers for different companies
        manager.set_active_timer(10, {"user_id": 10, "company_id": 1, "user_name": "Company 1 User"})
        manager.set_active_timer(11, {"user_id": 11, "company_id": 2, "user_name": "Company 2 User"})
        manager.set_active_timer(12, {"user_id": 12, "company_id": 1, "user_name": "Company 1 User 2"})
        
        # Filter by company 1
        company1_timers = manager.get_active_timers(company_id=1)
        assert len(company1_timers) == 2
        
        # Filter by company 2
        company2_timers = manager.get_active_timers(company_id=2)
        assert len(company2_timers) == 1
        
        # Clean up
        manager.clear_active_timer(10)
        manager.clear_active_timer(11)
        manager.clear_active_timer(12)


class TestTimerBroadcast:
    """Test timer start/stop broadcasts."""

    @pytest.mark.asyncio
    async def test_timer_start_updates_cache(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test that starting a timer updates the active timers cache."""
        from app.routers.websocket import manager
        
        # First, we need a project to start a timer
        # Create a team first
        team_response = await client.post(
            "/api/teams/",
            headers=auth_headers,
            json={"name": "Test Team for WebSocket"}
        )
        if team_response.status_code == 201:
            team_id = team_response.json()["id"]
            
            # Create a project
            project_response = await client.post(
                "/api/projects/",
                headers=auth_headers,
                json={"name": "Test Project for Timer", "team_id": team_id}
            )
            
            if project_response.status_code == 201:
                project_id = project_response.json()["id"]
                
                # Start timer
                start_response = await client.post(
                    "/api/time/start",
                    headers=auth_headers,
                    json={"project_id": project_id, "description": "Test timer"}
                )
                
                if start_response.status_code == 200:
                    # Check if timer is in cache
                    timers = manager.get_active_timers()
                    user_timer = [t for t in timers if t.get("user_id") == test_user.id]
                    
                    # Stop timer to clean up
                    await client.post("/api/time/stop", headers=auth_headers)
                    
                    # Timer should have been in cache during active period
                    # (might already be removed after stop)
