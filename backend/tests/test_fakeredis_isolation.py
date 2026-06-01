import fakeredis
import pytest

_seen_token_blacklist_redis_ids: list[int] = []


@pytest.mark.asyncio
async def test_01_token_blacklist_uses_fresh_fakeredis_instance_per_test():
    from app.services import token_blacklist as token_blacklist_module

    redis_client = token_blacklist_module.token_blacklist._redis
    assert redis_client is not None

    await redis_client.set("fakeredis:isolation", "present")
    _seen_token_blacklist_redis_ids.append(id(redis_client))


@pytest.mark.asyncio
async def test_02_token_blacklist_fakeredis_state_does_not_leak_between_tests():
    from app.services import token_blacklist as token_blacklist_module

    redis_client = token_blacklist_module.token_blacklist._redis
    assert redis_client is not None
    assert id(redis_client) not in _seen_token_blacklist_redis_ids

    assert await redis_client.get("fakeredis:isolation") is None


def test_ip_security_client_is_patched_to_fakeredis():
    from app.services import ip_security

    assert isinstance(ip_security.redis_client, fakeredis.FakeStrictRedis)
    ip_security.redis_client.set("fakeredis:ip-security", "ok")
    assert ip_security.redis_client.get("fakeredis:ip-security") == "ok"
