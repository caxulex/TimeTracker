# ============================================
# TIME TRACKER - WEBSOCKET HARDENING TESTS
# B8 / B13 / B21 — defensive correctness in the realtime path.
# ============================================
"""
Tests for the WebSocket router hardening pass:

* B8 Part 1 — bare except in the message loop is replaced with targeted
  handling. ``asyncio.CancelledError`` must propagate.
* B8 Part 2 — ``team_ids`` are populated from ``TeamMember`` at connect
  time. Team-scoped broadcasts only reach team members.
* B13 — per-connection active-timer load is tenant-scoped: cache writes
  for tenant A must not include tenant B's running entries.
"""

import asyncio
import os
from datetime import timedelta
from unittest.mock import AsyncMock

import fakeredis
import pytest
import pytest_asyncio

from app.models import Company, Team, TeamMember, TimeEntry, User
from app.routers import websocket as ws_module
from app.routers.websocket import (
    ConnectionManager,
    _load_user_team_ids,
    load_active_timers_from_db,
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


@pytest_asyncio.fixture(autouse=True)
async def _patch_presence_redis():
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager._redis = fake_redis
    manager.user_companies.clear()
    yield
    await fake_redis.flushdb()
    await fake_redis.aclose()
    manager._redis = None


# --------------------------------------------------------------------------- #
# B8 Part 1 — bare-except replacement                                         #
# --------------------------------------------------------------------------- #


class TestBareExceptReplacement:
    """The message loop must not swallow CancelledError."""

    @pytest.mark.asyncio
    async def test_send_personal_message_propagates_cancelled_error(self):
        """``send_personal_message`` propagates ``CancelledError`` raised
        from the underlying ``send_json`` call rather than silently
        treating it like any other exception."""
        mgr = ConnectionManager()

        sock = AsyncMock()
        sock.send_json = AsyncMock(side_effect=asyncio.CancelledError())
        mgr.active_connections[42] = {sock}

        with pytest.raises(asyncio.CancelledError):
            await mgr.send_personal_message({"type": "ping"}, 42)


# --------------------------------------------------------------------------- #
# B8 Part 2 — team_ids populated at connect time                              #
# --------------------------------------------------------------------------- #


class TestTeamScopedBroadcast:
    """Team-scoped broadcasts reach members and miss non-members."""

    @pytest.mark.asyncio
    async def test_broadcast_to_team_only_reaches_members(self):
        mgr = ConnectionManager()

        # User A is in team 7; user B is not.
        sock_a = AsyncMock()
        sock_a.send_json = AsyncMock()
        sock_b = AsyncMock()
        sock_b.send_json = AsyncMock()

        mgr.active_connections[1] = {sock_a}
        mgr.active_connections[2] = {sock_b}
        mgr.user_companies[1] = 100
        mgr.user_companies[2] = 100
        mgr.team_members[7] = {1}  # only user 1 in the team

        await mgr.broadcast_to_team({"type": "team_event"}, team_id=7)

        sock_a.send_json.assert_awaited_once()
        sock_b.send_json.assert_not_called()

    @pytest.mark.asyncio
    @skip_without_db
    async def test_load_user_team_ids_returns_user_teams(self, db_session):
        """``_load_user_team_ids`` returns exactly the teams the user
        is a member of — populated from the DB at connect time."""
        company = Company(name="Acme Co", slug="acme-co", email="acme@example.com")
        db_session.add(company)
        await db_session.flush()

        user = User(
            email="ws-team-user@example.com",
            name="WS Team User",
            password_hash="x",
            role="regular_user",
            is_active=True,
            company_id=company.id,
        )
        other_user = User(
            email="ws-other-user@example.com",
            name="WS Other User",
            password_hash="x",
            role="regular_user",
            is_active=True,
            company_id=company.id,
        )
        db_session.add_all([user, other_user])
        await db_session.flush()

        team_in = Team(name="In Team", company_id=company.id, owner_id=user.id)
        team_out = Team(name="Out Team", company_id=company.id, owner_id=other_user.id)
        db_session.add_all([team_in, team_out])
        await db_session.flush()

        db_session.add(TeamMember(team_id=team_in.id, user_id=user.id))
        db_session.add(TeamMember(team_id=team_out.id, user_id=other_user.id))
        await db_session.commit()

        team_ids = await _load_user_team_ids(user.id)

        assert team_in.id in team_ids
        assert team_out.id not in team_ids


# --------------------------------------------------------------------------- #
# B13 — per-connection cache load is tenant-scoped                            #
# --------------------------------------------------------------------------- #


class TestCrossTenantCacheIsolation:
    """A WS connect for tenant A must not write tenant B entries into
    tenant A's presence key."""

    @pytest.mark.asyncio
    @skip_without_db
    async def test_per_connection_load_does_not_leak_other_tenants(
        self, db_session
    ):
        # Two tenants, each with one user and one running TimeEntry.
        company_a = Company(name="Alpha", slug="alpha", email="alpha@example.com")
        company_b = Company(name="Bravo", slug="bravo", email="bravo@example.com")
        db_session.add_all([company_a, company_b])
        await db_session.flush()

        user_a = User(
            email="alpha-user@example.com",
            name="Alpha User",
            password_hash="x",
            role="regular_user",
            is_active=True,
            company_id=company_a.id,
        )
        user_b = User(
            email="bravo-user@example.com",
            name="Bravo User",
            password_hash="x",
            role="regular_user",
            is_active=True,
            company_id=company_b.id,
        )
        db_session.add_all([user_a, user_b])
        await db_session.flush()

        start = now_utc() - timedelta(minutes=5)
        entry_a = TimeEntry(
            user_id=user_a.id,
            start_time=start,
            end_time=None,
            is_running=True,
            description="alpha-running",
        )
        entry_b = TimeEntry(
            user_id=user_b.id,
            start_time=start,
            end_time=None,
            is_running=True,
            description="bravo-running",
        )
        db_session.add_all([entry_a, entry_b])
        await db_session.commit()

        # Simulate tenant A's WS connect: company-scoped warm.
        loaded = await load_active_timers_from_db(company_id=company_a.id)

        assert loaded == 1
        company_a_timers = await manager.get_active_timers(company_filter=company_a.id)
        company_b_timers = await manager.get_active_timers(company_filter=company_b.id)

        assert {t["user_id"] for t in company_a_timers} == {user_a.id}
        assert all(t["company_id"] == company_a.id for t in company_a_timers)
        assert company_b_timers == []

    @pytest.mark.asyncio
    @skip_without_db
    async def test_per_connection_load_preserves_other_tenant_entries(
        self, db_session
    ):
        """Loading tenant A's timers does not evict an entry already in
        the cache for tenant B (``dict.update`` semantics, not full
        replacement)."""
        company_a = Company(name="Alpha2", slug="alpha2", email="alpha2@example.com")
        company_b = Company(name="Bravo2", slug="bravo2", email="bravo2@example.com")
        db_session.add_all([company_a, company_b])
        await db_session.flush()

        user_a = User(
            email="alpha2-user@example.com",
            name="Alpha2 User",
            password_hash="x",
            role="regular_user",
            is_active=True,
            company_id=company_a.id,
        )
        db_session.add(user_a)
        await db_session.flush()

        start = now_utc() - timedelta(minutes=2)
        db_session.add(
            TimeEntry(
                user_id=user_a.id,
                start_time=start,
                end_time=None,
                is_running=True,
                description="alpha2-running",
            )
        )
        await db_session.commit()

        # Pre-seed an entry for tenant B as if its user were already
        # connected.
        await manager.set_active_timer(
            9999,
            {
                "user_id": 9999,
                "company_id": company_b.id,
                "user_name": "Bravo2 Cached",
                "start_time": now_utc().isoformat(),
            },
        )

        await load_active_timers_from_db(company_id=company_a.id)

        # Tenant B's pre-existing entry must remain untouched.
        company_b_timers = await manager.get_active_timers(company_filter=company_b.id)
        assert any(t["user_id"] == 9999 for t in company_b_timers)

        # Tenant A's row must have been added in tenant A key.
        company_a_timers = await manager.get_active_timers(company_filter=company_a.id)
        assert any(t["user_id"] == user_a.id for t in company_a_timers)
