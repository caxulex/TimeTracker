from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Project, ProjectTeam, Team, TeamMember, User
from app.services.auth_service import AuthService


def _headers_for(user: User) -> dict[str, str]:
    token = AuthService.create_access_token({"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


async def _make_user(db_session: AsyncSession, role: str = "regular_user", company_id: int | None = None) -> User:
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
async def test_get_team_projects_returns_primary_and_additional(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    other_owner = await _make_user(db_session)
    current_team = await _make_team(db_session, owner, "Current Team")
    other_team = await _make_team(db_session, other_owner, "Other Team")
    primary_project = await _make_project(db_session, current_team, "Primary Project")
    shared_project = await _make_project(db_session, other_team, "Shared Project")
    db_session.add(ProjectTeam(project_id=shared_project.id, team_id=current_team.id, added_by_user_id=owner.id))
    await db_session.commit()

    response = await client.get(f"/api/teams/{current_team.id}/projects", headers=_headers_for(owner))
    assert response.status_code == 200
    payload = response.json()
    assert {row["id"] for row in payload} == {primary_project.id, shared_project.id}
    rows_by_id = {row["id"]: row for row in payload}
    assert rows_by_id[primary_project.id]["association_type"] == "primary"
    assert rows_by_id[shared_project.id]["association_type"] == "additional"
    assert rows_by_id[shared_project.id]["primary_team_name"] == other_team.name


@pytest.mark.asyncio
async def test_get_team_projects_excludes_archived_by_default(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Team")
    active_project = await _make_project(db_session, team, "Active Project")
    archived_project = await _make_project(db_session, team, "Archived Project", archived=True)
    await db_session.commit()

    response = await client.get(f"/api/teams/{team.id}/projects", headers=_headers_for(owner))
    assert response.status_code == 200
    payload = response.json()
    assert [row["id"] for row in payload] == [active_project.id]
    assert archived_project.id not in {row["id"] for row in payload}


@pytest.mark.asyncio
async def test_get_team_projects_include_archived_param(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Team")
    active_project = await _make_project(db_session, team, "Active Project")
    archived_project = await _make_project(db_session, team, "Archived Project", archived=True)
    await db_session.commit()

    response = await client.get(
        f"/api/teams/{team.id}/projects",
        params={"include_archived": True},
        headers=_headers_for(owner),
    )
    assert response.status_code == 200
    assert {row["id"] for row in response.json()} == {active_project.id, archived_project.id}


@pytest.mark.asyncio
async def test_get_team_projects_returns_empty_for_team_with_no_projects(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Team")
    await db_session.commit()

    response = await client.get(f"/api/teams/{team.id}/projects", headers=_headers_for(owner))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_team_projects_returns_404_for_nonexistent_team(client: AsyncClient, auth_headers: dict) -> None:
    response = await client.get("/api/teams/999999/projects", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_team_projects_unauthorized_returns_401(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Team")
    await db_session.commit()

    response = await client.get(
        f"/api/teams/{team.id}/projects",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_add_project_to_team_works_for_any_authenticated_user(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    outsider = await _make_user(db_session)
    primary_team = await _make_team(db_session, owner, "Primary Team")
    add_team = await _make_team(db_session, await _make_user(db_session), "Add Team")
    project = await _make_project(db_session, primary_team, "Project")
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{project.id}/teams",
        json={"team_id": add_team.id},
        headers=_headers_for(outsider),
    )
    assert response.status_code == 201

    assoc = await db_session.execute(
        select(ProjectTeam).where(ProjectTeam.project_id == project.id, ProjectTeam.team_id == add_team.id)
    )
    assert assoc.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_remove_project_from_team_works_for_any_authenticated_user(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    outsider = await _make_user(db_session)
    primary_team = await _make_team(db_session, owner, "Primary Team")
    remove_team = await _make_team(db_session, await _make_user(db_session), "Remove Team")
    project = await _make_project(db_session, primary_team, "Project")
    db_session.add(ProjectTeam(project_id=project.id, team_id=remove_team.id, added_by_user_id=owner.id))
    await db_session.commit()

    response = await client.delete(
        f"/api/projects/{project.id}/teams/{remove_team.id}",
        headers=_headers_for(outsider),
    )
    assert response.status_code == 204

    assoc = await db_session.execute(
        select(ProjectTeam).where(ProjectTeam.project_id == project.id, ProjectTeam.team_id == remove_team.id)
    )
    assert assoc.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_add_project_to_team_creates_audit_log(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Team")
    other_team = await _make_team(db_session, await _make_user(db_session), "Other Team")
    project = await _make_project(db_session, team, "Project")
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{project.id}/teams",
        json={"team_id": other_team.id},
        headers=_headers_for(owner),
    )
    assert response.status_code == 201

    log_row = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "project_team.added", AuditLog.resource_type == "project_team")
    )
    assert log_row.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_remove_project_from_team_creates_audit_log(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Team")
    other_team = await _make_team(db_session, await _make_user(db_session), "Other Team")
    project = await _make_project(db_session, team, "Project")
    db_session.add(ProjectTeam(project_id=project.id, team_id=other_team.id, added_by_user_id=owner.id))
    await db_session.commit()

    response = await client.delete(
        f"/api/projects/{project.id}/teams/{other_team.id}",
        headers=_headers_for(owner),
    )
    assert response.status_code == 204

    log_row = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "project_team.removed", AuditLog.resource_type == "project_team")
    )
    assert log_row.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_add_project_to_team_is_idempotent(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Team")
    other_team = await _make_team(db_session, await _make_user(db_session), "Other Team")
    project = await _make_project(db_session, team, "Project")
    db_session.add(ProjectTeam(project_id=project.id, team_id=other_team.id, added_by_user_id=owner.id))
    await db_session.commit()

    first = await client.post(
        f"/api/projects/{project.id}/teams",
        json={"team_id": other_team.id},
        headers=_headers_for(owner),
    )
    second = await client.post(
        f"/api/projects/{project.id}/teams",
        json={"team_id": other_team.id},
        headers=_headers_for(owner),
    )
    assert first.status_code == 201
    assert second.status_code == 201

    assoc = await db_session.execute(
        select(ProjectTeam).where(ProjectTeam.project_id == project.id, ProjectTeam.team_id == other_team.id)
    )
    assert assoc.scalar_one_or_none() is not None