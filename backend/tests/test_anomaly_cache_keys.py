"""Regression tests for anomaly cache key dimensions.

These tests ensure cache keys include period and scope dimensions, so
results are not reused across incompatible requests.
"""

import pytest

from app.ai.utils.cache_manager import AICacheManager


class _FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def setex(self, key: str, _ttl: int, value: str):
        self._store[key] = value
        return True


@pytest.mark.asyncio
async def test_anomaly_cache_separates_same_date_by_period_days():
    cache = AICacheManager(redis_client=_FakeRedis())
    day = "2026-06-10"

    payload_7 = {"period_days": 7, "anomalies": [{"id": "a7"}]}
    payload_30 = {"period_days": 30, "anomalies": [{"id": "a30"}]}

    ok_7 = await cache.set_anomaly_cache(
        day,
        payload_7,
        user_id=42,
        period_days=7,
    )
    ok_30 = await cache.set_anomaly_cache(
        day,
        payload_30,
        user_id=42,
        period_days=30,
    )

    assert ok_7 is True
    assert ok_30 is True

    hit_7 = await cache.get_anomaly_cache(
        day,
        user_id=42,
        period_days=7,
    )
    hit_30 = await cache.get_anomaly_cache(
        day,
        user_id=42,
        period_days=30,
    )

    assert hit_7 == payload_7
    assert hit_30 == payload_30
    assert hit_7 != hit_30


@pytest.mark.asyncio
async def test_anomaly_cache_separates_team_scope_when_applicable():
    cache = AICacheManager(redis_client=_FakeRedis())
    day = "2026-06-10"

    team_5_payload = {"team_id": 5, "anomalies": [{"id": "t5"}]}
    team_9_payload = {"team_id": 9, "anomalies": [{"id": "t9"}]}

    ok_5 = await cache.set_anomaly_cache(
        day,
        team_5_payload,
        period_days=30,
        team_id=5,
        company_id=11,
    )
    ok_9 = await cache.set_anomaly_cache(
        day,
        team_9_payload,
        period_days=30,
        team_id=9,
        company_id=11,
    )

    assert ok_5 is True
    assert ok_9 is True

    hit_5 = await cache.get_anomaly_cache(
        day,
        period_days=30,
        team_id=5,
        company_id=11,
    )
    hit_9 = await cache.get_anomaly_cache(
        day,
        period_days=30,
        team_id=9,
        company_id=11,
    )

    assert hit_5 == team_5_payload
    assert hit_9 == team_9_payload
    assert hit_5 != hit_9
