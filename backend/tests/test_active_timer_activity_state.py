# ============================================
# TIME TRACKER - ACTIVE TIMER ACTIVITY STATE TESTS
# Covers the fix that surfaces break/meeting state on the
# "Who's Working Now" panel:
#   - GET /api/time/active response includes activity_state,
#     break_type, meeting_type, meeting_title.
#   - start_break / end_break / start_meeting / end_meeting
#     mutate ws_manager.active_timers and broadcast timer_updated.
# ============================================
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import fakeredis
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_company_filter, get_current_active_user, get_current_user
from app.main import app
from app.models import Project, Team, TeamMember, TimeEntry, User, WorkSession
from app.routers.websocket import manager as ws_manager


@pytest_asyncio.fixture(autouse=True)
def _bypass_auth(test_user: User):
    """Skip JWT/Redis blacklist — auth correctness isn't under test here."""
    app.dependency_overrides[get_current_active_user] = lambda: test_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def _team(db_session: AsyncSession, test_user: User) -> Team:
    team = Team(name="Activity Team", owner_id=test_user.id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=test_user.id, role="owner"))
    await db_session.flush()
    await db_session.refresh(team)
    return team


@pytest_asyncio.fixture
async def _project(db_session: AsyncSession, _team: Team) -> Project:
    project = Project(name="Activity Project", team_id=_team.id, color="#3B82F6")
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def _running_entry(
    db_session: AsyncSession, test_user: User, _project: Project
) -> TimeEntry:
    ws = WorkSession(
        user_id=test_user.id,
        company_id=test_user.company_id,
        start_time=datetime.now(timezone.utc) - timedelta(hours=1),
        status="active",
    )
    db_session.add(ws)
    await db_session.flush()
    entry = TimeEntry(
        user_id=test_user.id,
        project_id=_project.id,
        work_session_id=ws.id,
        description="Working",
        start_time=datetime.now(timezone.utc) - timedelta(minutes=10),
        is_running=True,
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    return entry


@pytest_asyncio.fixture(autouse=True)
async def _isolate_ws_manager():
    """Reset and stub ws_manager broadcasts so tests don't touch sockets."""
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ws_manager._redis = fake_redis
    ws_manager.user_companies.clear()
    ws_manager.broadcast_to_company = AsyncMock()
    ws_manager.broadcast_timer_updated = AsyncMock(wraps=ws_manager.broadcast_timer_updated)  # type: ignore[assignment]
    # Wrapping needs the real coroutine to still work; re-wrap with a clean
    # AsyncMock so call counts are reliable.
    ws_manager.broadcast_timer_updated = AsyncMock()
    yield
    await fake_redis.flushdb()
    await fake_redis.aclose()
    ws_manager._redis = None


class TestActiveTimersEndpointShape:
    @pytest.mark.asyncio
    async def test_endpoint_returns_activity_state_working(
        self,
        client: AsyncClient,
        auth_headers: dict,
        _running_entry: TimeEntry,
    ):
        resp = await client.get("/api/time/active", headers=auth_headers)
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        row = rows[0]
        assert row["activity_state"] == "working"
        assert row["break_type"] is None
        assert row["meeting_type"] is None
        assert row["meeting_title"] is None

    @pytest.mark.asyncio
    async def test_endpoint_returns_break_state(
        self,
        client: AsyncClient,
        auth_headers: dict,
        _running_entry: TimeEntry,
    ):
        # Trigger a break via the API so all side effects run.
        r = await client.post(
            "/api/work-sessions/break/start",
            json={"break_type": "lunch"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

        resp = await client.get("/api/time/active", headers=auth_headers)
        assert resp.status_code == 200
        row = resp.json()[0]
        assert row["activity_state"] == "break"
        assert row["break_type"] == "lunch"
        assert row["meeting_type"] is None
        assert row["meeting_title"] is None

    @pytest.mark.asyncio
    async def test_endpoint_returns_meeting_state(
        self,
        client: AsyncClient,
        auth_headers: dict,
        _running_entry: TimeEntry,
    ):
        r = await client.post(
            "/api/work-sessions/meeting/start",
            json={"meeting_type": "client", "title": "Weekly sync"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

        resp = await client.get("/api/time/active", headers=auth_headers)
        assert resp.status_code == 200
        rows = resp.json()
        # Meeting creates a *new* open TimeEntry (the original got closed).
        # Only one should remain open.
        assert len(rows) == 1
        row = rows[0]
        assert row["activity_state"] == "meeting"
        assert row["meeting_type"] == "client"
        assert row["meeting_title"] == "Weekly sync"
        assert row["break_type"] is None
        # Meeting time entries have no project.
        assert row["project_id"] is None


class TestCacheTransitions:
    @pytest.mark.asyncio
    async def test_start_break_updates_cache(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        _running_entry: TimeEntry,
    ):
        r = await client.post(
            "/api/work-sessions/break/start",
            json={"break_type": "short"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        cached = (await ws_manager.get_active_timers(company_filter=get_company_filter(test_user)))[0]
        assert cached["activity_state"] == "break"
        assert cached["break_type"] == "short"
        ws_manager.broadcast_timer_updated.assert_awaited()

    @pytest.mark.asyncio
    async def test_end_break_restores_working(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        _running_entry: TimeEntry,
    ):
        r1 = await client.post(
            "/api/work-sessions/break/start",
            json={"break_type": "short"},
            headers=auth_headers,
        )
        assert r1.status_code == 200, r1.text
        r2 = await client.post(
            "/api/work-sessions/break/end",
            headers=auth_headers,
        )
        assert r2.status_code == 200, r2.text
        cached = (await ws_manager.get_active_timers(company_filter=get_company_filter(test_user)))[0]
        assert cached["activity_state"] == "working"
        assert cached["break_type"] is None

    @pytest.mark.asyncio
    async def test_start_meeting_replaces_cache_with_meeting_entry(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        _running_entry: TimeEntry,
    ):
        r = await client.post(
            "/api/work-sessions/meeting/start",
            json={"meeting_type": "internal", "title": "Standup"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        cached = (await ws_manager.get_active_timers(company_filter=get_company_filter(test_user)))[0]
        assert cached["activity_state"] == "meeting"
        assert cached["meeting_type"] == "internal"
        assert cached["meeting_title"] == "Standup"
        # Meeting entries have no project.
        assert cached["project_id"] is None

    @pytest.mark.asyncio
    async def test_end_meeting_restores_project_entry(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        _project: Project,
        _running_entry: TimeEntry,
    ):
        r1 = await client.post(
            "/api/work-sessions/meeting/start",
            json={"meeting_type": "internal", "title": "Standup"},
            headers=auth_headers,
        )
        assert r1.status_code == 200, r1.text
        r2 = await client.post(
            "/api/work-sessions/meeting/end",
            headers=auth_headers,
        )
        assert r2.status_code == 200, r2.text
        cached = (await ws_manager.get_active_timers(company_filter=get_company_filter(test_user)))[0]
        assert cached["activity_state"] == "working"
        assert cached["meeting_type"] is None
        assert cached["meeting_title"] is None
        # The resumed entry is associated with the original project.
        assert cached["project_id"] == _project.id


class TestElapsedSecondsFreezesDuringBreak:
    """Regression tests for fix(active-timers): elapsed_seconds must freeze
    at paused_at while the user is on break, then resume counting after
    end_break without jumping forward by the break duration.
    """

    @pytest.mark.asyncio
    async def test_active_endpoint_freezes_elapsed_during_break(
        self,
        client: AsyncClient,
        auth_headers: dict,
        _running_entry: TimeEntry,
    ):
        # Start a break — entry becomes is_paused with paused_at = now.
        r = await client.post(
            "/api/work-sessions/break/start",
            json={"break_type": "short"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

        first = await client.get("/api/time/active", headers=auth_headers)
        assert first.status_code == 200
        elapsed_a = first.json()[0]["elapsed_seconds"]

        # Wait long enough that any non-frozen clock would tick at least 1s.
        await asyncio.sleep(1.2)

        second = await client.get("/api/time/active", headers=auth_headers)
        assert second.status_code == 200
        elapsed_b = second.json()[0]["elapsed_seconds"]

        assert elapsed_a == elapsed_b, (
            f"elapsed_seconds must be frozen during a break, "
            f"got {elapsed_a} then {elapsed_b}"
        )

    @pytest.mark.asyncio
    async def test_active_endpoint_resumes_after_end_break_without_jump(
        self,
        client: AsyncClient,
        auth_headers: dict,
        _running_entry: TimeEntry,
    ):
        # Snapshot elapsed BEFORE the break to establish the baseline.
        pre = await client.get("/api/time/active", headers=auth_headers)
        assert pre.status_code == 200
        elapsed_pre = pre.json()[0]["elapsed_seconds"]

        r1 = await client.post(
            "/api/work-sessions/break/start",
            json={"break_type": "short"},
            headers=auth_headers,
        )
        assert r1.status_code == 200, r1.text

        # Take a measurable break.
        break_seconds = 2
        await asyncio.sleep(break_seconds + 0.1)

        r2 = await client.post(
            "/api/work-sessions/break/end",
            headers=auth_headers,
        )
        assert r2.status_code == 200, r2.text

        post = await client.get("/api/time/active", headers=auth_headers)
        assert post.status_code == 200
        elapsed_post = post.json()[0]["elapsed_seconds"]

        # After resume, elapsed should be close to where it was when the
        # break started (within a small tolerance for test scheduling
        # jitter). It must NOT jump forward by the break duration.
        delta = elapsed_post - elapsed_pre
        assert 0 <= delta <= 1, (
            f"elapsed jumped by {delta}s after a {break_seconds}s break; "
            f"expected ~0 (pause_seconds should absorb the break)"
        )

    @pytest.mark.asyncio
    async def test_break_start_broadcast_carries_frozen_elapsed(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        _running_entry: TimeEntry,
    ):
        r = await client.post(
            "/api/work-sessions/break/start",
            json={"break_type": "short"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

        # The cache snapshot taken at break-start is what gets broadcast.
        cached = (await ws_manager.get_active_timers(company_filter=get_company_filter(test_user)))[0]
        cached_elapsed = cached["elapsed_seconds"]

        # Wait and re-hit the HTTP endpoint — it must agree with the
        # broadcast snapshot (both frozen at paused_at).
        await asyncio.sleep(1.2)
        resp = await client.get("/api/time/active", headers=auth_headers)
        assert resp.status_code == 200
        endpoint_elapsed = resp.json()[0]["elapsed_seconds"]

        # Allow a 1-second tolerance: the broadcast snapshot and the
        # endpoint may have captured paused_at fractions of a second apart.
        assert abs(endpoint_elapsed - cached_elapsed) <= 1, (
            f"broadcast elapsed ({cached_elapsed}) and endpoint elapsed "
            f"({endpoint_elapsed}) must agree while frozen"
        )

        # And ws_manager.broadcast_timer_updated was actually awaited as
        # part of the break-start flow.
        ws_manager.broadcast_timer_updated.assert_awaited()
        call_kwargs = ws_manager.broadcast_timer_updated.await_args.kwargs
        broadcast_entry = call_kwargs.get("timer_entry") or (
            ws_manager.broadcast_timer_updated.await_args.args[1]
            if len(ws_manager.broadcast_timer_updated.await_args.args) > 1
            else None
        )
        assert broadcast_entry is not None
        assert broadcast_entry["activity_state"] == "break"
        assert broadcast_entry["elapsed_seconds"] == cached_elapsed


class TestStateAnchoredElapsed:
    """Regression tests for the panel showing break/meeting DURATION
    (not the frozen work-time) on the "Who's Working Now" view.

    The API and WS cache must expose two anchor fields:
      * ``state_started_at``      — ISO timestamp of when the user
        entered the current activity state.
      * ``state_elapsed_seconds`` — whole seconds since that timestamp.

    These let the dashboard render "On break · 00:01:14" ticking upward
    instead of freezing at the work-time pause point.
    """

    @pytest.mark.asyncio
    async def test_working_state_anchors_to_time_entry_start(
        self,
        client: AsyncClient,
        auth_headers: dict,
        _running_entry: TimeEntry,
    ):
        resp = await client.get("/api/time/active", headers=auth_headers)
        assert resp.status_code == 200
        row = resp.json()[0]
        # Anchor is the running TimeEntry's start_time.
        assert row["state_started_at"] == row["start_time"]
        # And the displayed duration matches the work-time elapsed.
        assert row["state_elapsed_seconds"] == row["elapsed_seconds"]

    @pytest.mark.asyncio
    async def test_break_state_anchors_to_break_start_time(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        _running_entry: TimeEntry,
    ):
        from app.models import SessionBreak

        r = await client.post(
            "/api/work-sessions/break/start",
            json={"break_type": "lunch"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

        # Look up the open SessionBreak directly so the test is anchored
        # to the actual DB row, not whatever the API computed.
        from sqlalchemy import select

        brk_rows = (await db_session.execute(
            select(SessionBreak).where(SessionBreak.end_time.is_(None))
        )).scalars().all()
        assert brk_rows, "expected an open SessionBreak after break/start"
        brk = brk_rows[-1]

        await asyncio.sleep(1.1)

        resp = await client.get("/api/time/active", headers=auth_headers)
        assert resp.status_code == 200
        row = resp.json()[0]

        assert row["activity_state"] == "break"
        # Anchor matches the SessionBreak's start_time (ISO compare).
        # Normalize tz suffixes; the row.value comes from .isoformat().
        api_anchor = row["state_started_at"]
        # Drop microseconds and timezone differences by parsing.
        from datetime import datetime as _dt
        api_dt = _dt.fromisoformat(api_anchor.replace("Z", "+00:00"))
        brk_start = brk.start_time
        if brk_start.tzinfo is None:
            brk_start = brk_start.replace(tzinfo=timezone.utc)
        assert abs((api_dt - brk_start).total_seconds()) < 1.0, (
            f"state_started_at {api_anchor} should track SessionBreak.start_time {brk_start}"
        )

        # state_elapsed_seconds should reflect the BREAK duration, not the
        # frozen work elapsed. After ~1.1s of sleep it must be > 0 and
        # MUST advance independently of the frozen ``elapsed_seconds``.
        assert row["state_elapsed_seconds"] >= 1, row

    @pytest.mark.asyncio
    async def test_break_state_elapsed_advances_over_time(
        self,
        client: AsyncClient,
        auth_headers: dict,
        _running_entry: TimeEntry,
    ):
        r = await client.post(
            "/api/work-sessions/break/start",
            json={"break_type": "short"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

        first = await client.get("/api/time/active", headers=auth_headers)
        a = first.json()[0]
        await asyncio.sleep(1.2)
        second = await client.get("/api/time/active", headers=auth_headers)
        b = second.json()[0]

        # Work elapsed stays frozen (PR #26 behavior) ...
        assert a["elapsed_seconds"] == b["elapsed_seconds"]
        # ... but the break duration MUST advance.
        assert b["state_elapsed_seconds"] > a["state_elapsed_seconds"], (
            f"state_elapsed_seconds must advance during a break: "
            f"{a['state_elapsed_seconds']} -> {b['state_elapsed_seconds']}"
        )

    @pytest.mark.asyncio
    async def test_meeting_state_anchors_to_meeting_start_time(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        _running_entry: TimeEntry,
    ):
        from app.models import SessionMeeting
        from sqlalchemy import select

        r = await client.post(
            "/api/work-sessions/meeting/start",
            json={"meeting_type": "internal", "title": "Standup"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

        mtg = (await db_session.execute(
            select(SessionMeeting).where(SessionMeeting.end_time.is_(None))
        )).scalars().first()
        assert mtg is not None

        await asyncio.sleep(1.1)

        resp = await client.get("/api/time/active", headers=auth_headers)
        assert resp.status_code == 200
        row = resp.json()[0]
        assert row["activity_state"] == "meeting"

        from datetime import datetime as _dt
        api_dt = _dt.fromisoformat(row["state_started_at"].replace("Z", "+00:00"))
        mtg_start = mtg.start_time
        if mtg_start.tzinfo is None:
            mtg_start = mtg_start.replace(tzinfo=timezone.utc)
        assert abs((api_dt - mtg_start).total_seconds()) < 1.0

        # Meeting duration advances from 0 and reflects the actual elapsed
        # since meeting/start (1.1s sleep above).
        assert row["state_elapsed_seconds"] >= 1, row

    @pytest.mark.asyncio
    async def test_cache_entry_carries_state_fields_on_break_start(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        _running_entry: TimeEntry,
    ):
        r = await client.post(
            "/api/work-sessions/break/start",
            json={"break_type": "lunch"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        cached = (await ws_manager.get_active_timers(company_filter=get_company_filter(test_user)))[0]
        # Cache snapshot the broadcast uses must include the anchor fields.
        assert "state_started_at" in cached
        assert "state_elapsed_seconds" in cached
        assert cached["activity_state"] == "break"




