from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Project, ProjectTeam, Task, Team, TeamMember, TimeEntry, User
from app.services.auth_service import AuthService


def _headers_for(user: User) -> dict[str, str]:
    token = AuthService.create_access_token({"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


async def _make_user(db_session: AsyncSession, role: str = "regular_user") -> User:
    user = User(
        email=f"user-{uuid4().hex[:8]}@example.com",
        name="User",
        password_hash=AuthService.hash_password("testpassword123"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _make_team(db_session: AsyncSession, owner: User, name: str) -> Team:
    team = Team(name=name, owner_id=owner.id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=owner.id, role="owner"))
    await db_session.flush()
    return team


async def _make_project(db_session: AsyncSession, team: Team, name: str, archived: bool = False) -> Project:
    project = Project(name=name, description="", color="#3B82F6", team_id=team.id, is_archived=archived)
    db_session.add(project)
    await db_session.flush()
    return project


async def _make_task(db_session: AsyncSession, project: Project, name: str) -> Task:
    task = Task(project_id=project.id, name=name, status="TODO")
    db_session.add(task)
    await db_session.flush()
    return task


async def _make_entry(
    db_session: AsyncSession,
    *,
    project: Project,
    user: User,
    task: Task | None = None,
) -> TimeEntry:
    entry = TimeEntry(
        user_id=user.id,
        project_id=project.id,
        task_id=task.id if task else None,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        duration_seconds=120,
        description="seed",
        is_running=False,
    )
    db_session.add(entry)
    await db_session.flush()
    return entry


@pytest.mark.asyncio
async def test_update_project_works_for_any_authenticated_user(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    outsider = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    project = await _make_project(db_session, team, "Original")
    await db_session.commit()

    response = await client.put(
        f"/api/projects/{project.id}",
        json={"name": "Updated by outsider"},
        headers=_headers_for(outsider),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated by outsider"


@pytest.mark.asyncio
async def test_archive_project_toggles_is_archived(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    project = await _make_project(db_session, team, "Archive Me")
    await db_session.commit()

    response = await client.patch(
        f"/api/projects/{project.id}/archive",
        json={"is_archived": True},
        headers=_headers_for(owner),
    )

    assert response.status_code == 200
    assert response.json()["is_archived"] is True


@pytest.mark.asyncio
async def test_unarchive_project_toggles_is_archived_back(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    project = await _make_project(db_session, team, "Archive Me", archived=True)
    await db_session.commit()

    response = await client.patch(
        f"/api/projects/{project.id}/archive",
        json={"is_archived": False},
        headers=_headers_for(owner),
    )

    assert response.status_code == 200
    assert response.json()["is_archived"] is False


@pytest.mark.asyncio
async def test_delete_project_cascades_tasks_entries_associations(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    extra_owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    extra_team = await _make_team(db_session, extra_owner, "Admin")
    project = await _make_project(db_session, team, "Delete Me")
    task = await _make_task(db_session, project, "Task A")
    await _make_entry(db_session, project=project, user=owner, task=task)
    db_session.add(ProjectTeam(project_id=project.id, team_id=extra_team.id, added_by_user_id=owner.id))
    await db_session.commit()

    response = await client.delete(f"/api/projects/{project.id}", headers=_headers_for(owner))

    assert response.status_code == 200
    data = response.json()
    assert data["deleted_tasks"] == 1
    assert data["deleted_entries"] == 1

    assert (await db_session.execute(select(Project).where(Project.id == project.id))).scalar_one_or_none() is None
    assert (await db_session.execute(select(Task).where(Task.project_id == project.id))).scalars().all() == []
    assert (await db_session.execute(select(TimeEntry).where(TimeEntry.project_id == project.id))).scalars().all() == []
    assert (await db_session.execute(select(ProjectTeam).where(ProjectTeam.project_id == project.id))).scalars().all() == []


@pytest.mark.asyncio
async def test_delete_project_creates_audit_log_before_deletion(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    project = await _make_project(db_session, team, "Audit Delete")
    await _make_task(db_session, project, "Task A")
    await _make_entry(db_session, project=project, user=owner)
    await db_session.commit()

    response = await client.delete(f"/api/projects/{project.id}", headers=_headers_for(owner))
    assert response.status_code == 200

    audit = (
        await db_session.execute(
            select(AuditLog)
            .where(
                AuditLog.resource_type == "project",
                AuditLog.resource_id == project.id,
                AuditLog.action == "DELETE",
            )
            .order_by(AuditLog.id.desc())
        )
    ).scalar_one_or_none()

    assert audit is not None
    assert "Hard-deleted project" in (audit.details or "")


@pytest.mark.asyncio
async def test_delete_project_returns_counts_of_cascaded_deletions(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    project = await _make_project(db_session, team, "Delete Counts")
    t1 = await _make_task(db_session, project, "Task 1")
    t2 = await _make_task(db_session, project, "Task 2")
    await _make_entry(db_session, project=project, user=owner, task=t1)
    await _make_entry(db_session, project=project, user=owner, task=t2)
    await _make_entry(db_session, project=project, user=owner)
    await db_session.commit()

    response = await client.delete(f"/api/projects/{project.id}", headers=_headers_for(owner))

    assert response.status_code == 200
    assert response.json() == {"deleted_tasks": 2, "deleted_entries": 3}


@pytest.mark.asyncio
async def test_merge_projects_moves_tasks_to_target(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    source = await _make_project(db_session, team, "Source")
    target = await _make_project(db_session, team, "Target")
    moved_task = await _make_task(db_session, source, "Move Me")
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{source.id}/merge",
        json={"target_project_id": target.id},
        headers=_headers_for(owner),
    )

    assert response.status_code == 200
    assert response.json()["moved_tasks"] == 1

    await db_session.refresh(moved_task)
    assert moved_task.project_id == target.id


@pytest.mark.asyncio
async def test_merge_projects_renames_conflicting_task_names(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    source = await _make_project(db_session, team, "Source")
    target = await _make_project(db_session, team, "Target")
    conflict_name = "Patch SMC sites"
    task = await _make_task(db_session, source, conflict_name)
    await _make_task(db_session, target, conflict_name)
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{source.id}/merge",
        json={"target_project_id": target.id},
        headers=_headers_for(owner),
    )

    assert response.status_code == 200
    renamed = response.json()["renamed_tasks"]
    assert any(name.startswith(f"{conflict_name} (from Source)") for name in renamed)

    await db_session.refresh(task)
    assert task.project_id == target.id
    assert task.name in renamed


@pytest.mark.asyncio
async def test_merge_projects_moves_time_entries_to_target(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    source = await _make_project(db_session, team, "Source")
    target = await _make_project(db_session, team, "Target")
    entry = await _make_entry(db_session, project=source, user=owner)
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{source.id}/merge",
        json={"target_project_id": target.id},
        headers=_headers_for(owner),
    )

    assert response.status_code == 200
    assert response.json()["moved_entries"] == 1

    await db_session.refresh(entry)
    assert entry.project_id == target.id


@pytest.mark.asyncio
async def test_merge_projects_migrates_team_associations(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    secondary_owner = await _make_user(db_session)
    team_a = await _make_team(db_session, owner, "Team A")
    team_b = await _make_team(db_session, secondary_owner, "Team B")
    source = await _make_project(db_session, team_a, "Source")
    target = await _make_project(db_session, team_a, "Target")
    db_session.add(ProjectTeam(project_id=source.id, team_id=team_b.id, added_by_user_id=owner.id))
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{source.id}/merge",
        json={"target_project_id": target.id},
        headers=_headers_for(owner),
    )

    assert response.status_code == 200

    target_teams = (
        await db_session.execute(select(ProjectTeam.team_id).where(ProjectTeam.project_id == target.id))
    ).scalars().all()
    assert team_b.id in target_teams

    source_teams = (
        await db_session.execute(select(ProjectTeam.team_id).where(ProjectTeam.project_id == source.id))
    ).scalars().all()
    assert source_teams == []


@pytest.mark.asyncio
async def test_merge_projects_archives_source(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    source = await _make_project(db_session, team, "Source")
    target = await _make_project(db_session, team, "Target")
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{source.id}/merge",
        json={"target_project_id": target.id},
        headers=_headers_for(owner),
    )

    assert response.status_code == 200
    assert response.json()["archived_source"] is True

    await db_session.refresh(source)
    assert source.is_archived is True


@pytest.mark.asyncio
async def test_merge_projects_rejects_same_source_and_target(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    source = await _make_project(db_session, team, "Source")
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{source.id}/merge",
        json={"target_project_id": source.id},
        headers=_headers_for(owner),
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_merge_projects_rejects_archived_target(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    source = await _make_project(db_session, team, "Source")
    target = await _make_project(db_session, team, "Target", archived=True)
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{source.id}/merge",
        json={"target_project_id": target.id},
        headers=_headers_for(owner),
    )

    assert response.status_code == 400
