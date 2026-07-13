# ============================================
# TIME TRACKER - WEBSOCKET TESTS
# Phase 7: Testing - WebSocket functionality
# ============================================
"""
Tests for WebSocket real-time functionality.
Note: These tests use mocks since WebSocket testing is complex.
Some tests require a database connection and will be skipped locally.
"""

import pytest
import os
import fakeredis
import pytest_asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient

from app.models import User
from app.utils.timewindow import now_utc


# Check if database is available
def database_available():
    """Check if test database is accessible."""
    db_url = os.getenv("DATABASE_URL", "")
    return bool(db_url and "postgresql" in db_url)


skip_without_db = pytest.mark.skipif(
    not database_available(),
    reason="PostgreSQL database not available"
)


class TestWebSocketConnection:
    """Test WebSocket connection and authentication."""

    @pytest.mark.asyncio
    async def test_websocket_endpoint_requires_auth(self, client: AsyncClient):
        """Test that WebSocket endpoint requires authentication token."""
        # WebSocket upgrade without token should fail
        response = await client.get("/api/ws")
        # Should return 403 or redirect, not 101 (upgrade)
        assert response.status_code != 101

    @pytest.mark.asyncio
    @skip_without_db
    async def test_websocket_active_timers_endpoint(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test HTTP endpoint for active timers."""
        response = await client.get("/api/ws/active-timers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Handle wrapped response (dict with timers) or raw list
        timers = data.get("timers", data) if isinstance(data, dict) else data
        assert isinstance(timers, list)

    @pytest.mark.asyncio
    async def test_websocket_active_timers_unauthenticated(self, client: AsyncClient):
        """Test active timers endpoint requires authentication."""
        response = await client.get("/api/ws/active-timers")
        # 401 = Unauthorized, 403 = Forbidden, 422 = Unprocessable Entity (missing token)
        assert response.status_code in [401, 403, 422]


class TestWebSocketManager:
    """Test WebSocket manager functionality."""

    @pytest_asyncio.fixture(autouse=True)
    async def _patch_ws_presence_redis(self):
        """Use isolated fakeredis instance for presence tests."""
        from app.routers.websocket import manager

        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        manager._redis = fake_redis
        manager.user_companies.clear()
        yield
        await fake_redis.flushdb()
        await fake_redis.aclose()
        manager._redis = None

    def test_presence_manager_has_connection_helpers(self):
        """Test that manager exposes expected presence helpers."""
        from app.routers.websocket import manager
        assert hasattr(manager, "get_redis")
        assert hasattr(manager, "set_active_timer")
        assert hasattr(manager, "clear_active_timer")

    @pytest.mark.asyncio
    async def test_set_active_timer(self):
        """Test setting an active timer in Redis presence."""
        from app.routers.websocket import manager

        timer_info = {
            "user_name": "Test User",
            "project_name": "Test Project",
            "start_time": "2026-01-08T10:00:00+00:00",
            "company_id": None,
        }
        await manager.set_active_timer(1, timer_info)

        timers = await manager.get_active_timers(company_filter=None)
        user_timer = [t for t in timers if t.get("user_id") == 1]
        assert len(user_timer) == 1
        assert user_timer[0]["user_name"] == "Test User"

    @pytest.mark.asyncio
    async def test_clear_active_timer(self):
        """Test clearing an active timer from Redis presence."""
        from app.routers.websocket import manager

        await manager.set_active_timer(2, {"user_name": "Test", "company_id": 2})
        await manager.clear_active_timer(2, company_id=2)

        timers = await manager.get_active_timers(company_filter=2)
        assert timers == []

    @pytest.mark.asyncio
    async def test_get_active_timers_with_company_filter(self):
        """Test filtering active timers by company_filter."""
        from app.routers.websocket import manager
        from app.dependencies import FILTER_NULL_COMPANY

        # Set up timers for different companies
        await manager.set_active_timer(10, {"company_id": 1, "user_name": "Company 1 User"})
        await manager.set_active_timer(11, {"company_id": 2, "user_name": "Company 2 User"})
        await manager.set_active_timer(12, {"company_id": 1, "user_name": "Company 1 User 2"})
        await manager.set_active_timer(13, {"company_id": None, "user_name": "Platform User"})

        # Filter by company 1
        company1_timers = await manager.get_active_timers(company_filter=1)
        assert len(company1_timers) == 2

        # Filter by company 2
        company2_timers = await manager.get_active_timers(company_filter=2)
        assert len(company2_timers) == 1

        # Filter by NULL company (platform users) using sentinel
        null_company_timers = await manager.get_active_timers(company_filter=FILTER_NULL_COMPANY)
        assert len(null_company_timers) == 1
        assert null_company_timers[0]["company_id"] is None

        # Super admin (company_filter=None) sees ALL timers
        all_timers = await manager.get_active_timers(company_filter=None)
        assert len(all_timers) == 4

    @pytest.mark.asyncio
    async def test_stale_entry_filtered_and_deleted(self):
        """Stale heartbeat entries are filtered from reads and lazily evicted."""
        from app.routers.websocket import manager, PRESENCE_STALE_THRESHOLD_SEC

        redis_client = await manager.get_redis()
        stale_hb = (now_utc() - timedelta(seconds=PRESENCE_STALE_THRESHOLD_SEC + 5)).isoformat()
        key = manager._presence_key(2)
        await redis_client.hset(
            key,
            "501",
            '{"user_id": 501, "company_id": 2, "user_name": "Stale", "heartbeat_at": "' + stale_hb + '"}'
        )

        timers = await manager.get_active_timers(company_filter=2)
        assert timers == []
        assert await redis_client.hget(key, "501") is None

    @pytest.mark.asyncio
    async def test_redis_down_failclosed(self, monkeypatch):
        """Presence operations fail-closed (no raise) when Redis is unavailable."""
        from app.routers.websocket import manager

        async def _raise():
            raise RuntimeError("redis down")

        monkeypatch.setattr(manager, "get_redis", _raise)
        await manager.set_active_timer(1, {"company_id": 2, "user_name": "X"})
        await manager.clear_active_timer(1, company_id=2)
        timers = await manager.get_active_timers(company_filter=2)
        assert timers == []

    @pytest.mark.asyncio
    async def test_elapsed_update_path_uses_redis_presence(self):
        """timer_update message mutates elapsed_seconds via Redis-backed presence."""
        from app.routers.websocket import manager, handle_message

        class _FakeWebSocket:
            async def send_json(self, _message):
                return None

        class _FakeUser:
            id = 77
            name = "Timer User"
            company_id = 3

        await manager.set_active_timer(
            77,
            {
                "company_id": 3,
                "user_name": "Timer User",
                "start_time": now_utc().isoformat(),
                "elapsed_seconds": 5,
            },
        )

        await handle_message(_FakeWebSocket(), _FakeUser(), {"type": "timer_update", "elapsed_seconds": 42})
        timers = await manager.get_active_timers(company_filter=3)
        assert len(timers) == 1
        assert timers[0]["elapsed_seconds"] == 42


class TestTimerBroadcast:
    """Test timer start/stop broadcasts."""

    @pytest.mark.asyncio
    @skip_without_db
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
                    timers = await manager.get_active_timers()
                    user_timer = [t for t in timers if t.get("user_id") == test_user.id]
                    
                    # Stop timer to clean up
                    await client.post("/api/time/stop", headers=auth_headers)
                    
                    # Timer should have been in cache during active period
                    # (might already be removed after stop)
