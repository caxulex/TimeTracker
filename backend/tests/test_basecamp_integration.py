"""Tests for the Basecamp integration (v1).

Covers:
* Schema / model column presence + migration round-trip
* ``BasecampService`` unit tests (OAuth URL, exchange, refresh, sync)
* Router endpoint auth + happy-path behavior

All Basecamp API calls are mocked via ``unittest.mock``; no real
network traffic. The OAuth state CSRF token is stored in the same
Redis instance the token blacklist uses, so these tests require Redis
to be reachable on the configured ``REDIS_URL``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import inspect, select
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
from app.services.basecamp_service import (
    BasecampAuthError,
    BasecampService,
    _parse_next_link,
)
from app.services.encryption_service import EncryptionService


# ----------------------------------------------------------------------
# Helpers / fixtures
# ----------------------------------------------------------------------


@pytest_asyncio.fixture
async def _bypass_blacklist(monkeypatch):
    """Bypass the Redis-backed JWT blacklist so router tests can run when
    Redis is not reachable in the local environment.

    Returns ``False`` (== not blacklisted) for every JTI. Other tests in
    the suite expect Redis to be available; this fixture only applies to
    Basecamp router tests.
    """
    async def _ok(_jti):
        return False

    monkeypatch.setattr(
        "app.dependencies._check_blacklist_or_fail_closed", _ok
    )
    yield


@pytest_asyncio.fixture
async def _fake_state_store(monkeypatch):
    """In-memory replacement for the Redis-backed OAuth state store."""
    store: dict[str, dict] = {}

    async def _store(state: str, payload: dict) -> None:
        store[state] = payload

    async def _consume(state: str):
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
    """Set BASECAMP env vars + an encryption key for the duration of the test."""
    monkeypatch.setattr(settings, "BASECAMP_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "BASECAMP_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(
        settings,
        "BASECAMP_REDIRECT_URI",
        "https://timetracker.shaemarcus.com/api/integrations/basecamp/callback",
    )
    if not settings.API_KEY_ENCRYPTION_KEY:
        monkeypatch.setattr(
            settings, "API_KEY_ENCRYPTION_KEY", "test-encryption-key-for-basecamp-suite"
        )
    yield


@pytest_asyncio.fixture
async def company(db_session: AsyncSession) -> Company:
    unique = uuid.uuid4().hex[:8]
    c = Company(
        name=f"BC Co {unique}",
        slug=f"bc-co-{unique}",
        email=f"bc-{unique}@example.com",
        status="active",
    )
    db_session.add(c)
    await db_session.flush()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def super_admin(db_session: AsyncSession, company: Company) -> User:
    u = User(
        email=f"sa-{uuid.uuid4().hex[:8]}@example.com",
        name="Super Admin",
        password_hash=AuthService.hash_password("TestPass123!"),
        role="super_admin",
        company_id=company.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def regular(db_session: AsyncSession, company: Company) -> User:
    u = User(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        name="Regular",
        password_hash=AuthService.hash_password("TestPass123!"),
        role="regular_user",
        company_id=company.id,
        is_active=True,
    )
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest_asyncio.fixture
async def team(db_session: AsyncSession, company: Company, super_admin: User) -> Team:
    t = Team(name="Default Team", owner_id=super_admin.id, company_id=company.id)
    db_session.add(t)
    await db_session.flush()
    await db_session.refresh(t)
    return t


def _bearer(user: User) -> dict:
    token = AuthService.create_access_token(
        {"sub": str(user.id), "email": user.email}
    )
    return {"Authorization": f"Bearer {token}"}


def _make_creds(
    company_id: int,
    *,
    expires_in: int = 3600,
    account_id: str = "999999999",
) -> BasecampCredentials:
    enc = EncryptionService()
    return BasecampCredentials(
        company_id=company_id,
        account_id=account_id,
        account_name="Shae Marcus Consulting",
        access_token_encrypted=enc.encrypt("access-tok-1"),
        refresh_token_encrypted=enc.encrypt("refresh-tok-1"),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    )


# ----------------------------------------------------------------------
# Schema / migration tests
# ----------------------------------------------------------------------


class TestSchema:
    def test_basecamp_credentials_columns(self):
        cols = {c.name for c in BasecampCredentials.__table__.columns}
        assert cols == {
            "id",
            "company_id",
            "account_id",
            "account_name",
            "access_token_encrypted",
            "refresh_token_encrypted",
            "expires_at",
            "connected_by_user_id",
            "last_sync_at",
            "target_team_id",
            "auto_sync_enabled",
            "created_at",
            "updated_at",
        }

    def test_basecamp_project_mapping_columns(self):
        cols = {c.name for c in BasecampProjectMapping.__table__.columns}
        assert cols == {
            "id",
            "company_id",
            "basecamp_account_id",
            "basecamp_project_id",
            "internal_project_id",
            "last_synced_at",
        }

    def test_unique_constraints_present(self):
        # Company UNIQUE on credentials
        cred_cols = BasecampCredentials.__table__.columns["company_id"]
        assert cred_cols.unique is True

        # Composite UNIQUE on mappings
        names = {
            uc.name for uc in BasecampProjectMapping.__table__.constraints
            if uc.__class__.__name__ == "UniqueConstraint"
        }
        assert "uq_basecamp_project_mapping_external" in names

    @pytest.mark.asyncio
    async def test_migration_tables_exist(self, async_engine):
        async with async_engine.connect() as conn:
            def _inspect(sync_conn):
                return inspect(sync_conn).get_table_names()
            tables = await conn.run_sync(_inspect)
        assert "basecamp_credentials" in tables
        assert "basecamp_project_mappings" in tables


# ----------------------------------------------------------------------
# Service unit tests
# ----------------------------------------------------------------------


class TestService:
    def test_authorization_url(self, configured_basecamp):
        url = BasecampService.get_authorization_url("abc123")
        assert url.startswith(
            "https://launchpad.37signals.com/authorization/new?"
        )
        assert "client_id=test-client-id" in url
        assert "state=abc123" in url
        assert "type=web_server" in url
        assert "redirect_uri=" in url

    def test_authorization_url_unconfigured(self, monkeypatch):
        monkeypatch.setattr(settings, "BASECAMP_CLIENT_ID", "")
        monkeypatch.setattr(settings, "BASECAMP_CLIENT_SECRET", "")
        with pytest.raises(Exception):
            BasecampService.get_authorization_url("x")

    def test_exchange_code_success(self, configured_basecamp):
        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {
            "access_token": "AT-1",
            "refresh_token": "RT-1",
            "expires_in": 1209600,
        }
        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {
            "accounts": [
                {"id": 999999999, "name": "Shae Marcus", "product": "bc3"}
            ],
        }

        client_ctx = MagicMock()
        client_ctx.post.return_value = token_resp
        client_ctx.get.return_value = auth_resp

        with patch(
            "app.services.basecamp_service.httpx.Client"
        ) as ClientMock:
            ClientMock.return_value.__enter__.return_value = client_ctx
            result = BasecampService.exchange_code_for_tokens("the-code")

        assert result["access_token"] == "AT-1"
        assert result["refresh_token"] == "RT-1"
        assert result["account_id"] == "999999999"
        assert result["account_name"] == "Shae Marcus"
        assert result["expires_at"] > datetime.now(timezone.utc)

    def test_exchange_code_401(self, configured_basecamp):
        token_resp = MagicMock()
        token_resp.status_code = 401

        client_ctx = MagicMock()
        client_ctx.post.return_value = token_resp

        with patch("app.services.basecamp_service.httpx.Client") as ClientMock:
            ClientMock.return_value.__enter__.return_value = client_ctx
            with pytest.raises(BasecampAuthError):
                BasecampService.exchange_code_for_tokens("bad-code")

    @pytest.mark.asyncio
    async def test_refresh_access_token(
        self, configured_basecamp, db_session, company
    ):
        creds = _make_creds(company.id, expires_in=10)
        db_session.add(creds)
        await db_session.flush()

        refresh_resp = MagicMock()
        refresh_resp.status_code = 200
        refresh_resp.json.return_value = {
            "access_token": "AT-2",
            "expires_in": 1209600,
        }

        async_client = MagicMock()
        async_client.post = AsyncMock(return_value=refresh_resp)

        with patch(
            "app.services.basecamp_service.httpx.AsyncClient"
        ) as AC:
            AC.return_value.__aenter__.return_value = async_client
            new_token = await BasecampService.refresh_access_token(
                creds, db_session
            )

        assert new_token == "AT-2"
        # DB row was updated with new ciphertext + future expiry
        decrypted = EncryptionService().decrypt(creds.access_token_encrypted)
        assert decrypted == "AT-2"
        assert creds.expires_at > datetime.now(timezone.utc) + timedelta(
            days=10
        )

    @pytest.mark.asyncio
    async def test_sync_dry_run_does_not_write(
        self, configured_basecamp, db_session, company, team
    ):
        creds = _make_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        async def fake_list(_creds, _db):
            return [
                {
                    "id": "p1",
                    "name": "Project Alpha",
                    "description": "Desc A",
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00Z",
                },
                {
                    "id": "p2",
                    "name": "Project Beta",
                    "description": None,
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00Z",
                },
            ]

        with patch.object(
            BasecampService, "list_projects", side_effect=fake_list
        ):
            report = await BasecampService.sync_projects_to_company(
                creds, company.id, db_session, dry_run=True
            )

        assert report == {
            "created": 2,
            "updated": 0,
            "unchanged": 0,
            "errors": [],
            "dry_run": True,
        }
        # Nothing persisted
        rows = await db_session.execute(
            select(Project).where(Project.team_id == team.id)
        )
        assert rows.scalars().all() == []
        rows = await db_session.execute(select(BasecampProjectMapping))
        assert rows.scalars().all() == []

    @pytest.mark.asyncio
    async def test_sync_creates_then_idempotent(
        self, configured_basecamp, db_session, company, team
    ):
        creds = _make_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        bc_payload = [
            {
                "id": "p1",
                "name": "Project Alpha",
                "description": "Desc A",
                "status": "active",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "id": "p2",
                "name": "Project Beta",
                "description": "",
                "status": "active",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]

        async def fake_list(_creds, _db):
            return bc_payload

        with patch.object(
            BasecampService, "list_projects", side_effect=fake_list
        ):
            r1 = await BasecampService.sync_projects_to_company(
                creds, company.id, db_session, dry_run=False
            )
            await db_session.flush()
            r2 = await BasecampService.sync_projects_to_company(
                creds, company.id, db_session, dry_run=False
            )

        assert r1["created"] == 2
        assert r1["updated"] == 0
        assert r1["unchanged"] == 0
        assert r1["errors"] == []

        # Second run: nothing changed in payload, so updates == 0,
        # unchanged == 2
        assert r2["created"] == 0
        assert r2["updated"] == 0
        assert r2["unchanged"] == 2

        # Now mutate one project's name and re-sync; should record updated=1.
        bc_payload[0]["name"] = "Project Alpha v2"
        with patch.object(
            BasecampService, "list_projects", side_effect=fake_list
        ):
            r3 = await BasecampService.sync_projects_to_company(
                creds, company.id, db_session, dry_run=False
            )
        assert r3["created"] == 0
        assert r3["updated"] == 1
        assert r3["unchanged"] == 1

        # Persisted exactly 2 mappings + 2 projects (no duplicates)
        proj_rows = await db_session.execute(
            select(Project).where(Project.team_id == team.id)
        )
        projects = proj_rows.scalars().all()
        assert len(projects) == 2
        names = sorted(p.name for p in projects)
        assert names == ["Project Alpha v2", "Project Beta"]

        map_rows = await db_session.execute(
            select(BasecampProjectMapping).where(
                BasecampProjectMapping.company_id == company.id
            )
        )
        assert len(map_rows.scalars().all()) == 2

    def test_parse_next_link(self):
        h = '<https://3.basecampapi.com/1/projects.json?page=2>; rel="next"'
        assert (
            _parse_next_link(h)
            == "https://3.basecampapi.com/1/projects.json?page=2"
        )
        assert _parse_next_link(None) is None
        assert _parse_next_link('<x>; rel="prev"') is None


# ----------------------------------------------------------------------
# Router endpoint tests
# ----------------------------------------------------------------------


class TestRouter:
    @pytest.mark.asyncio
    async def test_connect_requires_super_admin(
        self, client: AsyncClient, regular: User, configured_basecamp
    ):
        resp = await client.get(
            "/api/integrations/basecamp/connect",
            headers=_bearer(regular),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_connect_returns_url(
        self, client: AsyncClient, super_admin: User, configured_basecamp
    ):
        resp = await client.get(
            "/api/integrations/basecamp/connect",
            headers=_bearer(super_admin),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorization_url"].startswith(
            "https://launchpad.37signals.com/authorization/new?"
        )
        assert "state=" in data["authorization_url"]

    @pytest.mark.asyncio
    async def test_connect_503_when_not_configured(
        self, client: AsyncClient, super_admin: User, monkeypatch, _bypass_blacklist
    ):
        monkeypatch.setattr(settings, "BASECAMP_CLIENT_ID", "")
        monkeypatch.setattr(settings, "BASECAMP_CLIENT_SECRET", "")
        resp = await client.get(
            "/api/integrations/basecamp/connect",
            headers=_bearer(super_admin),
        )
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_callback_rejects_invalid_state(
        self, client: AsyncClient, configured_basecamp
    ):
        resp = await client.get(
            "/api/integrations/basecamp/callback",
            params={"code": "x", "state": "definitely-not-a-real-state"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_happy_path(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        super_admin: User,
        company: Company,
        configured_basecamp,
        _fake_state_store,
    ):
        # Pre-populate the fake state store so the callback recognises it.
        _fake_state_store["valid-state-1"] = {
            "company_id": company.id,
            "user_id": super_admin.id,
        }

        def fake_exchange(code):
            return {
                "access_token": "AT-callback",
                "refresh_token": "RT-callback",
                "expires_at": datetime.now(timezone.utc)
                + timedelta(seconds=1209600),
                "account_id": "777",
                "account_name": "BC Account",
            }

        with patch.object(
            BasecampService,
            "exchange_code_for_tokens",
            side_effect=fake_exchange,
        ):
            resp = await client.get(
                "/api/integrations/basecamp/callback",
                params={"code": "the-code", "state": "valid-state-1"},
                follow_redirects=False,
            )

        assert resp.status_code == 302
        assert "settings/integrations" in resp.headers["location"]

        row = await db_session.execute(
            select(BasecampCredentials).where(
                BasecampCredentials.company_id == company.id
            )
        )
        creds = row.scalar_one()
        assert creds.account_id == "777"
        assert creds.account_name == "BC Account"
        # Token is encrypted, not stored in plaintext
        assert creds.access_token_encrypted != "AT-callback"
        assert (
            EncryptionService().decrypt(creds.access_token_encrypted)
            == "AT-callback"
        )

    @pytest.mark.asyncio
    async def test_status_disconnected(
        self, client: AsyncClient, super_admin: User, configured_basecamp
    ):
        resp = await client.get(
            "/api/integrations/basecamp/status",
            headers=_bearer(super_admin),
        )
        assert resp.status_code == 200
        assert resp.json()["connected"] is False

    @pytest.mark.asyncio
    async def test_status_connected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        super_admin: User,
        company: Company,
        configured_basecamp,
    ):
        creds = _make_creds(company.id)
        db_session.add(creds)
        await db_session.commit()

        resp = await client.get(
            "/api/integrations/basecamp/status",
            headers=_bearer(super_admin),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is True
        assert body["account_name"] == "Shae Marcus Consulting"
        # Tokens are NOT in the response
        assert "access_token" not in body
        assert "refresh_token" not in body

    @pytest.mark.asyncio
    async def test_sync_dry_run(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        super_admin: User,
        company: Company,
        team: Team,
        configured_basecamp,
    ):
        creds = _make_creds(company.id)
        db_session.add(creds)
        await db_session.commit()

        async def fake_list(_creds, _db):
            return [
                {
                    "id": "p1",
                    "name": "P1",
                    "description": "",
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]

        with patch.object(BasecampService, "list_projects", side_effect=fake_list), \
             patch.object(BasecampService, "_list_todolists", new=AsyncMock(return_value=[])), \
             patch.object(BasecampService, "_get_valid_access_token", new=AsyncMock(return_value="tok")):
            resp = await client.post(
                "/api/integrations/basecamp/sync",
                headers=_bearer(super_admin),
                json={"dry_run": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["dry_run"] is True
        assert body["created"] == 1
        # New v3.0 to-do fields are present (zero, since no mappings exist yet)
        assert body["todos_created"] == 0
        assert body["todos_updated"] == 0
        assert body["todos_unchanged"] == 0
        assert body["todo_errors"] == []
        # No persisted rows
        rows = await db_session.execute(select(BasecampProjectMapping))
        assert rows.scalars().all() == []

    @pytest.mark.asyncio
    async def test_sync_writes_projects(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        super_admin: User,
        company: Company,
        team: Team,
        configured_basecamp,
    ):
        creds = _make_creds(company.id)
        db_session.add(creds)
        await db_session.commit()

        async def fake_list(_creds, _db):
            return [
                {
                    "id": "p1",
                    "name": "P1",
                    "description": "d",
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]

        with patch.object(BasecampService, "list_projects", side_effect=fake_list), \
             patch.object(BasecampService, "_list_todolists", new=AsyncMock(return_value=[])), \
             patch.object(BasecampService, "_get_valid_access_token", new=AsyncMock(return_value="tok")):
            resp = await client.post(
                "/api/integrations/basecamp/sync",
                headers=_bearer(super_admin),
                json={"dry_run": False},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] == 1
        # New v3.0 to-do response fields are present (zero, no to-dos returned)
        assert body["todos_created"] == 0
        assert body["todos_updated"] == 0
        assert body["todos_unchanged"] == 0
        assert body["todo_errors"] == []

        rows = await db_session.execute(select(BasecampProjectMapping))
        assert len(rows.scalars().all()) == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_credentials(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        super_admin: User,
        company: Company,
        configured_basecamp,
    ):
        creds = _make_creds(company.id)
        db_session.add(creds)
        await db_session.commit()

        with patch.object(
            BasecampService, "revoke_token", AsyncMock(return_value=True)
        ):
            resp = await client.delete(
                "/api/integrations/basecamp/disconnect",
                headers=_bearer(super_admin),
            )

        assert resp.status_code == 200
        rows = await db_session.execute(
            select(BasecampCredentials).where(
                BasecampCredentials.company_id == company.id
            )
        )
        assert rows.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_disconnect_404_when_not_connected(
        self, client: AsyncClient, super_admin: User, configured_basecamp
    ):
        resp = await client.delete(
            "/api/integrations/basecamp/disconnect",
            headers=_bearer(super_admin),
        )
        assert resp.status_code == 404
