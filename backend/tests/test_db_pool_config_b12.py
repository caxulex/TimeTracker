"""B12: smoke tests for env-driven DB pool selection.

Verifies:
- ENVIRONMENT=test/development -> NullPool.
- ENVIRONMENT=production       -> AsyncAdaptedQueuePool with the configured
  pool_size / max_overflow / timeout / recycle / pre_ping.

The tests build *isolated* engines via ``app.database._build_engine``
under monkeypatched settings; the global ``engine`` is not touched.
"""
import pytest
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from app import database
from app.config import settings


@pytest.mark.asyncio
async def test_pool_class_is_nullpool_in_test_env(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    eng = database._build_engine()
    try:
        assert isinstance(eng.pool, NullPool), (
            f"expected NullPool in test env, got {type(eng.pool).__name__}"
        )
    finally:
        await eng.dispose()


@pytest.mark.asyncio
async def test_pool_class_is_nullpool_in_development_env(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    eng = database._build_engine()
    try:
        assert isinstance(eng.pool, NullPool)
    finally:
        await eng.dispose()


@pytest.mark.asyncio
async def test_pool_class_is_queuepool_in_production_env(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "DB_POOL_SIZE", 7)
    monkeypatch.setattr(settings, "DB_MAX_OVERFLOW", 11)
    monkeypatch.setattr(settings, "DB_POOL_TIMEOUT", 13)
    monkeypatch.setattr(settings, "DB_POOL_RECYCLE", 17)
    monkeypatch.setattr(settings, "DB_POOL_PRE_PING", True)

    eng = database._build_engine()
    try:
        assert isinstance(eng.pool, AsyncAdaptedQueuePool), (
            f"expected AsyncAdaptedQueuePool in production env, "
            f"got {type(eng.pool).__name__}"
        )
        assert eng.pool.size() == 7
        # SQLAlchemy stores configured overflow as ``_max_overflow`` on QueuePool.
        assert eng.pool._max_overflow == 11
        assert eng.pool._timeout == 13
        assert eng.pool._recycle == 17
        # pre-ping flag exposed via ``_pre_ping``.
        assert eng.pool._pre_ping is True
    finally:
        await eng.dispose()
