from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, ProjectTeam, Task, Team, TeamMember, TimeEntry, User
from app.services.auth_service import AuthService
from app.services.project_service import get_merge_preview, merge_projects


async def _make_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"user-{uuid4().hex[:8]}@example.com",
        name="User",
        password_hash=AuthService.hash_password("testpassword123"),
        role="regular_user",
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


async def _make_project(db_session: AsyncSession, team: Team, name: str) -> Project:
    project = Project(name=name, description="", color="#3B82F6", team_id=team.id)
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.mark.asyncio
async def test_merge_projects_is_atomic(db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    source = await _make_project(db_session, team, "Source")
    target = await _make_project(db_session, team, "Target")

    task = Task(project_id=source.id, name="Task A", status="TODO")
    db_session.add(task)
    entry = TimeEntry(
        user_id=owner.id,
        project_id=source.id,
        task_id=None,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        duration_seconds=100,
        description="seed",
        is_running=False,
    )
    db_session.add(entry)
    db_session.add(ProjectTeam(project_id=source.id, team_id=team.id, added_by_user_id=owner.id))
    await db_session.commit()

    with pytest.raises(RuntimeError):
        await merge_projects(
            db=db_session,
            source_project=source,
            target_project=target,
            acting_user=owner,
            fail_after_task_move_for_test=True,
        )

    await db_session.refresh(source)
    await db_session.refresh(task)
    await db_session.refresh(entry)

    assert source.is_archived is False
    assert task.project_id == source.id
    assert entry.project_id == source.id


@pytest.mark.asyncio
async def test_get_merge_preview_reports_conflicts(db_session: AsyncSession):
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    source = await _make_project(db_session, team, "Source")
    target = await _make_project(db_session, team, "Target")

    db_session.add(Task(project_id=source.id, name="Monthly report", status="TODO"))
    db_session.add(Task(project_id=target.id, name="Monthly report", status="TODO"))
    db_session.add(Task(project_id=target.id, name="Other", status="TODO"))
    db_session.add(
        TimeEntry(
            user_id=owner.id,
            project_id=source.id,
            task_id=None,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            duration_seconds=60,
            description="seed",
            is_running=False,
        )
    )
    await db_session.commit()

    preview = await get_merge_preview(db=db_session, source_project=source, target_project=target)

    assert preview.tasks_to_move == 1
    assert preview.entries_to_move == 1
    assert preview.task_name_conflicts == ["Monthly report"]
    assert preview.target_existing_tasks == 2
    assert preview.source_will_be_archived is True


@pytest.mark.asyncio
async def test_merge_projects_migrates_team_associations_without_duplicates(db_session: AsyncSession):
    owner = await _make_user(db_session)
    second_owner = await _make_user(db_session)
    team_a = await _make_team(db_session, owner, "Team A")
    team_b = await _make_team(db_session, second_owner, "Team B")
    source = await _make_project(db_session, team_a, "Source")
    target = await _make_project(db_session, team_a, "Target")

    db_session.add(ProjectTeam(project_id=source.id, team_id=team_a.id, added_by_user_id=owner.id))
    db_session.add(ProjectTeam(project_id=source.id, team_id=team_b.id, added_by_user_id=owner.id))
    db_session.add(ProjectTeam(project_id=target.id, team_id=team_a.id, added_by_user_id=owner.id))
    await db_session.commit()

    result = await merge_projects(
        db=db_session,
        source_project=source,
        target_project=target,
        acting_user=owner,
    )

    assert result.archived_source is True

    target_teams = (
        await db_session.execute(select(ProjectTeam.team_id).where(ProjectTeam.project_id == target.id))
    ).scalars().all()
    assert sorted(target_teams) == sorted({team_a.id, team_b.id})

    source_teams = (
        await db_session.execute(select(ProjectTeam.team_id).where(ProjectTeam.project_id == source.id))
    ).scalars().all()
    assert source_teams == []
