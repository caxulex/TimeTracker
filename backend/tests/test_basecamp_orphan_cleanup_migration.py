from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BasecampProjectMapping,
    Company,
    Project,
    Task,
    Team,
    TimeEntry,
    User,
)
from app.services.auth_service import AuthService


def _load_migration_031_module():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "031_basecamp_orphan_project_cleanup.py"
    )
    spec = importlib.util.spec_from_file_location(
        "migration_031_basecamp_orphan_cleanup",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _mk_company_owner_team(db: AsyncSession) -> tuple[Company, User, Team]:
    unique = uuid.uuid4().hex[:8]
    company = Company(
        name=f"Migration Co {unique}",
        slug=f"migration-co-{unique}",
        email=f"migration-{unique}@example.com",
        status="active",
    )
    db.add(company)
    await db.flush()

    owner = User(
        email=f"owner-{unique}@example.com",
        name="Owner",
        password_hash=AuthService.hash_password("TestPass123!"),
        role="super_admin",
        company_id=company.id,
        is_active=True,
    )
    db.add(owner)
    await db.flush()

    team = Team(name="Default", owner_id=owner.id, company_id=company.id)
    db.add(team)
    await db.flush()

    return company, owner, team


class TestBasecampOrphanCleanupMigration:
    @pytest.mark.asyncio
    async def test_migration_deletes_only_target_orphan_projects(
        self, db_session: AsyncSession
    ):
        module = _load_migration_031_module()
        company, owner, team = await _mk_company_owner_team(db_session)

        in_window = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)

        orphan = Project(team_id=team.id, name="orphan", created_at=in_window)
        with_mapping = Project(team_id=team.id, name="with-mapping", created_at=in_window)
        with_task = Project(team_id=team.id, name="with-task", created_at=in_window)
        with_time_entry = Project(
            team_id=team.id,
            name="with-time-entry",
            created_at=in_window,
        )
        db_session.add_all([orphan, with_mapping, with_task, with_time_entry])
        await db_session.flush()

        db_session.add(
            BasecampProjectMapping(
                company_id=company.id,
                basecamp_account_id="acct-1",
                basecamp_project_id="mapped",
                internal_project_id=with_mapping.id,
                last_synced_at=in_window,
            )
        )
        db_session.add(
            Task(
                project_id=with_task.id,
                name="Task exists",
                status="TODO",
            )
        )
        db_session.add(
            TimeEntry(
                user_id=owner.id,
                project_id=with_time_entry.id,
                task_id=None,
                start_time=in_window,
                end_time=in_window,
                duration_seconds=0,
                description="seed",
                is_running=False,
            )
        )
        await db_session.commit()

        async with db_session.bind.begin() as conn:
            await conn.run_sync(module.run_orphan_project_cleanup)

        rows = await db_session.execute(
            select(Project.id, Project.name).where(Project.team_id == team.id)
        )
        remaining = sorted(rows.all(), key=lambda row: row[1])
        remaining_names = [row[1] for row in remaining]

        assert remaining_names == ["with-mapping", "with-task", "with-time-entry"]
