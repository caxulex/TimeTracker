"""Tests for the 4-hourly Basecamp auto-sync scheduler job.

Verifies ``sync_all_enabled_companies`` in ``scripts/sync_basecamp_projects``:
* Only processes ``auto_sync_enabled=True`` credentials
* Skips disabled credentials
* Per-company errors do not abort the loop
* Summary dict shape is correct
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Make ``scripts/`` importable.
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.config import settings  # noqa: E402
from app.models import (  # noqa: E402
    BasecampCredentials,
    Company,
    Project,
    Team,
    User,
)
from app.services.auth_service import AuthService  # noqa: E402
from app.services.basecamp_service import BasecampError, BasecampService  # noqa: E402
from app.services.encryption_service import EncryptionService  # noqa: E402
from scripts.sync_basecamp_projects import sync_all_enabled_companies  # noqa: E402


@pytest_asyncio.fixture
async def _enc_key(monkeypatch):
    if not settings.API_KEY_ENCRYPTION_KEY:
        monkeypatch.setattr(
            settings, "API_KEY_ENCRYPTION_KEY", "test-enc-key-autosync"
        )
    yield


async def _mk_company(db: AsyncSession) -> Company:
    unique = uuid.uuid4().hex[:8]
    c = Company(
        name=f"AS Co {unique}",
        slug=f"as-{unique}",
        email=f"as-{unique}@example.com",
        status="active",
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


async def _mk_owner_and_team(
    db: AsyncSession, company: Company
) -> tuple[User, Team]:
    u = User(
        email=f"o-{uuid.uuid4().hex[:8]}@example.com",
        name="Owner",
        password_hash=AuthService.hash_password("TestPass123!"),
        role="super_admin",
        company_id=company.id,
        is_active=True,
    )
    db.add(u)
    await db.flush()
    await db.refresh(u)

    t = Team(name="Default", owner_id=u.id, company_id=company.id)
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return u, t


def _mk_creds(company_id: int, *, auto: bool) -> BasecampCredentials:
    enc = EncryptionService()
    return BasecampCredentials(
        company_id=company_id,
        account_id=f"acct-{company_id}",
        account_name="Auto Co",
        access_token_encrypted=enc.encrypt("at"),
        refresh_token_encrypted=enc.encrypt("rt"),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=3600),
        auto_sync_enabled=auto,
    )


class TestAutoSyncJob:
    @pytest.mark.asyncio
    async def test_autosync_processes_enabled_credentials(
        self, db_session: AsyncSession, _enc_key
    ):
        co = await _mk_company(db_session)
        await _mk_owner_and_team(db_session, co)
        db_session.add(_mk_creds(co.id, auto=True))
        await db_session.commit()

        async def fake_list(_c, _d):
            return [
                {
                    "id": "p1",
                    "name": "Alpha",
                    "description": None,
                    "status": "active",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]

        with patch.object(
            BasecampService, "list_projects", side_effect=fake_list
        ):
            summary = await sync_all_enabled_companies(db_session)

        assert summary["companies_processed"] == 1
        assert summary["companies_succeeded"] == 1
        assert summary["companies_failed"] == 0
        assert summary["results"][0]["company_id"] == co.id
        assert summary["results"][0]["created"] == 1

        # Project was actually created (commit happened).
        from sqlalchemy import select

        rows = await db_session.execute(
            select(Project).where(Project.name == "Alpha")
        )
        assert rows.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_autosync_skips_disabled_credentials(
        self, db_session: AsyncSession, _enc_key
    ):
        co_enabled = await _mk_company(db_session)
        co_disabled = await _mk_company(db_session)
        await _mk_owner_and_team(db_session, co_enabled)
        await _mk_owner_and_team(db_session, co_disabled)
        db_session.add(_mk_creds(co_enabled.id, auto=True))
        db_session.add(_mk_creds(co_disabled.id, auto=False))
        await db_session.commit()

        seen_company_ids: list[int] = []

        async def fake_sync(creds, company_id, db, dry_run=False):
            seen_company_ids.append(company_id)
            return {"created": 0, "updated": 0, "unchanged": 0, "errors": []}

        with patch.object(
            BasecampService, "sync_projects_to_company", side_effect=fake_sync
        ):
            summary = await sync_all_enabled_companies(db_session)

        assert summary["companies_processed"] == 1
        assert seen_company_ids == [co_enabled.id]
        assert co_disabled.id not in seen_company_ids

    @pytest.mark.asyncio
    async def test_autosync_handles_per_company_errors(
        self, db_session: AsyncSession, _enc_key
    ):
        co_a = await _mk_company(db_session)
        co_b = await _mk_company(db_session)
        await _mk_owner_and_team(db_session, co_a)
        await _mk_owner_and_team(db_session, co_b)
        db_session.add(_mk_creds(co_a.id, auto=True))
        db_session.add(_mk_creds(co_b.id, auto=True))
        await db_session.commit()

        async def fake_sync(creds, company_id, db, dry_run=False):
            if company_id == co_a.id:
                raise BasecampError("simulated A failure")
            return {"created": 0, "updated": 0, "unchanged": 1, "errors": []}

        with patch.object(
            BasecampService, "sync_projects_to_company", side_effect=fake_sync
        ):
            summary = await sync_all_enabled_companies(db_session)

        assert summary["companies_processed"] == 2
        assert summary["companies_succeeded"] == 1
        assert summary["companies_failed"] == 1
        assert len(summary["errors"]) == 1
        assert summary["errors"][0]["company_id"] == co_a.id
        assert "simulated A failure" in summary["errors"][0]["error"]
        # B's result still recorded
        assert any(r["company_id"] == co_b.id for r in summary["results"])

    @pytest.mark.asyncio
    async def test_autosync_returns_summary(
        self, db_session: AsyncSession, _enc_key
    ):
        # No enabled creds → empty summary.
        summary = await sync_all_enabled_companies(db_session)
        assert summary == {
            "companies_processed": 0,
            "companies_succeeded": 0,
            "companies_failed": 0,
            "errors": [],
            "results": [],
        }
