# ============================================
# TIME TRACKER - WEBSOCKET HEARTBEAT TESTS
# Bidirectional ping/pong, liveness watchdog, snapshot, metrics endpoint.
# ============================================
"""
Tests for the WebSocket heartbeat + reconnect-sync hardening pass.

The heartbeat path is tested at the manager + task level rather than
through a real WebSocket client because the relevant behaviors are:

* The proactive ping task fires on its interval and bumps a counter on
  ``websocket.send_json``.
* A pong recorded via ``manager.record_pong`` resets ``last_pong_at`` so
  the next interval does NOT trip the timeout.
* When ``last_pong_at`` is older than ``HEARTBEAT_TIMEOUT_SEC`` the task
  closes the socket with code ``4001`` and records a metrics event.

The metrics endpoint is exercised through the regular HTTP test client
so the admin role guard is verified end-to-end.
"""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.routers import websocket as ws_module
from app.routers.websocket import (
    HEARTBEAT_TIMEOUT_CLOSE_CODE,
    HEARTBEAT_TIMEOUT_CLOSE_REASON,
    ConnectionManager,
    _heartbeat_task,
    manager,
)
from app.utils.timewindow import now_utc


def _database_available() -> bool:
    db_url = os.getenv("DATABASE_URL", "") or os.getenv("TEST_DATABASE_URL", "")
    return bool(db_url and "postgresql" in db_url)


skip_without_db = pytest.mark.skipif(
    not _database_available(),
    reason="PostgreSQL database not available",
)


# --------------------------------------------------------------------------- #
# Heartbeat task                                                              #
# --------------------------------------------------------------------------- #


class TestHeartbeatTask:
    """Bidirectional ping/pong + liveness watchdog."""

    @pytest.mark.asyncio
    async def test_server_sends_ping_at_interval(self, monkeypatch):
        """The heartbeat task sends a ``{"type": "ping"}`` payload as
        soon as the interval elapses."""
        # Compress the interval so the test runs in milliseconds.
        monkeypatch.setattr(ws_module, "HEARTBEAT_INTERVAL_SEC", 0.05)
        monkeypatch.setattr(ws_module, "HEARTBEAT_TIMEOUT_SEC", 5.0)

        sock = AsyncMock()
        sock.send_json = AsyncMock()
        sock.close = AsyncMock()

        # Register the socket on the global manager so the task can read
        # ``last_pong_at`` and ``connection_ids``.
        manager.connection_ids[sock] = "test-conn-1"
        manager.last_pong_at[sock] = now_utc()
        try:
            task = asyncio.create_task(_heartbeat_task(sock, user_id=99))
            # Wait long enough for at least one ping cycle.
            await asyncio.sleep(0.12)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            assert sock.send_json.await_count >= 1
            payload = sock.send_json.await_args_list[0].args[0]
            assert payload["type"] == "ping"
            assert "timestamp" in payload
            sock.close.assert_not_awaited()
        finally:
            manager.connection_ids.pop(sock, None)
            manager.last_pong_at.pop(sock, None)

    @pytest.mark.asyncio
    async def test_pong_resets_timeout(self, monkeypatch):
        """``record_pong`` resets ``last_pong_at`` so a subsequent
        interval does not trip the timeout."""
        monkeypatch.setattr(ws_module, "HEARTBEAT_INTERVAL_SEC", 0.05)
        monkeypatch.setattr(ws_module, "HEARTBEAT_TIMEOUT_SEC", 0.5)

        sock = AsyncMock()
        sock.send_json = AsyncMock()
        sock.close = AsyncMock()

        manager.connection_ids[sock] = "test-conn-2"
        manager.last_pong_at[sock] = now_utc()
        try:
            task = asyncio.create_task(_heartbeat_task(sock, user_id=99))
            # Simulate a healthy client: keep pumping pongs in faster than
            # the interval so the watchdog never trips.
            for _ in range(4):
                await asyncio.sleep(0.06)
                manager.record_pong(sock)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            sock.close.assert_not_awaited()
            assert sock.send_json.await_count >= 2
        finally:
            manager.connection_ids.pop(sock, None)
            manager.last_pong_at.pop(sock, None)

    @pytest.mark.asyncio
    async def test_no_pong_triggers_disconnect(self, monkeypatch):
        """A connection with no recent pong is force-closed with the
        distinct ``4001 heartbeat_timeout`` code so the frontend can
        log it and reconnect."""
        monkeypatch.setattr(ws_module, "HEARTBEAT_INTERVAL_SEC", 0.05)
        monkeypatch.setattr(ws_module, "HEARTBEAT_TIMEOUT_SEC", 0.05)

        sock = AsyncMock()
        sock.send_json = AsyncMock()
        sock.close = AsyncMock()

        # Seed last_pong well in the past so the watchdog fires on the
        # very first cycle.
        manager.connection_ids[sock] = "test-conn-3"
        manager.last_pong_at[sock] = now_utc() - timedelta(seconds=30)
        events_before = len(manager.heartbeat_timeout_events)
        try:
            await asyncio.wait_for(
                _heartbeat_task(sock, user_id=99),
                timeout=1.0,
            )
            sock.close.assert_awaited_once()
            kwargs = sock.close.await_args.kwargs
            assert kwargs.get("code") == HEARTBEAT_TIMEOUT_CLOSE_CODE
            assert kwargs.get("reason") == HEARTBEAT_TIMEOUT_CLOSE_REASON
            assert len(manager.heartbeat_timeout_events) == events_before + 1
        finally:
            manager.connection_ids.pop(sock, None)
            manager.last_pong_at.pop(sock, None)


