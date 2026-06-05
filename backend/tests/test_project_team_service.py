from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, ProjectTeam, Team, TeamMember, User
from app.services.project_team_service import get_projects_for_team


async def _make_user(db_session: AsyncSession, role: str = "regular_user", company_id: int | None = None) -> User:
    from app.services.auth_service import AuthService

    user = User(
        email=f"user-{uuid4().hex[:8]}@example.com",
        name="User",
        password_hash=AuthService.hash_password("testpassword123"),
        role=role,
        is_active=True,
        company_id=company_id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _make_team(db_session: AsyncSession, owner: User, name: str, company_id: int | None = None) -> Team:
    team = Team(name=name, owner_id=owner.id, company_id=company_id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=owner.id, role="owner"))
    await db_session.flush()
    return team


async def _make_project(db_session: AsyncSession, team: Team, name: str, archived: bool = False) -> Project:
    project = Project(name=name, team_id=team.id, color="#3B82F6", is_archived=archived)
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.mark.asyncio
async def test_get_projects_for_team_returns_primary_and_additional(db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    extra_owner = await _make_user(db_session)
    primary_team = await _make_team(db_session, owner, "Primary")
    extra_team = await _make_team(db_session, extra_owner, "Extra")
    primary_project = await _make_project(db_session, primary_team, "Primary Project")
    additional_project = await _make_project(db_session, extra_team, "Additional Project")
    db_session.add(ProjectTeam(project_id=additional_project.id, team_id=primary_team.id, added_by_user_id=owner.id))
    await db_session.commit()

    rows = await get_projects_for_team(primary_team.id, db=db_session)

    assert {row["id"] for row in rows} == {primary_project.id, additional_project.id}
    rows_by_id = {row["id"]: row for row in rows}
    assert rows_by_id[primary_project.id]["association_type"] == "primary"
    assert rows_by_id[primary_project.id]["primary_team_id"] == primary_team.id
    assert rows_by_id[primary_project.id]["primary_team_name"] == primary_team.name
    assert rows_by_id[additional_project.id]["association_type"] == "additional"
    assert rows_by_id[additional_project.id]["primary_team_id"] == extra_team.id
    assert rows_by_id[additional_project.id]["primary_team_name"] == extra_team.name


@pytest.mark.asyncio
async def test_get_projects_for_team_excludes_archived_by_default(db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Team")
    active_project = await _make_project(db_session, team, "Active Project")
    archived_project = await _make_project(db_session, team, "Archived Project", archived=True)
    await db_session.commit()

    rows = await get_projects_for_team(team.id, db=db_session)

    assert [row["id"] for row in rows] == [active_project.id]
    assert archived_project.id not in {row["id"] for row in rows}


@pytest.mark.asyncio
async def test_get_projects_for_team_include_archived_param(db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Team")
    active_project = await _make_project(db_session, team, "Active Project")
    archived_project = await _make_project(db_session, team, "Archived Project", archived=True)
    await db_session.commit()

    rows = await get_projects_for_team(team.id, include_archived=True, db=db_session)

    assert {row["id"] for row in rows} == {active_project.id, archived_project.id}


@pytest.mark.asyncio
async def test_get_projects_for_team_returns_empty_for_team_with_no_projects(db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Team")
    await db_session.commit()

    rows = await get_projects_for_team(team.id, db=db_session)

    assert rows == []