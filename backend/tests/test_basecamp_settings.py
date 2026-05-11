"""Tests for Basecamp v2 settings endpoint + sync target-team behavior.

Covers PATCH /api/integrations/basecamp/settings, the new fields on
GET /api/integrations/basecamp/status, and the sync logic's use of
``target_team_id`` (with fallback to lowest-id team).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    BasecampCredentials,
    BasecampProjectMapping,
    Company,
    Project,
    Team,
    User,
)
from app.services.auth_service import AuthService
from app.services.basecamp_service import BasecampService
from app.services.encryption_service import EncryptionService


# ----------------------------------------------------------------------
# Local fixtures (intentionally duplicated from test_basecamp_integration
# to avoid touching conftest.py per the PR constraints)
# ----------------------------------------------------------------------


@pytest_asyncio.fixture
async def _bypass_blacklist(monkeypatch):
    async def _ok(_jti):
        return False
    monkeypatch.setattr(
        "app.dependencies._check_blacklist_or_fail_closed", _ok
    )
    yield


@pytest_asyncio.fixture
async def _fake_state_store(monkeypatch):
    store: dict[str, dict] = {}

    async def _store(state, payload):
        store[state] = payload

    async def _consume(state):
        return store.pop(state, None)

    monkeypatch.setattr(
        "app.routers.integrations.basecamp._store_state_token", _store
    )
    monkeypatch.setattr(
        "app.routers.integrations.basecamp._consume_state_token", _consume
    )
    yield store


@pytest_asyncio.fixture
async def configured_basecamp(monkeypatch, _bypass_blacklist, _fake_state_store):
    monkeypatch.setattr(settings, "BASECAMP_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "BASECAMP_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(
        settings,
        "BASECAMP_REDIRECT_URI",
        "https://timetracker.shaemarcus.com/api/integrations/basecamp/callback",
    )
    if not settings.API_KEY_ENCRYPTION_KEY:
        monkeypatch.setattr(
            settings,
            "API_KEY_ENCRYPTION_KEY",
            "test-encryption-key-for-basecamp-settings",
        )
    yield


async def _mk_company(db: AsyncSession, slug_prefix: str = "co") -> Company:
    unique = uuid.uuid4().hex[:8]
    c = Company(
        name=f"BC Co {unique}",
        slug=f"{slug_prefix}-{unique}",
        email=f"{slug_prefix}-{unique}@example.com",
        status="active",
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


async def _mk_user(
    db: AsyncSession, company: Company, role: str = "super_admin"
) -> User:
    u = User(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        name=f"User {role}",
        password_hash=AuthService.hash_password("TestPass123!"),
        role=role,
        company_id=company.id,
        is_active=True,
    )
    db.add(u)
    await db.flush()
    await db.refresh(u)
    return u


async def _mk_team(db: AsyncSession, company: Company, owner: User, name: str = "T") -> Team:
    t = Team(name=name, owner_id=owner.id, company_id=company.id)
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return t


def _mk_creds(company_id: int, **kw) -> BasecampCredentials:
    enc = EncryptionService()
    return BasecampCredentials(
        company_id=company_id,
        account_id=kw.get("account_id", "999999999"),
        account_name=kw.get("account_name", "Acme"),
        access_token_encrypted=enc.encrypt("at-1"),
        refresh_token_encrypted=enc.encrypt("rt-1"),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=3600),
        auto_sync_enabled=kw.get("auto_sync_enabled", False),
        target_team_id=kw.get("target_team_id"),
    )


def _bearer(user: User) -> dict:
    token = AuthService.create_access_token(
        {"sub": str(user.id), "email": user.email}
    )
    return {"Authorization": f"Bearer {token}"}


# ----------------------------------------------------------------------
# PATCH /settings tests
# ----------------------------------------------------------------------


class TestPatchSettings:
    @pytest.mark.asyncio
    async def test_patch_settings_sets_target_team(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        sa_user = await _mk_user(db_session, company, "super_admin")
        team = await _mk_team(db_session, company, sa_user, "Engineering")
        db_session.add(_mk_creds(company.id))
        await db_session.commit()

        resp = await client.patch(
            "/api/integrations/basecamp/settings",
            headers=_bearer(sa_user),
            json={"target_team_id": team.id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["target_team_id"] == team.id
        assert body["target_team_name"] == "Engineering"
        assert body["auto_sync_enabled"] is False

        # Persisted
        row = await db_session.execute(
            select(BasecampCredentials).where(
                BasecampCredentials.company_id == company.id
            )
        )
        creds = row.scalar_one()
        assert creds.target_team_id == team.id

    @pytest.mark.asyncio
    async def test_patch_settings_sets_auto_sync_enabled(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        sa_user = await _mk_user(db_session, company, "super_admin")
        db_session.add(_mk_creds(company.id))
        await db_session.commit()

        resp = await client.patch(
            "/api/integrations/basecamp/settings",
            headers=_bearer(sa_user),
            json={"auto_sync_enabled": True},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["auto_sync_enabled"] is True
        assert body["target_team_id"] is None

        row = await db_session.execute(
            select(BasecampCredentials).where(
                BasecampCredentials.company_id == company.id
            )
        )
        creds = row.scalar_one()
        assert creds.auto_sync_enabled is True

    @pytest.mark.asyncio
    async def test_patch_settings_sets_both_fields_atomically(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        sa_user = await _mk_user(db_session, company, "super_admin")
        team = await _mk_team(db_session, company, sa_user, "Ops")
        db_session.add(_mk_creds(company.id))
        await db_session.commit()

        resp = await client.patch(
            "/api/integrations/basecamp/settings",
            headers=_bearer(sa_user),
            json={"target_team_id": team.id, "auto_sync_enabled": True},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["target_team_id"] == team.id
        assert body["target_team_name"] == "Ops"
        assert body["auto_sync_enabled"] is True

    @pytest.mark.asyncio
    async def test_patch_settings_rejects_team_from_other_company(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company_a = await _mk_company(db_session, "a")
        company_b = await _mk_company(db_session, "b")
        sa_a = await _mk_user(db_session, company_a, "super_admin")
        owner_b = await _mk_user(db_session, company_b, "super_admin")
        # Team in company B
        team_b = await _mk_team(db_session, company_b, owner_b, "B-Team")
        db_session.add(_mk_creds(company_a.id))
        await db_session.commit()

        resp = await client.patch(
            "/api/integrations/basecamp/settings",
            headers=_bearer(sa_a),
            json={"target_team_id": team_b.id},
        )
        assert resp.status_code == 400
        assert "different company" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_patch_settings_rejects_nonexistent_team(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        sa_user = await _mk_user(db_session, company, "super_admin")
        db_session.add(_mk_creds(company.id))
        await db_session.commit()

        resp = await client.patch(
            "/api/integrations/basecamp/settings",
            headers=_bearer(sa_user),
            json={"target_team_id": 999_999_999},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_settings_requires_connected_credentials(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        sa_user = await _mk_user(db_session, company, "super_admin")
        await db_session.commit()
        # No credentials row.

        resp = await client.patch(
            "/api/integrations/basecamp/settings",
            headers=_bearer(sa_user),
            json={"auto_sync_enabled": True},
        )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_patch_settings_only_super_admin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        admin = await _mk_user(db_session, company, "admin")
        db_session.add(_mk_creds(company.id))
        await db_session.commit()

        resp = await client.patch(
            "/api/integrations/basecamp/settings",
            headers=_bearer(admin),
            json={"auto_sync_enabled": True},
        )
        assert resp.status_code == 403


# ----------------------------------------------------------------------
# GET /status — new fields
# ----------------------------------------------------------------------


class TestStatusNewFields:
    @pytest.mark.asyncio
    async def test_status_includes_new_fields_when_unset(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        sa_user = await _mk_user(db_session, company, "super_admin")
        db_session.add(_mk_creds(company.id))
        await db_session.commit()

        resp = await client.get(
            "/api/integrations/basecamp/status",
            headers=_bearer(sa_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is True
        assert body["target_team_id"] is None
        assert body["target_team_name"] is None
        assert body["auto_sync_enabled"] is False

    @pytest.mark.asyncio
    async def test_status_includes_new_fields_when_set(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        sa_user = await _mk_user(db_session, company, "super_admin")
        team = await _mk_team(db_session, company, sa_user, "Squad-A")
        creds = _mk_creds(
            company.id, target_team_id=team.id, auto_sync_enabled=True
        )
        db_session.add(creds)
        await db_session.commit()

        resp = await client.get(
            "/api/integrations/basecamp/status",
            headers=_bearer(sa_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["target_team_id"] == team.id
        assert body["target_team_name"] == "Squad-A"
        assert body["auto_sync_enabled"] is True


# ----------------------------------------------------------------------
# Sync service uses target_team_id (or falls back)
# ----------------------------------------------------------------------


class TestSyncTargetTeam:
    @pytest.mark.asyncio
    async def test_sync_uses_target_team_when_set(
        self,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        owner = await _mk_user(db_session, company, "super_admin")
        # Two teams; lowest-id is "Default", we want sync to target "Secondary".
        default_team = await _mk_team(db_session, company, owner, "Default")
        secondary = await _mk_team(db_session, company, owner, "Secondary")
        assert default_team.id < secondary.id

        creds = _mk_creds(company.id, target_team_id=secondary.id)
        db_session.add(creds)
        await db_session.flush()

        async def fake_list(_c, _d):
            return [
                {
                    "id": "p1",
                    "name": "Alpha",
                    "description": "d",
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]

        with patch.object(
            BasecampService, "list_projects", side_effect=fake_list
        ):
            await BasecampService.sync_projects_to_company(
                creds, company.id, db_session, dry_run=False
            )
        await db_session.flush()

        rows = await db_session.execute(
            select(Project).where(Project.team_id == secondary.id)
        )
        secondary_projects = rows.scalars().all()
        rows = await db_session.execute(
            select(Project).where(Project.team_id == default_team.id)
        )
        default_projects = rows.scalars().all()
        assert len(secondary_projects) == 1
        assert secondary_projects[0].name == "Alpha"
        assert default_projects == []

    @pytest.mark.asyncio
    async def test_sync_falls_back_to_lowest_id_team_when_null(
        self,
        db_session: AsyncSession,
        configured_basecamp,
    ):
        company = await _mk_company(db_session)
        owner = await _mk_user(db_session, company, "super_admin")
        default_team = await _mk_team(db_session, company, owner, "Default")
        secondary = await _mk_team(db_session, company, owner, "Secondary")
        assert default_team.id < secondary.id

        creds = _mk_creds(company.id, target_team_id=None)
        db_session.add(creds)
        await db_session.flush()

        async def fake_list(_c, _d):
            return [
                {
                    "id": "p1",
                    "name": "Alpha",
                    "description": "d",
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]

        with patch.object(
            BasecampService, "list_projects", side_effect=fake_list
        ):
            await BasecampService.sync_projects_to_company(
                creds, company.id, db_session, dry_run=False
            )
        await db_session.flush()

        rows = await db_session.execute(
            select(Project).where(Project.team_id == default_team.id)
        )
        assert len(rows.scalars().all()) == 1
        # Mapping persisted exactly once
        mrows = await db_session.execute(
            select(BasecampProjectMapping).where(
                BasecampProjectMapping.company_id == company.id
            )
        )
        assert len(mrows.scalars().all()) == 1
