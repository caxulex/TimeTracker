from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    AuditLog,
    BasecampCredentials,
    BasecampProcessedEvent,
    BasecampProjectMapping,
    BasecampWebhookSubscription,
    Company,
    Project,
    Team,
    User,
)
from app.services.auth_service import AuthService
from app.services.basecamp_webhook_service import BasecampWebhookService
from app.services.encryption_service import EncryptionService


@pytest_asyncio.fixture
async def _enc_key(monkeypatch):
    if not settings.API_KEY_ENCRYPTION_KEY:
        monkeypatch.setattr(
            settings,
            "API_KEY_ENCRYPTION_KEY",
            "test-enc-key-basecamp-webhooks",
        )
    monkeypatch.setattr(settings, "WEBHOOK_BASE_URL", "https://timetracker.example.com")
    yield


async def _mk_company(db: AsyncSession, label: str) -> Company:
    unique = uuid.uuid4().hex[:8]
    c = Company(
        name=f"{label} {unique}",
        slug=f"{label.lower()}-{unique}",
        email=f"{label.lower()}-{unique}@example.com",
        status="active",
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


async def _mk_owner_and_team(db: AsyncSession, company: Company) -> Team:
    u = User(
        email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
        name="Owner",
        password_hash=AuthService.hash_password("TestPass123!"),
        role="super_admin",
        company_id=company.id,
        is_active=True,
    )
    db.add(u)
    await db.flush()
    await db.refresh(u)

    t = Team(name="Default Team", owner_id=u.id, company_id=company.id)
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return t


async def _mk_creds(db: AsyncSession, company_id: int, *, account_id: str = "acct-1") -> BasecampCredentials:
    enc = EncryptionService()
    creds = BasecampCredentials(
        company_id=company_id,
        account_id=account_id,
        account_name="Webhook Co",
        access_token_encrypted=enc.encrypt("access-token"),
        refresh_token_encrypted=enc.encrypt("refresh-token"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(creds)
    await db.flush()
    await db.refresh(creds)
    return creds


async def _mk_project_mapping(
    db: AsyncSession,
    *,
    company_id: int,
    team_id: int,
    account_id: str,
    project_id: str,
) -> BasecampProjectMapping:
    project = Project(team_id=team_id, name=f"BC Project {project_id}", description=None)
    db.add(project)
    await db.flush()

    mapping = BasecampProjectMapping(
        company_id=company_id,
        basecamp_account_id=account_id,
        basecamp_project_id=project_id,
        internal_project_id=project.id,
    )
    db.add(mapping)
    await db.flush()
    return mapping


class TestWebhookReceiver:
    @pytest.mark.asyncio
    async def test_unknown_token_returns_404(self, client, db_session: AsyncSession, _enc_key):
        response = await client.post(
            "/api/integrations/basecamp/webhook/unknown-token",
            json={"id": "evt-1", "kind": "todo_updated", "recording": {"id": "1"}},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_valid_token_returns_200(self, client, db_session: AsyncSession, _enc_key):
        company = await _mk_company(db_session, "WH")
        team = await _mk_owner_and_team(db_session, company)
        creds = await _mk_creds(db_session, company.id)
        await _mk_project_mapping(
            db_session,
            company_id=company.id,
            team_id=team.id,
            account_id=creds.account_id,
            project_id="1001",
        )

        token = "valid-secret-token"
        creds.webhook_secret_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        await db_session.commit()

        with patch(
            "app.routers.integrations.basecamp._process_basecamp_event_background",
            new=AsyncMock(),
        ) as mocked_bg:
            response = await client.post(
                f"/api/integrations/basecamp/webhook/{token}",
                json={
                    "id": "evt-2",
                    "kind": "todo_updated",
                    "recording": {
                        "id": "55",
                        "bucket": {"id": "1001"},
                        "parent": {"id": "2002"},
                    },
                },
            )

        assert response.status_code == 200
        mocked_bg.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cross_tenant_bucket_acks_and_logs(self, client, db_session: AsyncSession, _enc_key):
        company = await _mk_company(db_session, "WH2")
        await _mk_owner_and_team(db_session, company)
        creds = await _mk_creds(db_session, company.id)

        token = "tenant-token"
        creds.webhook_secret_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        await db_session.commit()

        response = await client.post(
            f"/api/integrations/basecamp/webhook/{token}",
            json={
                "id": "evt-3",
                "kind": "todo_updated",
                "recording": {
                    "id": "55",
                    "bucket": {"id": "not-mapped"},
                },
            },
        )
        assert response.status_code == 200

        logs = await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "basecamp.webhook.cross_tenant_rejected")
        )
        assert logs.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_idempotent_event_only_processed_once(self, client, db_session: AsyncSession, _enc_key):
        company = await _mk_company(db_session, "WH3")
        team = await _mk_owner_and_team(db_session, company)
        creds = await _mk_creds(db_session, company.id)
        await _mk_project_mapping(
            db_session,
            company_id=company.id,
            team_id=team.id,
            account_id=creds.account_id,
            project_id="2001",
        )

        token = "idem-token"
        creds.webhook_secret_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        await db_session.commit()

        payload = {
            "id": "evt-idem-1",
            "kind": "todo_updated",
            "recording": {
                "id": "90",
                "bucket": {"id": "2001"},
                "parent": {"id": "3001"},
            },
        }

        with patch(
            "app.routers.integrations.basecamp._process_basecamp_event_background",
            new=AsyncMock(),
        ) as mocked_bg:
            r1 = await client.post(f"/api/integrations/basecamp/webhook/{token}", json=payload)
            r2 = await client.post(f"/api/integrations/basecamp/webhook/{token}", json=payload)

        assert r1.status_code == 200
        assert r2.status_code == 200
        mocked_bg.assert_awaited_once()

        rows = await db_session.execute(select(BasecampProcessedEvent).where(BasecampProcessedEvent.event_id == "evt-idem-1"))
        assert rows.scalar_one_or_none() is not None


class TestWebhookService:
    @pytest.mark.asyncio
    async def test_register_for_project_persists_subscription(self, db_session: AsyncSession, _enc_key):
        company = await _mk_company(db_session, "WS")
        await _mk_owner_and_team(db_session, company)
        creds = await _mk_creds(db_session, company.id)

        fake_response = MagicMock()
        fake_response.status_code = 201
        fake_response.content = b"{}"
        fake_response.json.return_value = {"id": "wh-001"}

        fake_client = AsyncMock()
        fake_client.__aenter__.return_value = fake_client
        fake_client.__aexit__.return_value = None
        fake_client.post.return_value = fake_response

        with patch("app.services.basecamp_webhook_service.httpx.AsyncClient", return_value=fake_client), patch.object(
            BasecampWebhookService,
            "_basecamp_headers",
            new=AsyncMock(return_value={"Authorization": "Bearer t"}),
        ):
            sub = await BasecampWebhookService.register_for_project(
                creds=creds,
                project_id="901",
                db=db_session,
            )

        assert sub.basecamp_webhook_id == "wh-001"
        rows = await db_session.execute(
            select(BasecampWebhookSubscription).where(
                BasecampWebhookSubscription.credentials_id == creds.id,
                BasecampWebhookSubscription.basecamp_project_id == "901",
            )
        )
        assert rows.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_reconcile_registers_missing_local_subscription(self, db_session: AsyncSession, _enc_key):
        company = await _mk_company(db_session, "WS2")
        team = await _mk_owner_and_team(db_session, company)
        creds = await _mk_creds(db_session, company.id)
        await _mk_project_mapping(
            db_session,
            company_id=company.id,
            team_id=team.id,
            account_id=creds.account_id,
            project_id="7001",
        )

        with patch.object(
            BasecampWebhookService,
            "_list_remote_webhooks",
            new=AsyncMock(return_value=[]),
        ), patch.object(
            BasecampWebhookService,
            "register_for_project",
            new=AsyncMock(return_value=BasecampWebhookSubscription(
                credentials_id=creds.id,
                basecamp_project_id="7001",
                basecamp_webhook_id="wh-7001",
            )),
        ) as mocked_register:
            result = await BasecampWebhookService.reconcile_subscriptions(creds, db_session)

        assert result["registered"] == 1
        mocked_register.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reconcile_re_registers_when_remote_missing(self, db_session: AsyncSession, _enc_key):
        company = await _mk_company(db_session, "WS3")
        team = await _mk_owner_and_team(db_session, company)
        creds = await _mk_creds(db_session, company.id)
        await _mk_project_mapping(
            db_session,
            company_id=company.id,
            team_id=team.id,
            account_id=creds.account_id,
            project_id="7002",
        )
        existing = BasecampWebhookSubscription(
            credentials_id=creds.id,
            basecamp_project_id="7002",
            basecamp_webhook_id="wh-old",
            active=True,
        )
        db_session.add(existing)
        await db_session.commit()

        with patch.object(
            BasecampWebhookService,
            "_list_remote_webhooks",
            new=AsyncMock(return_value=[{"id": "wh-other"}]),
        ), patch.object(
            BasecampWebhookService,
            "register_for_project",
            new=AsyncMock(return_value=existing),
        ) as mocked_register:
            result = await BasecampWebhookService.reconcile_subscriptions(creds, db_session)

        assert result["re_registered"] == 1
        mocked_register.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_flag_stale_subscriptions_marks_unhealthy(self, db_session: AsyncSession, _enc_key):
        company = await _mk_company(db_session, "WS4")
        await _mk_owner_and_team(db_session, company)
        creds = await _mk_creds(db_session, company.id)
        sub = BasecampWebhookSubscription(
            credentials_id=creds.id,
            basecamp_project_id="stale-1",
            basecamp_webhook_id="wh-stale",
            active=True,
            last_event_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        db_session.add(sub)
        await db_session.commit()

        count = await BasecampWebhookService.flag_stale_subscriptions(
            creds,
            db_session,
            stale_days=7,
        )
        await db_session.commit()

        assert count == 1
        refreshed = await db_session.get(BasecampWebhookSubscription, sub.id)
        assert refreshed is not None
        assert refreshed.last_error is not None

    @pytest.mark.asyncio
    async def test_flag_stale_subscriptions_ignores_new_null_last_event(
        self,
        db_session: AsyncSession,
        _enc_key,
    ):
        company = await _mk_company(db_session, "WS5")
        await _mk_owner_and_team(db_session, company)
        creds = await _mk_creds(db_session, company.id)
        sub = BasecampWebhookSubscription(
            credentials_id=creds.id,
            basecamp_project_id="fresh-null-event",
            basecamp_webhook_id="wh-fresh-null",
            active=True,
            last_event_at=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.add(sub)
        await db_session.commit()

        count = await BasecampWebhookService.flag_stale_subscriptions(
            creds,
            db_session,
            stale_days=7,
        )
        await db_session.commit()

        assert count == 0
        refreshed = await db_session.get(BasecampWebhookSubscription, sub.id)
        assert refreshed is not None
        assert refreshed.last_error is None

    @pytest.mark.asyncio
    async def test_flag_stale_subscriptions_marks_old_null_last_event(
        self,
        db_session: AsyncSession,
        _enc_key,
    ):
        company = await _mk_company(db_session, "WS6")
        await _mk_owner_and_team(db_session, company)
        creds = await _mk_creds(db_session, company.id)
        sub = BasecampWebhookSubscription(
            credentials_id=creds.id,
            basecamp_project_id="old-null-event",
            basecamp_webhook_id="wh-old-null",
            active=True,
            last_event_at=None,
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        db_session.add(sub)
        await db_session.commit()

        count = await BasecampWebhookService.flag_stale_subscriptions(
            creds,
            db_session,
            stale_days=7,
        )
        await db_session.commit()

        assert count == 1
        refreshed = await db_session.get(BasecampWebhookSubscription, sub.id)
        assert refreshed is not None
        assert refreshed.last_error is not None