# --------------------------------------------------------------------------- #
# Manager bookkeeping                                                         #
# --------------------------------------------------------------------------- #


class TestConnectionManagerHeartbeatState:
    """Manager exposes per-connection state used by the watchdog."""

    @pytest.mark.asyncio
    async def test_connect_assigns_connection_id_and_seeds_last_pong(self):
        mgr = ConnectionManager()
        sock = AsyncMock()
        sock.accept = AsyncMock()

        connection_id = await mgr.connect(sock, user_id=1, team_ids=[], company_id=None)

        assert isinstance(connection_id, str) and connection_id
        assert mgr.connection_ids[sock] == connection_id
        assert sock in mgr.last_pong_at
        assert sock in mgr.connection_started_at

    @pytest.mark.asyncio
    async def test_disconnect_clears_per_connection_state(self):
        mgr = ConnectionManager()
        sock = AsyncMock()
        sock.accept = AsyncMock()
        await mgr.connect(sock, user_id=1, team_ids=[], company_id=None)

        mgr.disconnect(sock, user_id=1, reason="client_close")

        assert sock not in mgr.connection_ids
        assert sock not in mgr.last_pong_at
        assert sock not in mgr.connection_started_at

    def test_heartbeat_timeouts_last_hour_prunes_old_events(self):
        mgr = ConnectionManager()
        # Far-past event: should be pruned on read.
        mgr.heartbeat_timeout_events.append(now_utc() - timedelta(hours=2))
        # Recent event: should be counted.
        mgr.heartbeat_timeout_events.append(now_utc() - timedelta(minutes=10))
        assert mgr.heartbeat_timeouts_last_hour() == 1


# --------------------------------------------------------------------------- #
# Metrics endpoint                                                            #
# --------------------------------------------------------------------------- #


class TestWebSocketMetricsEndpoint:
    """``/api/admin/ws/metrics`` — admin-only operational visibility."""

    @pytest.mark.asyncio
    @skip_without_db
    async def test_metrics_endpoint_allows_manager(
        self, client: AsyncClient, manager_auth_headers: dict
    ):
        response = await client.get("/api/admin/ws/metrics", headers=manager_auth_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @skip_without_db
    async def test_metrics_endpoint_allows_admin(
        self, client: AsyncClient, role_admin_auth_headers: dict
    ):
        response = await client.get("/api/admin/ws/metrics", headers=role_admin_auth_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @skip_without_db
    async def test_metrics_endpoint_rejects_non_admin(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.get("/api/admin/ws/metrics", headers=auth_headers)
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    @skip_without_db
    async def test_metrics_endpoint_returns_expected_shape(
        self, client: AsyncClient, admin_auth_headers: dict
    ):
        # Seed a couple of fake connections on the global manager so the
        # by_company / unique_users counts exercise both branches.
        sock_a = AsyncMock()
        sock_b = AsyncMock()
        sock_a.accept = AsyncMock()
        sock_b.accept = AsyncMock()
        await manager.connect(sock_a, user_id=9001, team_ids=[], company_id=42)
        await manager.connect(sock_b, user_id=9002, team_ids=[], company_id=None)
        try:
            response = await client.get(
                "/api/admin/ws/metrics", headers=admin_auth_headers
            )
            assert response.status_code == 200
            body = response.json()
            assert set(body.keys()) == {
                "active_connections",
                "unique_users",
                "by_company",
                "heartbeat_timeouts_last_hour",
            }
            assert body["active_connections"] >= 2
            assert body["unique_users"] >= 2
            assert "42" in body["by_company"]
            assert "null" in body["by_company"]
            assert isinstance(body["heartbeat_timeouts_last_hour"], int)
        finally:
            manager.disconnect(sock_a, user_id=9001, reason="test_cleanup")
            manager.disconnect(sock_b, user_id=9002, reason="test_cleanup")


# --------------------------------------------------------------------------- #
# Snapshot construction                                                       #
# --------------------------------------------------------------------------- #


class TestSnapshotPayload:
    """The endpoint sends a ``snapshot`` immediately after connect.

    Full integration through a real WS upgrade is tricky to set up; here
    we verify the manager helpers used to build the payload return the
    expected shape.
    """

    def test_snapshot_helpers_expose_current_state(self):
        mgr = ConnectionManager()
        mgr.set_active_timer(
            7,
            {
                "user_id": 7,
                "user_name": "Snap User",
                "company_id": None,
                "start_time": "2026-01-01T00:00:00+00:00",
            },
        )
        mgr.active_connections[7] = {AsyncMock()}

        timers = mgr.get_active_timers(company_filter=None)
        online = mgr.get_online_users()

        assert any(t["user_id"] == 7 for t in timers)
        assert 7 in online
