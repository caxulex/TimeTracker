from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import APIKey, User
from app.services.api_key_service import APIKeyService


@pytest.fixture(autouse=True)
async def _ensure_api_key_health_columns(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            """
            ALTER TABLE api_keys
            ADD COLUMN IF NOT EXISTS last_successful_call_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS last_failed_call_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS success_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS failure_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS last_error_message TEXT NULL,
            ADD COLUMN IF NOT EXISTS last_error_status_code INTEGER NULL
            """
        )
    )
    await db_session.commit()


async def _create_api_key(db_session: AsyncSession, admin_user: User) -> APIKey:
    api_key = APIKey(
        provider="gemini",
        encrypted_key="enc:test",
        key_preview="...1234",
        label="Primary Gemini",
        is_active=True,
        created_by=admin_user.id,
        usage_count=0,
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)
    return api_key


@pytest.mark.asyncio
async def test_record_success_updates_fields(db_session: AsyncSession, admin_user: User) -> None:
    api_key = await _create_api_key(db_session, admin_user)
    service = APIKeyService(db_session)

    await service.record_success(api_key.id)

    refreshed = (await db_session.execute(select(APIKey).where(APIKey.id == api_key.id))).scalar_one()
    assert refreshed.success_count == 1
    assert refreshed.usage_count == 1
    assert refreshed.last_successful_call_at is not None
    assert refreshed.last_used_at is not None


@pytest.mark.asyncio
async def test_record_failure_updates_fields(db_session: AsyncSession, admin_user: User) -> None:
    api_key = await _create_api_key(db_session, admin_user)
    service = APIKeyService(db_session)

    await service.record_failure(api_key.id, "quota exhausted", 429)

    refreshed = (await db_session.execute(select(APIKey).where(APIKey.id == api_key.id))).scalar_one()
    assert refreshed.failure_count == 1
    assert refreshed.usage_count == 1
    assert refreshed.last_failed_call_at is not None
    assert refreshed.last_used_at is not None
    assert refreshed.last_error_message == "quota exhausted"
    assert refreshed.last_error_status_code == 429


@pytest.mark.asyncio
async def test_record_failure_truncates_long_messages(db_session: AsyncSession, admin_user: User) -> None:
    api_key = await _create_api_key(db_session, admin_user)
    service = APIKeyService(db_session)
    long_error = "x" * 2000

    await service.record_failure(api_key.id, long_error)

    refreshed = (await db_session.execute(select(APIKey).where(APIKey.id == api_key.id))).scalar_one()
    assert refreshed.last_error_message is not None
    assert len(refreshed.last_error_message) <= 1000


@pytest.mark.asyncio
async def test_health_status_healthy(db_session: AsyncSession, admin_user: User) -> None:
    api_key = await _create_api_key(db_session, admin_user)
    now = datetime.now(timezone.utc)
    api_key.usage_count = 10
    api_key.success_count = 10
    api_key.failure_count = 0
    api_key.last_successful_call_at = now - timedelta(hours=2)
    api_key.last_failed_call_at = now - timedelta(hours=2)
    await db_session.commit()
    await db_session.refresh(api_key)

    assert api_key.health_status == "healthy"


@pytest.mark.asyncio
async def test_health_status_failing(db_session: AsyncSession, admin_user: User) -> None:
    api_key = await _create_api_key(db_session, admin_user)
    now = datetime.now(timezone.utc)
    api_key.usage_count = 12
    api_key.success_count = 0
    api_key.failure_count = 12
    api_key.last_failed_call_at = now - timedelta(minutes=10)
    await db_session.commit()
    await db_session.refresh(api_key)

    assert api_key.health_status == "failing"


@pytest.mark.asyncio
async def test_health_status_degraded(db_session: AsyncSession, admin_user: User) -> None:
    api_key = await _create_api_key(db_session, admin_user)
    now = datetime.now(timezone.utc)
    api_key.usage_count = 15
    api_key.success_count = 12
    api_key.failure_count = 3
    api_key.last_successful_call_at = now - timedelta(hours=2)
    api_key.last_failed_call_at = now - timedelta(minutes=20)
    await db_session.commit()
    await db_session.refresh(api_key)

    assert api_key.health_status == "degraded"


@pytest.mark.asyncio
async def test_health_status_unused(db_session: AsyncSession, admin_user: User) -> None:
    api_key = await _create_api_key(db_session, admin_user)
    api_key.usage_count = 0
    api_key.success_count = 0
    api_key.failure_count = 0
    api_key.last_successful_call_at = None
    api_key.last_failed_call_at = None
    await db_session.commit()
    await db_session.refresh(api_key)

    assert api_key.health_status == "unused"
