from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    AuditLog,
    BasecampCredentials,
    BasecampProjectMapping,
    Company,
    Team,
    User,
)
from app.services.auth_service import AuthService
from app.services.basecamp_service import (
    BASECAMP_SYNC_SYSTEM_EMAIL,
    BasecampService,
)
from app.services.encryption_service import EncryptionService


@pytest_asyncio.fixture
async def configured_basecamp(monkeypatch):
    async def _not_blacklisted(_jti: str) -> bool:
        return False

    monkeypatch.setattr(
        "app.dependencies._check_blacklist_or_fail_closed",
        _not_blacklisted,
    )
    monkeypatch.setattr(settings, "BASECAMP_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "BASECAMP_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(
        settings,
        "BASECAMP_REDIRECT_URI",
        "https://timetracker.shaemarcus.com/api/integrations/basecamp/callback",
    )
    if not settings.API_KEY_ENCRYPTION_KEY:
        monkeypatch.setattr(settings, "API_KEY_ENCRYPTION_KEY", "test-basecamp-sync-audit-key")
    yield


async def _mk_company(db: AsyncSession) -> Company:
    unique = uuid.uuid4().hex[:8]
    c = Company(
        name=f"Audit Co {unique}",
        slug=f"audit-co-{unique}",
        email=f"audit-{unique}@example.com",
        status="active",
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


async def _mk_super_admin(db: AsyncSession, company: Company) -> User:
    u = User(
        email=f"sa-{uuid.uuid4().hex[:8]}@example.com",
        name="Super Admin",
        password_hash=AuthService.hash_password("TestPass123!"),
        role="super_admin",
        company_id=company.id,
        is_active=True,
    )
    db.add(u)
    await db.flush()
    await db.refresh(u)
    return u


async def _mk_team(db: AsyncSession, company: Company, owner: User) -> Team:
    t = Team(name="Default Team", owner_id=owner.id, company_id=company.id)
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return t


def _mk_creds(company_id: int) -> BasecampCredentials:
    enc = EncryptionService()
    return BasecampCredentials(
        company_id=company_id,
        account_id="acct-1",
        account_name="Audit Account",
        access_token_encrypted=enc.encrypt("access-token"),
        refresh_token_encrypted=enc.encrypt("refresh-token"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )


def _bearer(user: User) -> dict:
    token = AuthService.create_access_token({"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


class TestBasecampSyncAudit:
    @pytest.mark.asyncio
    async def test_manual_sync_endpoint_writes_project_audit_with_admin_identity(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        admin = await _mk_super_admin(db_session, company)
        await _mk_team(db_session, company, admin)

        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.commit()

        async def fake_list_projects(_creds, _db):
            return [
                {
                    "id": "p-manual-1",
                    "name": "Manual Synced Project",
                    "description": "From Basecamp",
                    "status": "active",
                    "created_at": "2026-05-26T10:00:00Z",
                }
            ]

        with patch.object(BasecampService, "list_projects", side_effect=fake_list_projects), patch.object(
            BasecampService,
            "_get_valid_access_token",
            new=AsyncMock(return_value="token"),
        ), patch.object(
            BasecampService,
            "_list_todolists",
            new=AsyncMock(return_value=[]),
        ):
            resp = await client.post(
                "/api/integrations/basecamp/sync",
                headers=_bearer(admin),
                json={"dry_run": False},
            )

        assert resp.status_code == 200

        row = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "CREATE",
                AuditLog.resource_type == "project",
                AuditLog.details.ilike("%Basecamp project p-manual-1%"),
            )
        )
        log = row.scalar_one_or_none()
        assert log is not None
        assert log.user_id == admin.id
        assert log.user_email == admin.email
        assert "manual sync" in (log.details or "")

    @pytest.mark.asyncio
    async def test_project_update_writes_old_values_name(
        self,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        admin = await _mk_super_admin(db_session, company)
        await _mk_team(db_session, company, admin)

        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        payload = [
            {
                "id": "p-upd-1",
                "name": "Project Alpha",
                "description": "desc",
                "status": "active",
                "created_at": "2026-05-26T10:00:00Z",
            }
        ]

        async def fake_list_projects(_creds, _db):
            return payload

        with patch.object(BasecampService, "list_projects", side_effect=fake_list_projects):
            await BasecampService.sync_projects_to_company(
                creds,
                company.id,
                db_session,
                dry_run=False,
                triggered_by_user_id=admin.id,
                triggered_by_user_email=admin.email,
            )
            payload[0]["name"] = "Project Alpha Renamed"
            await BasecampService.sync_projects_to_company(
                creds,
                company.id,
                db_session,
                dry_run=False,
                triggered_by_user_id=admin.id,
                triggered_by_user_email=admin.email,
            )

        row = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "UPDATE",
                AuditLog.resource_type == "project",
            )
        )
        log = row.scalar_one_or_none()
        assert log is not None
        old_values = json.loads(log.old_values or "{}")
        new_values = json.loads(log.new_values or "{}")
        assert old_values["name"] == "Project Alpha"
        assert new_values["name"] == "Project Alpha Renamed"

    @pytest.mark.asyncio
    async def test_scheduler_project_sync_uses_system_identity_and_no_noise_on_unchanged(
        self,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        owner = await _mk_super_admin(db_session, company)
        await _mk_team(db_session, company, owner)

        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        async def fake_list_projects(_creds, _db):
            return [
                {
                    "id": "p-sched-1",
                    "name": "Scheduler Project",
                    "description": "desc",
                    "status": "active",
                    "created_at": "2026-05-26T10:00:00Z",
                }
            ]

        with patch.object(BasecampService, "list_projects", side_effect=fake_list_projects):
            first = await BasecampService.sync_projects_to_company(
                creds,
                company.id,
                db_session,
                dry_run=False,
            )

            count_before = await db_session.execute(select(func.count(AuditLog.id)))
            audit_count_before = count_before.scalar_one()

            second = await BasecampService.sync_projects_to_company(
                creds,
                company.id,
                db_session,
                dry_run=False,
            )

            count_after = await db_session.execute(select(func.count(AuditLog.id)))
            audit_count_after = count_after.scalar_one()

        assert first["created"] == 1
        assert second["unchanged"] == 1
        assert audit_count_before == audit_count_after

        project_row = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "CREATE",
                AuditLog.resource_type == "project",
                AuditLog.details.ilike("%Basecamp project p-sched-1%"),
            )
        )
        project_log = project_row.scalar_one_or_none()
        assert project_log is not None
        assert project_log.user_id is None
        assert project_log.user_email == BASECAMP_SYNC_SYSTEM_EMAIL
        assert "daily scheduler" in (project_log.details or "")

        mapping_row = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "CREATE",
                AuditLog.resource_type == "basecamp_project_mapping",
                AuditLog.details.ilike("%project p-sched-1%"),
            )
        )
        assert mapping_row.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_task_create_writes_task_audit_entry_with_system_identity(
        self,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        owner = await _mk_super_admin(db_session, company)
        team = await _mk_team(db_session, company, owner)

        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        async def fake_list_projects(_creds, _db):
            return [
                {
                    "id": "p-task-1",
                    "name": "Task Project",
                    "description": "desc",
                    "status": "active",
                    "created_at": "2026-05-26T10:00:00Z",
                }
            ]

        with patch.object(BasecampService, "list_projects", side_effect=fake_list_projects):
            await BasecampService.sync_projects_to_company(
                creds,
                company.id,
                db_session,
                dry_run=False,
            )

        project_mapping = await db_session.execute(
            select(BasecampProjectMapping).where(
                BasecampProjectMapping.company_id == company.id,
                BasecampProjectMapping.basecamp_project_id == "p-task-1",
            )
        )
        mapping = project_mapping.scalar_one_or_none()
        assert mapping is not None

        with patch.object(
            BasecampService,
            "_get_valid_access_token",
            new=AsyncMock(return_value="token"),
        ), patch.object(
            BasecampService,
            "_list_todolists",
            new=AsyncMock(return_value=[{"id": "list-1", "title": "Backlog"}]),
        ), patch.object(
            BasecampService,
            "_list_todos_in_list",
            new=AsyncMock(
                return_value=[
                    {
                        "id": "todo-1",
                        "content": "Implement audit",
                        "description": "traceability",
                        "completed": False,
                        "due_on": None,
                        "created_at": "2026-05-26T10:05:00Z",
                        "position": 1,
                    }
                ]
            ),
        ), patch.object(
            BasecampService,
            "_get_todo_detail",
            new=AsyncMock(
                return_value={
                    "id": "todo-1",
                    "content": "Implement audit",
                    "description": "traceability",
                    "completed": False,
                    "status": "active",
                    "due_on": None,
                    "created_at": "2026-05-26T10:05:00Z",
                    "position": 1,
                    "steps": [],
                }
            ),
        ):
            report = await BasecampService.sync_todos_for_company(
                creds,
                company.id,
                db_session,
                dry_run=False,
            )

        assert report["todos_created"] == 1

        row = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "CREATE",
                AuditLog.resource_type == "task",
                AuditLog.details.ilike("%Basecamp to-do todo-1%"),
            )
        )
        log = row.scalar_one_or_none()
        assert log is not None
        assert log.user_id is None
        assert log.user_email == BASECAMP_SYNC_SYSTEM_EMAIL
        assert "daily scheduler" in (log.details or "")

        task_values = json.loads(log.new_values or "{}")
        assert task_values["project_id"] == mapping.internal_project_id
        assert task_values["status"] == "TODO"
        assert task_values["name"] == "[Backlog] Implement audit"
