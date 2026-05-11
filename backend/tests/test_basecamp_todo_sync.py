"""Tests for the Basecamp -> TimeTracker one-way to-do mirror (v3.0).

Covers:
* Happy path: to-dos are created as Tasks in the linked Project
* Idempotency: re-syncing updates only changed to-dos
* Status mapping: completed Basecamp to-dos -> Task.status="DONE",
  active -> "TODO"
* Mapped-projects-only: projects without a basecamp_project_mappings
  row are ignored
* Cross-tenant isolation: company A cannot see company B's to-dos
* Pagination via Link header
* Per-item error isolation
* Dry-run safety
* BasecampTaskMapping unique constraint

All Basecamp API calls are mocked at the ``_list_todolists`` /
``_list_todos_in_list`` boundary or via direct ``httpx.AsyncClient``
patches; no real network traffic.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    BasecampCredentials,
    BasecampProjectMapping,
    BasecampTaskMapping,
    Company,
    Project,
    Task,
    Team,
    User,
)
from app.services.auth_service import AuthService
from app.services.basecamp_service import BasecampService
from app.services.encryption_service import EncryptionService


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest_asyncio.fixture
async def _enc_key(monkeypatch):
    if not settings.API_KEY_ENCRYPTION_KEY:
        monkeypatch.setattr(
            settings, "API_KEY_ENCRYPTION_KEY", "test-enc-key-todo-sync"
        )
    yield


async def _mk_company(db: AsyncSession, label: str = "TodoCo") -> Company:
    unique = uuid.uuid4().hex[:8]
    c = Company(
        name=f"{label} {unique}",
        slug=f"todo-{unique}",
        email=f"td-{unique}@example.com",
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


def _mk_creds(company_id: int, *, account_id: str = "acct-1") -> BasecampCredentials:
    enc = EncryptionService()
    return BasecampCredentials(
        company_id=company_id,
        account_id=account_id,
        account_name="Co",
        access_token_encrypted=enc.encrypt("at-todo"),
        refresh_token_encrypted=enc.encrypt("rt-todo"),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=3600),
    )


async def _mk_project_and_mapping(
    db: AsyncSession,
    company: Company,
    team: Team,
    *,
    basecamp_project_id: str,
    account_id: str = "acct-1",
    project_name: str = "Mapped Project",
) -> tuple[Project, BasecampProjectMapping]:
    project = Project(team_id=team.id, name=project_name, description=None)
    db.add(project)
    await db.flush()
    await db.refresh(project)

    mapping = BasecampProjectMapping(
        company_id=company.id,
        basecamp_account_id=account_id,
        basecamp_project_id=basecamp_project_id,
        internal_project_id=project.id,
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(mapping)
    await db.flush()
    return project, mapping


# ----------------------------------------------------------------------
# Common patch helpers
# ----------------------------------------------------------------------


def _patch_basecamp_api(todolists_by_project: dict, todos_by_list: dict):
    """Build patches for the two Basecamp HTTP helpers + token getter.

    ``todolists_by_project`` maps basecamp_project_id -> list of
    ``{"id": str, "title": str}`` dicts.
    ``todos_by_list`` maps todolist_id -> list of
    ``{"id": str, "content": str, "completed": bool, ...}`` dicts.
    """
    async def fake_token(_creds, _db):
        return "fake-access-token"

    async def fake_lists(_token, _account_id, basecamp_project_id):
        return list(todolists_by_project.get(basecamp_project_id, []))

    async def fake_todos(_token, _account_id, _project_id, todolist_id):
        return list(todos_by_list.get(todolist_id, []))

    return (
        patch.object(
            BasecampService, "_get_valid_access_token", side_effect=fake_token
        ),
        patch.object(
            BasecampService, "_list_todolists", side_effect=fake_lists
        ),
        patch.object(
            BasecampService, "_list_todos_in_list", side_effect=fake_todos
        ),
    )


class TestTodoSyncSchema:
    def test_basecamp_task_mapping_columns(self):
        cols = {c.name for c in BasecampTaskMapping.__table__.columns}
        assert cols == {
            "id",
            "company_id",
            "basecamp_account_id",
            "basecamp_project_id",
            "basecamp_todolist_id",
            "basecamp_todo_id",
            "task_id",
            "last_synced_at",
        }

    def test_basecamp_task_mapping_unique_constraint(self):
        names = {
            uc.name
            for uc in BasecampTaskMapping.__table__.constraints
            if uc.__class__.__name__ == "UniqueConstraint"
        }
        assert "uq_basecamp_task_mapping_external" in names


# ----------------------------------------------------------------------
# Service tests
# ----------------------------------------------------------------------


class TestTodoSync:
    @pytest.mark.asyncio
    async def test_sync_creates_new_todos_in_correct_project(
        self, db_session: AsyncSession, _enc_key
    ):
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        project, _ = await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        todolists = {"bcp-1": [{"id": "list-1", "title": "Sprint A"}]}
        todos = {
            "list-1": [
                {"id": "td-1", "content": "Write docs", "completed": False},
                {"id": "td-2", "content": "Ship it", "completed": False},
            ]
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            report = await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )

        assert report["todos_created"] == 2
        assert report["todos_updated"] == 0
        assert report["todos_unchanged"] == 0
        assert report["todo_errors"] == []

        # Tasks live in the right project, and names include the list title
        rows = await db_session.execute(
            select(Task).where(Task.project_id == project.id)
        )
        tasks = rows.scalars().all()
        assert len(tasks) == 2
        names = sorted(t.name for t in tasks)
        assert names == ["[Sprint A] Ship it", "[Sprint A] Write docs"]

    @pytest.mark.asyncio
    async def test_sync_updates_existing_todos_when_changed(
        self, db_session: AsyncSession, _enc_key
    ):
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        todolists = {"bcp-1": [{"id": "list-1", "title": "Sprint A"}]}
        todos = {
            "list-1": [
                {"id": "td-1", "content": "Original", "completed": False},
            ]
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            r1 = await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )
        assert r1["todos_created"] == 1

        # Mutate the to-do content and re-sync
        todos["list-1"][0]["content"] = "Renamed"
        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            r2 = await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )
        assert r2["todos_created"] == 0
        assert r2["todos_updated"] == 1
        assert r2["todos_unchanged"] == 0

        rows = await db_session.execute(select(Task))
        tasks = rows.scalars().all()
        assert len(tasks) == 1
        assert tasks[0].name == "[Sprint A] Renamed"

    @pytest.mark.asyncio
    async def test_sync_marks_unchanged_when_no_diff(
        self, db_session: AsyncSession, _enc_key
    ):
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        todolists = {"bcp-1": [{"id": "list-1", "title": "L"}]}
        todos = {"list-1": [{"id": "td-1", "content": "X", "completed": False}]}

        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )

        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            r2 = await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )
        assert r2["todos_created"] == 0
        assert r2["todos_updated"] == 0
        assert r2["todos_unchanged"] == 1

    @pytest.mark.asyncio
    async def test_sync_handles_completed_todos(
        self, db_session: AsyncSession, _enc_key
    ):
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        todolists = {"bcp-1": [{"id": "list-1", "title": "L"}]}
        todos = {
            "list-1": [
                {"id": "td-1", "content": "Done item", "completed": True},
            ]
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )

        rows = await db_session.execute(select(Task))
        tasks = rows.scalars().all()
        assert len(tasks) == 1
        assert tasks[0].status == "DONE"

    @pytest.mark.asyncio
    async def test_sync_handles_active_todos(
        self, db_session: AsyncSession, _enc_key
    ):
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        todolists = {"bcp-1": [{"id": "list-1", "title": "L"}]}
        todos = {
            "list-1": [
                {"id": "td-1", "content": "Pending item", "completed": False},
            ]
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )

        rows = await db_session.execute(select(Task))
        tasks = rows.scalars().all()
        assert len(tasks) == 1
        assert tasks[0].status == "TODO"

    @pytest.mark.asyncio
    async def test_sync_scopes_to_mapped_projects_only(
        self, db_session: AsyncSession, _enc_key
    ):
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        # Project WITHOUT a mapping - should be ignored
        unmapped = Project(team_id=team.id, name="Unmapped", description=None)
        db_session.add(unmapped)
        await db_session.flush()
        # Project WITH a mapping
        await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        # Even if Basecamp returned to-dos for an unmapped project id,
        # those should not be touched because the sync iterates the
        # mappings table.
        todolists = {
            "bcp-1": [{"id": "list-1", "title": "L"}],
            "bcp-unmapped": [{"id": "list-99", "title": "Ghost"}],
        }
        todos = {
            "list-1": [{"id": "td-1", "content": "Real", "completed": False}],
            "list-99": [{"id": "td-99", "content": "Ghost", "completed": False}],
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            report = await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )
        assert report["todos_created"] == 1

        # The unmapped project has zero tasks
        rows = await db_session.execute(
            select(Task).where(Task.project_id == unmapped.id)
        )
        assert rows.scalars().all() == []

    @pytest.mark.asyncio
    async def test_sync_respects_company_isolation(
        self, db_session: AsyncSession, _enc_key
    ):
        # Two companies each with their own creds + a mapping with the
        # SAME basecamp_project_id and SAME basecamp_todo_id (different
        # Basecamp accounts).
        co_a = await _mk_company(db_session, "A")
        co_b = await _mk_company(db_session, "B")
        _, team_a = await _mk_owner_and_team(db_session, co_a)
        _, team_b = await _mk_owner_and_team(db_session, co_b)
        proj_a, _ = await _mk_project_and_mapping(
            db_session, co_a, team_a,
            basecamp_project_id="bcp-shared",
            account_id="acct-A",
            project_name="A Project",
        )
        proj_b, _ = await _mk_project_and_mapping(
            db_session, co_b, team_b,
            basecamp_project_id="bcp-shared",
            account_id="acct-B",
            project_name="B Project",
        )
        creds_a = _mk_creds(co_a.id, account_id="acct-A")
        creds_b = _mk_creds(co_b.id, account_id="acct-B")
        db_session.add_all([creds_a, creds_b])
        await db_session.flush()

        # Sync A
        todolists = {"bcp-shared": [{"id": "list-1", "title": "L"}]}
        todos_a = {
            "list-1": [{"id": "td-1", "content": "A only", "completed": False}]
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos_a)
        with p1, p2, p3:
            await BasecampService.sync_todos_for_company(
                creds_a, co_a.id, db_session, dry_run=False
            )

        # Sync B (same basecamp_todo_id - must not collide because the
        # unique constraint is per-company).
        todos_b = {
            "list-1": [{"id": "td-1", "content": "B only", "completed": True}]
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos_b)
        with p1, p2, p3:
            await BasecampService.sync_todos_for_company(
                creds_b, co_b.id, db_session, dry_run=False
            )

        # A's task lives only in A's project; B's only in B's
        rows_a = await db_session.execute(
            select(Task).where(Task.project_id == proj_a.id)
        )
        a_tasks = rows_a.scalars().all()
        assert [t.name for t in a_tasks] == ["[L] A only"]
        assert a_tasks[0].status == "TODO"

        rows_b = await db_session.execute(
            select(Task).where(Task.project_id == proj_b.id)
        )
        b_tasks = rows_b.scalars().all()
        assert [t.name for t in b_tasks] == ["[L] B only"]
        assert b_tasks[0].status == "DONE"

        # Two distinct mapping rows persisted
        all_maps = await db_session.execute(select(BasecampTaskMapping))
        assert len(all_maps.scalars().all()) == 2

    @pytest.mark.asyncio
    async def test_sync_handles_paginated_todo_lists(
        self, db_session: AsyncSession, _enc_key
    ):
        # Drive the real _list_todolists + _list_todos_in_list code paths
        # through a paginated mock httpx client.
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        project, _ = await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        # Page 1 of todolists -> Link: rel=next ; Page 2 -> last.
        page1 = MagicMock()
        page1.status_code = 200
        page1.json.return_value = [{"id": 10, "title": "List 1"}]
        page1.headers = {
            "Link": (
                '<https://3.basecampapi.com/acct-1/buckets/bcp-1/'
                'todolists.json?page=2>; rel="next"'
            )
        }
        page2 = MagicMock()
        page2.status_code = 200
        page2.json.return_value = [{"id": 20, "title": "List 2"}]
        page2.headers = {}

        # Todos for list 10 + 20, no pagination for to-dos.
        todos_10 = MagicMock()
        todos_10.status_code = 200
        todos_10.json.return_value = [
            {"id": 100, "content": "T100", "completed": False}
        ]
        todos_10.headers = {}
        empty_completed = MagicMock()
        empty_completed.status_code = 200
        empty_completed.json.return_value = []
        empty_completed.headers = {}
        todos_20 = MagicMock()
        todos_20.status_code = 200
        todos_20.json.return_value = [
            {"id": 200, "content": "T200", "completed": True}
        ]
        todos_20.headers = {}

        # The mocked AsyncClient is entered twice (once for todolists,
        # once for each list's todos). Build a side_effect that returns
        # the right response based on URL.
        def make_response(url: str):
            if "todolists.json?page=2" in url:
                return page2
            if "todolists.json" in url and "page=" not in url:
                return page1
            if "todolists/10/todos.json" in url and "completed=true" in url:
                return empty_completed
            if "todolists/10/todos.json" in url:
                return todos_10
            if "todolists/20/todos.json" in url and "completed=true" in url:
                return todos_20  # completed=True item shows up here
            if "todolists/20/todos.json" in url:
                return empty_completed
            raise AssertionError(f"Unexpected URL: {url}")

        async def fake_get(url):
            return make_response(url)

        async def fake_token(_creds, _db):
            return "tok"

        async_client = MagicMock()
        async_client.get = AsyncMock(side_effect=fake_get)

        with patch.object(
            BasecampService, "_get_valid_access_token", side_effect=fake_token
        ), patch(
            "app.services.basecamp_service.httpx.AsyncClient"
        ) as AC:
            AC.return_value.__aenter__.return_value = async_client
            report = await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )

        assert report["todos_created"] == 2
        assert report["todo_errors"] == []
        rows = await db_session.execute(
            select(Task).where(Task.project_id == project.id)
        )
        tasks = sorted(rows.scalars().all(), key=lambda t: t.name)
        assert [t.name for t in tasks] == ["[List 1] T100", "[List 2] T200"]
        statuses = {t.name: t.status for t in tasks}
        assert statuses["[List 1] T100"] == "TODO"
        assert statuses["[List 2] T200"] == "DONE"

    @pytest.mark.asyncio
    async def test_sync_per_todo_error_doesnt_abort_other_todos(
        self, db_session: AsyncSession, _enc_key
    ):
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        project, _ = await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        todolists = {"bcp-1": [{"id": "list-1", "title": "L"}]}
        # Three to-dos; the middle one will explode on dict access.
        class _Exploder(dict):
            def __getitem__(self, k):
                if k == "content":
                    raise RuntimeError("boom on to-do 2")
                return super().__getitem__(k)

        todos = {
            "list-1": [
                {"id": "td-1", "content": "Good 1", "completed": False},
                _Exploder({"id": "td-2", "completed": False}),
                {"id": "td-3", "content": "Good 3", "completed": False},
            ]
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            report = await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )

        assert report["todos_created"] == 2
        assert len(report["todo_errors"]) == 1
        assert "td-2" in report["todo_errors"][0]

        rows = await db_session.execute(
            select(Task).where(Task.project_id == project.id)
        )
        tasks = sorted(t.name for t in rows.scalars().all())
        assert tasks == ["[L] Good 1", "[L] Good 3"]

    @pytest.mark.asyncio
    async def test_sync_dry_run_returns_counts_without_writes(
        self, db_session: AsyncSession, _enc_key
    ):
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        project, _ = await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        todolists = {"bcp-1": [{"id": "list-1", "title": "L"}]}
        todos = {
            "list-1": [
                {"id": "td-1", "content": "A", "completed": False},
                {"id": "td-2", "content": "B", "completed": True},
            ]
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            report = await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=True
            )

        assert report["todos_created"] == 2
        assert report["dry_run"] is True

        # Nothing persisted
        tasks = await db_session.execute(
            select(Task).where(Task.project_id == project.id)
        )
        assert tasks.scalars().all() == []
        maps = await db_session.execute(select(BasecampTaskMapping))
        assert maps.scalars().all() == []

    @pytest.mark.asyncio
    async def test_task_mapping_row_created_on_first_sync(
        self, db_session: AsyncSession, _enc_key
    ):
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        _, _ = await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        todolists = {"bcp-1": [{"id": "list-7", "title": "Backlog"}]}
        todos = {
            "list-7": [
                {"id": "td-42", "content": "Mapping row check", "completed": False},
            ]
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )

        rows = await db_session.execute(select(BasecampTaskMapping))
        maps = rows.scalars().all()
        assert len(maps) == 1
        m = maps[0]
        assert m.company_id == company.id
        assert m.basecamp_account_id == "acct-1"
        assert m.basecamp_project_id == "bcp-1"
        assert m.basecamp_todolist_id == "list-7"
        assert m.basecamp_todo_id == "td-42"
        # The mapping links to a real Task
        task_row = await db_session.execute(
            select(Task).where(Task.id == m.task_id)
        )
        assert task_row.scalar_one() is not None

    @pytest.mark.asyncio
    async def test_task_mapping_unique_constraint_enforced(
        self, db_session: AsyncSession, _enc_key
    ):
        # Re-syncing the same to-do twice produces a single mapping row,
        # not a UNIQUE-violation crash.
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        _, _ = await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        todolists = {"bcp-1": [{"id": "list-1", "title": "L"}]}
        todos = {
            "list-1": [
                {"id": "td-1", "content": "Same item", "completed": False},
            ]
        }
        # Sync twice.
        for _ in range(2):
            p1, p2, p3 = _patch_basecamp_api(todolists, todos)
            with p1, p2, p3:
                await BasecampService.sync_todos_for_company(
                    creds, company.id, db_session, dry_run=False
                )

        rows = await db_session.execute(select(BasecampTaskMapping))
        assert len(rows.scalars().all()) == 1
        tasks = await db_session.execute(select(Task))
        assert len(tasks.scalars().all()) == 1

    @pytest.mark.asyncio
    async def test_task_name_format_includes_list_title(
        self, db_session: AsyncSession, _enc_key
    ):
        company = await _mk_company(db_session)
        _, team = await _mk_owner_and_team(db_session, company)
        _, _ = await _mk_project_and_mapping(
            db_session, company, team, basecamp_project_id="bcp-1"
        )
        creds = _mk_creds(company.id)
        db_session.add(creds)
        await db_session.flush()

        todolists = {
            "bcp-1": [
                {"id": "list-1", "title": "Engineering"},
                {"id": "list-2", "title": "Marketing"},
            ]
        }
        todos = {
            "list-1": [{"id": "td-1", "content": "Build", "completed": False}],
            "list-2": [{"id": "td-2", "content": "Promote", "completed": False}],
        }
        p1, p2, p3 = _patch_basecamp_api(todolists, todos)
        with p1, p2, p3:
            await BasecampService.sync_todos_for_company(
                creds, company.id, db_session, dry_run=False
            )

        rows = await db_session.execute(select(Task))
        names = sorted(t.name for t in rows.scalars().all())
        assert names == ["[Engineering] Build", "[Marketing] Promote"]
