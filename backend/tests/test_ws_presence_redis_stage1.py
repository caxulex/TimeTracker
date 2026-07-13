import inspect
from datetime import timedelta

import fakeredis
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.dependencies import FILTER_NULL_COMPANY
from app.routers.websocket import manager, PRESENCE_STALE_THRESHOLD_SEC
from app.utils.timewindow import now_utc


@pytest_asyncio.fixture(autouse=True)
async def _patch_ws_presence_redis():
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager._redis = fake_redis
    manager.user_companies.clear()
    yield fake_redis
    await fake_redis.flushdb()
    await fake_redis.aclose()
    manager._redis = None


@pytest.mark.asyncio
async def test_cross_process_visibility():
    await manager.set_active_timer(
        201,
        {
            "company_id": 2,
            "user_name": "Worker A",
            "start_time": now_utc().isoformat(),
        },
    )

    loaded = await manager.get_active_timers(company_filter=2)
    assert [t["user_id"] for t in loaded] == [201]

    await manager.clear_active_timer(201, company_id=2)
    loaded_after_clear = await manager.get_active_timers(company_filter=2)
    assert loaded_after_clear == []


@pytest.mark.asyncio
async def test_stale_entry_filtered():
    redis_client = await manager.get_redis()
    stale_hb = (now_utc() - timedelta(seconds=PRESENCE_STALE_THRESHOLD_SEC + 10)).isoformat()
    key = manager._presence_key(2)
    await redis_client.hset(
        key,
        "301",
        (
            '{"user_id":301,"company_id":2,"user_name":"Stale",'
            '"heartbeat_at":"' + stale_hb + '","start_time":"' + stale_hb + '"}'
        ),
    )

    timers = await manager.get_active_timers(company_filter=2)
    assert timers == []
    assert await redis_client.hget(key, "301") is None


@pytest.mark.asyncio
async def test_tenant_isolation():
    await manager.set_active_timer(401, {"company_id": 2, "user_name": "C2"})
    await manager.set_active_timer(402, {"company_id": 3, "user_name": "C3"})

    c2 = await manager.get_active_timers(company_filter=2)
    c3 = await manager.get_active_timers(company_filter=3)

    assert [t["user_id"] for t in c2] == [401]
    assert [t["user_id"] for t in c3] == [402]


@pytest.mark.asyncio
async def test_redis_down_failclosed(monkeypatch):
    async def _raise():
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(manager, "get_redis", _raise)

    await manager.set_active_timer(501, {"company_id": 2, "user_name": "X"})
    await manager.clear_active_timer(501, company_id=2)
    timers = await manager.get_active_timers(company_filter=2)
    assert timers == []


@pytest.mark.asyncio
async def test_redis_down_does_not_break_timer(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch,
):
    # Prepare project/team for timer start
    team_response = await client.post(
        "/api/teams",
        headers=auth_headers,
        json={"name": "Presence Redis Down Team"},
    )
    assert team_response.status_code in (200, 201)
    team_id = team_response.json()["id"]

    project_response = await client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": "Presence Redis Down Project", "team_id": team_id},
    )
    assert project_response.status_code in (200, 201)
    project_id = project_response.json()["id"]

    start_response = await client.post(
        "/api/time/start",
        headers=auth_headers,
        json={"project_id": project_id, "description": "redis down stop test"},
    )
    assert start_response.status_code in (200, 201)

    async def _raise():
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(manager, "get_redis", _raise)

    stop_response = await client.post("/api/time/stop", headers=auth_headers)
    assert stop_response.status_code == 200


@pytest.mark.asyncio
async def test_scheduler_clears_presence():
    from scripts.close_stale_sessions import _clear_presence_for_affected_users

    await manager.set_active_timer(601, {"company_id": 2, "user_name": "S1"})
    await manager.set_active_timer(602, {"company_id": None, "user_name": "S2"})

    await _clear_presence_for_affected_users({601: 2, 602: None})

    assert await manager.get_active_timers(company_filter=2) == []
    platform = await manager.get_active_timers(company_filter=FILTER_NULL_COMPANY)
    assert platform == []


def test_work_sessions_refresh_no_direct_active_timers_get():
    from app.routers import work_sessions

    src = inspect.getsource(work_sessions._refresh_active_timer_cache)
    assert "active_timers.get(" not in src
