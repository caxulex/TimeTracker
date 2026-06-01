import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.dependencies as dependencies
from app.models import Project, Task, Team, TeamMember, TimeEntry, User
from app.services.time_entry_description import resolve_description


@pytest_asyncio.fixture(autouse=True)
async def _bypass_blacklist_for_module(monkeypatch):
    async def _not_blacklisted(_: str) -> bool:
        return False

    monkeypatch.setattr(
        dependencies,
        "_check_blacklist_or_fail_closed",
        _not_blacklisted,
    )


@pytest_asyncio.fixture
async def session_team(db_session: AsyncSession, test_user: User) -> Team:
    team = Team(name="Autofill Team", owner_id=test_user.id)
    db_session.add(team)
    await db_session.flush()

    db_session.add(
        TeamMember(
            team_id=team.id,
            user_id=test_user.id,
            role="owner",
        )
    )
    await db_session.flush()
    await db_session.refresh(team)
    return team


@pytest_asyncio.fixture
async def session_project(db_session: AsyncSession, session_team: Team) -> Project:
    project = Project(
        name="Autofill Project",
        description="Project for description autofill tests",
        team_id=session_team.id,
        color="#0EA5E9",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def task_one(db_session: AsyncSession, session_project: Project) -> Task:
    task = Task(project_id=session_project.id, name="Task One")
    db_session.add(task)
    await db_session.flush()
    await db_session.refresh(task)
    return task


@pytest_asyncio.fixture
async def task_two(db_session: AsyncSession, session_project: Project) -> Task:
    task = Task(project_id=session_project.id, name="Task Two")
    db_session.add(task)
    await db_session.flush()
    await db_session.refresh(task)
    return task


class TestSessionCreateAutofill:
    @pytest.mark.asyncio
    async def test_start_timer_autofills_none_description(
        self, client: AsyncClient, auth_headers: dict, session_project: Project, task_one: Task
    ):
        response = await client.post(
            "/api/time/start",
            json={"project_id": session_project.id, "task_id": task_one.id, "description": None},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["description"] == task_one.name

    @pytest.mark.asyncio
    async def test_start_timer_autofills_empty_description(
        self, client: AsyncClient, auth_headers: dict, session_project: Project, task_one: Task
    ):
        response = await client.post(
            "/api/time/start",
            json={"project_id": session_project.id, "task_id": task_one.id, "description": ""},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["description"] == task_one.name

    @pytest.mark.asyncio
    async def test_start_timer_autofills_whitespace_description(
        self, client: AsyncClient, auth_headers: dict, session_project: Project, task_one: Task
    ):
        response = await client.post(
            "/api/time/start",
            json={"project_id": session_project.id, "task_id": task_one.id, "description": "   \t\n"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["description"] == task_one.name

    @pytest.mark.asyncio
    async def test_start_timer_keeps_non_empty_description(
        self, client: AsyncClient, auth_headers: dict, session_project: Project, task_one: Task
    ):
        response = await client.post(
            "/api/time/start",
            json={"project_id": session_project.id, "task_id": task_one.id, "description": "real txt"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["description"] == "real txt"

    @pytest.mark.asyncio
    async def test_start_timer_with_no_task_keeps_empty_description(
        self, client: AsyncClient, auth_headers: dict, session_project: Project
    ):
        response = await client.post(
            "/api/time/start",
            json={"project_id": session_project.id, "task_id": None, "description": None},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["description"] is None


class TestSessionUpdateAutofill:
    @pytest_asyncio.fixture
    async def closed_entry(
        self,
        db_session: AsyncSession,
        test_user: User,
        session_project: Project,
        task_one: Task,
    ) -> TimeEntry:
        now = datetime.now(timezone.utc)
        entry = TimeEntry(
            user_id=test_user.id,
            project_id=session_project.id,
            task_id=task_one.id,
            description="original",
            start_time=now - timedelta(hours=1),
            end_time=now - timedelta(minutes=30),
            duration_seconds=1800,
            is_running=False,
        )
        db_session.add(entry)
        await db_session.flush()
        await db_session.refresh(entry)
        return entry

    @pytest.mark.asyncio
    async def test_patch_task_change_with_empty_description_autofills(
        self,
        client: AsyncClient,
        auth_headers: dict,
        closed_entry: TimeEntry,
        task_two: Task,
    ):
        response = await client.patch(
            f"/api/time/entries/{closed_entry.id}",
            json={"task_id": task_two.id, "description": "   "},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["task_id"] == task_two.id
        assert response.json()["description"] == task_two.name

    @pytest.mark.asyncio
    async def test_patch_task_change_with_non_empty_description_keeps_user_text(
        self,
        client: AsyncClient,
        auth_headers: dict,
        closed_entry: TimeEntry,
        task_two: Task,
    ):
        response = await client.patch(
            f"/api/time/entries/{closed_entry.id}",
            json={"task_id": task_two.id, "description": "keep me"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["description"] == "keep me"

    @pytest.mark.asyncio
    async def test_put_task_change_with_empty_description_autofills(
        self,
        client: AsyncClient,
        auth_headers: dict,
        closed_entry: TimeEntry,
        task_two: Task,
    ):
        response = await client.put(
            f"/api/time/{closed_entry.id}",
            json={"task_id": task_two.id, "description": ""},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["description"] == task_two.name

    @pytest.mark.asyncio
    async def test_put_task_change_with_non_empty_description_keeps_user_text(
        self,
        client: AsyncClient,
        auth_headers: dict,
        closed_entry: TimeEntry,
        task_two: Task,
    ):
        response = await client.put(
            f"/api/time/{closed_entry.id}",
            json={"task_id": task_two.id, "description": "typed by user"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["description"] == "typed by user"

    @pytest.mark.asyncio
    async def test_patch_task_change_without_description_does_not_autofill_existing_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
        session_project: Project,
        task_one: Task,
        task_two: Task,
    ):
        now = datetime.now(timezone.utc)
        entry = TimeEntry(
            user_id=test_user.id,
            project_id=session_project.id,
            task_id=task_one.id,
            description="   ",
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
            duration_seconds=3600,
            is_running=False,
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        response = await client.patch(
            f"/api/time/entries/{entry.id}",
            json={"task_id": task_two.id},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["description"] == "   "


class TestManualCreateAutofill:
    @pytest.mark.asyncio
    async def test_create_manual_entry_autofills_description_when_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        session_project: Project,
        task_one: Task,
    ):
        now = datetime.now(timezone.utc)
        response = await client.post(
            "/api/time",
            json={
                "project_id": session_project.id,
                "task_id": task_one.id,
                "description": "",
                "start_time": (now - timedelta(hours=1)).isoformat(),
                "end_time": now.isoformat(),
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert response.json()["description"] == task_one.name

    @pytest.mark.asyncio
    async def test_create_manual_entry_preserves_explicit_description(
        self,
        client: AsyncClient,
        auth_headers: dict,
        session_project: Project,
        task_one: Task,
    ):
        now = datetime.now(timezone.utc)
        response = await client.post(
            "/api/time",
            json={
                "project_id": session_project.id,
                "task_id": task_one.id,
                "description": "typed by user",
                "start_time": (now - timedelta(hours=1)).isoformat(),
                "end_time": now.isoformat(),
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert response.json()["description"] == "typed by user"

    @pytest.mark.asyncio
    async def test_create_manual_entry_no_autofill_without_task(
        self,
        client: AsyncClient,
        auth_headers: dict,
        session_project: Project,
    ):
        now = datetime.now(timezone.utc)
        response = await client.post(
            "/api/time",
            json={
                "project_id": session_project.id,
                "description": "",
                "start_time": (now - timedelta(hours=1)).isoformat(),
                "end_time": now.isoformat(),
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        assert response.json()["description"] == ""


class TestResolveDescriptionHelper:
    @pytest.mark.asyncio
    async def test_resolve_description_keeps_empty_when_task_id_invalid(
        self,
        db_session: AsyncSession,
    ):
        resolved = await resolve_description(
            description="",
            task_id=999_999,
            db=db_session,
        )
        assert resolved == ""


class TestSessionFinalizationAutofill:
    @pytest.mark.asyncio
    async def test_switch_creates_new_entry_with_task_name_when_description_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        session_project: Project,
        task_one: Task,
        task_two: Task,
    ):
        start_response = await client.post(
            "/api/time/start",
            json={"project_id": session_project.id, "task_id": task_one.id, "description": "active"},
            headers=auth_headers,
        )
        assert start_response.status_code == 201

        switch_response = await client.post(
            "/api/time/switch",
            json={"project_id": session_project.id, "task_id": task_two.id, "description": "   "},
            headers=auth_headers,
        )
        assert switch_response.status_code == 200
        assert switch_response.json()["description"] == task_two.name

    @pytest.mark.asyncio
    async def test_switch_creates_new_entry_and_keeps_non_empty_description(
        self,
        client: AsyncClient,
        auth_headers: dict,
        session_project: Project,
        task_one: Task,
        task_two: Task,
    ):
        start_response = await client.post(
            "/api/time/start",
            json={"project_id": session_project.id, "task_id": task_one.id, "description": "active"},
            headers=auth_headers,
        )
        assert start_response.status_code == 201

        switch_response = await client.post(
            "/api/time/switch",
            json={"project_id": session_project.id, "task_id": task_two.id, "description": "real txt"},
            headers=auth_headers,
        )
        assert switch_response.status_code == 200
        assert switch_response.json()["description"] == "real txt"


class TestBackfillMigration:
    @pytest.mark.asyncio
    async def test_backfill_sql_updates_only_empty_descriptions(
        self,
        db_session: AsyncSession,
        test_user: User,
        session_project: Project,
        task_one: Task,
    ):
        now = datetime.now(timezone.utc)

        row_empty = TimeEntry(
            user_id=test_user.id,
            project_id=session_project.id,
            task_id=task_one.id,
            description="   ",
            start_time=now - timedelta(hours=3),
            end_time=now - timedelta(hours=2),
            duration_seconds=3600,
            is_running=False,
        )
        row_real = TimeEntry(
            user_id=test_user.id,
            project_id=session_project.id,
            task_id=task_one.id,
            description="real",
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
            duration_seconds=3600,
            is_running=False,
        )
        row_no_task = TimeEntry(
            user_id=test_user.id,
            project_id=session_project.id,
            task_id=None,
            description="",
            start_time=now - timedelta(hours=1),
            end_time=now - timedelta(minutes=30),
            duration_seconds=1800,
            is_running=False,
        )
        db_session.add_all([row_empty, row_real, row_no_task])
        await db_session.commit()

        migration_path = (
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "029_backfill_time_entry_descriptions_from_task.py"
        )
        spec = importlib.util.spec_from_file_location("m029_backfill", migration_path)
        assert spec is not None and spec.loader is not None
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)

        await db_session.execute(text(migration_module.BACKFILL_SQL))
        await db_session.commit()

        await db_session.refresh(row_empty)
        await db_session.refresh(row_real)
        await db_session.refresh(row_no_task)

        assert row_empty.description == task_one.name
        assert row_real.description == "real"
        assert row_no_task.description == ""
