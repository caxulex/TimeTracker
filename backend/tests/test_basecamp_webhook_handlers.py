from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuditLog, BasecampCredentials, Company
from app.services.basecamp_webhook_handlers import BasecampWebhookHandlers
from app.services.encryption_service import EncryptionService


@pytest_asyncio.fixture
async def _enc_key(monkeypatch):
    if not settings.API_KEY_ENCRYPTION_KEY:
        monkeypatch.setattr(settings, "API_KEY_ENCRYPTION_KEY", "test-enc-key-webhook-handlers")
    yield


async def _mk_company(db: AsyncSession) -> Company:
    unique = uuid.uuid4().hex[:8]
    c = Company(
        name=f"Handlers {unique}",
        slug=f"handlers-{unique}",
        email=f"handlers-{unique}@example.com",
        status="active",
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


async def _mk_creds(db: AsyncSession, company_id: int) -> BasecampCredentials:
    enc = EncryptionService()
    creds = BasecampCredentials(
        company_id=company_id,
        account_id="acct-handlers",
        account_name="Handlers Co",
        access_token_encrypted=enc.encrypt("access-token"),
        refresh_token_encrypted=enc.encrypt("refresh-token"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(creds)
    await db.flush()
    await db.refresh(creds)
    return creds


class TestWebhookHandlerRouting:
    @pytest.mark.asyncio
    async def test_todo_kind_routes_to_single_todo_sync(self, db_session: AsyncSession, _enc_key):
        company = await _mk_company(db_session)
        creds = await _mk_creds(db_session, company.id)

        event = {
            "id": "evt-1",
            "kind": "todo_updated",
            "recording": {
                "id": "todo-1",
                "bucket": {"id": "bucket-1"},
                "parent": {"id": "list-1"},
            },
        }

        with patch(
            "app.services.basecamp_webhook_handlers.BasecampService.sync_single_todo_for_company",
            new=AsyncMock(return_value={}),
        ) as todo_sync:
            await BasecampWebhookHandlers.handle_event(event=event, credentials=creds, db=db_session)

        todo_sync.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_todolist_cascade_kind_routes_to_resync(self, db_session: AsyncSession, _enc_key):
        company = await _mk_company(db_session)
        creds = await _mk_creds(db_session, company.id)

        event = {
            "id": "evt-2",
            "kind": "todolist_archived",
            "recording": {
                "id": "list-99",
                "bucket": {"id": "bucket-99"},
            },
        }

        with patch(
            "app.services.basecamp_webhook_handlers.BasecampService.resync_todolist_for_company",
            new=AsyncMock(return_value={}),
        ) as list_sync:
            await BasecampWebhookHandlers.handle_event(event=event, credentials=creds, db=db_session)

        list_sync.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unhandled_kind_logs_and_fallback_refetch(self, db_session: AsyncSession, _enc_key):
        company = await _mk_company(db_session)
        creds = await _mk_creds(db_session, company.id)

        event = {
            "id": "evt-3",
            "kind": "mystery_kind",
            "recording": {
                "id": "todo-3",
                "bucket": {"id": "bucket-3"},
                "parent": {"id": "list-3"},
            },
        }

        with patch(
            "app.services.basecamp_webhook_handlers.BasecampService.sync_single_todo_for_company",
            new=AsyncMock(return_value={}),
        ) as fallback:
            await BasecampWebhookHandlers.handle_event(event=event, credentials=creds, db=db_session)
            await db_session.commit()

        fallback.assert_awaited_once()
        row = await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "basecamp.webhook.unhandled_kind")
        )
        assert row.scalar_one_or_none() is not None
