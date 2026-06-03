from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Company, Project, ProjectTeam, Team, TeamMember, TimeEntry, User
from app.services.auth_service import AuthService
from app.services.project_team_service import add_team_to_project


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


async def _make_project(db_session: AsyncSession, team: Team, name: str = "Project X") -> Project:
    project = Project(name=name, team_id=team.id, color="#3B82F6")
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.mark.asyncio
async def test_add_team_success_and_audit_log(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    target_member = await _make_user(db_session)
    engineering = await _make_team(db_session, owner, "Engineering")
    admin_team = await _make_team(db_session, target_member, "Admin")
    db_session.add(TeamMember(team_id=admin_team.id, user_id=owner.id, role="member"))
    project = await _make_project(db_session, engineering, "SMC")
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{project.id}/teams",
        json={"team_id": admin_team.id},
        headers=_headers_for(owner),
    )
    assert response.status_code == 201

    assoc = await db_session.execute(
        select(ProjectTeam).where(ProjectTeam.project_id == project.id, ProjectTeam.team_id == admin_team.id)
    )
    assert assoc.scalar_one_or_none() is not None

    log_row = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "project_team.added", AuditLog.resource_type == "project_team")
    )
    assert log_row.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_add_team_requires_team_membership(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    outsider = await _make_user(db_session)
    engineering = await _make_team(db_session, owner, "Engineering")
    admin_team = await _make_team(db_session, await _make_user(db_session), "Admin")
    project = await _make_project(db_session, engineering, "SMC")
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{project.id}/teams",
        json={"team_id": admin_team.id},
        headers=_headers_for(outsider),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_add_team_already_associated_returns_409(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    engineering = await _make_team(db_session, owner, "Engineering")
    admin_team = await _make_team(db_session, owner, "Admin")
    project = await _make_project(db_session, engineering, "SMC")
    db_session.add(ProjectTeam(project_id=project.id, team_id=admin_team.id, added_by_user_id=owner.id))
    await db_session.commit()

    response = await client.post(
        f"/api/projects/{project.id}/teams",
        json={"team_id": admin_team.id},
        headers=_headers_for(owner),
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_remove_team_primary_rejected(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    engineering = await _make_team(db_session, owner, "Engineering")
    project = await _make_project(db_session, engineering, "SMC")
    await db_session.commit()

    response = await client.delete(
        f"/api/projects/{project.id}/teams/{engineering.id}",
        headers=_headers_for(owner),
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_project_teams_primary_first(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    engineering = await _make_team(db_session, owner, "Engineering")
    admin_team = await _make_team(db_session, owner, "Admin")
    project = await _make_project(db_session, engineering, "SMC")
    db_session.add(ProjectTeam(project_id=project.id, team_id=admin_team.id, added_by_user_id=owner.id))
    await db_session.commit()

    response = await client.get(f"/api/projects/{project.id}/teams", headers=_headers_for(owner))
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["team_id"] == engineering.id
    assert payload[0]["is_primary"] is True
    assert {row["team_id"] for row in payload} == {engineering.id, admin_team.id}


@pytest.mark.asyncio
async def test_visibility_user_sees_project_via_associated_team(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    laura = await _make_user(db_session)
    engineering = await _make_team(db_session, owner, "Engineering")
    admin_team = await _make_team(db_session, laura, "Admin")
    project = await _make_project(db_session, engineering, "SMC")
    await db_session.commit()

    pre = await client.get("/api/projects", headers=_headers_for(laura))
    assert pre.status_code == 200
    assert project.id not in {row["id"] for row in pre.json()["items"]}

    add = await client.post(
        f"/api/projects/{project.id}/teams",
        json={"team_id": admin_team.id},
        headers=_headers_for(laura),
    )
    assert add.status_code == 201

    post = await client.get("/api/projects", headers=_headers_for(laura))
    assert post.status_code == 200
    assert project.id in {row["id"] for row in post.json()["items"]}

    timer = await client.post(
        "/api/time/start",
        json={"project_id": project.id, "description": "Cross-team work"},
        headers=_headers_for(laura),
    )
    assert timer.status_code == 201


@pytest.mark.asyncio
async def test_remove_revokes_visibility(client: AsyncClient, db_session: AsyncSession):
    owner = await _make_user(db_session)
    member = await _make_user(db_session)
    engineering = await _make_team(db_session, owner, "Engineering")
    admin_team = await _make_team(db_session, member, "Admin")
    project = await _make_project(db_session, engineering, "SMC")
    db_session.add(ProjectTeam(project_id=project.id, team_id=admin_team.id, added_by_user_id=owner.id))
    await db_session.commit()

    visible_before = await client.get("/api/projects", headers=_headers_for(member))
    assert project.id in {row["id"] for row in visible_before.json()["items"]}

    remove = await client.delete(
        f"/api/projects/{project.id}/teams/{admin_team.id}",
        headers=_headers_for(member),
    )
    assert remove.status_code == 204

    visible_after = await client.get("/api/projects", headers=_headers_for(member))
    assert project.id not in {row["id"] for row in visible_after.json()["items"]}


@pytest.mark.asyncio
async def test_visibility_admin_unaffected(client: AsyncClient, db_session: AsyncSession):
    admin = await _make_user(db_session, role="admin")
    owner = await _make_user(db_session)
    team = await _make_team(db_session, owner, "Engineering")
    project = await _make_project(db_session, team, "SMC")
    await db_session.commit()

    response = await client.get("/api/projects", headers=_headers_for(admin))
    assert response.status_code == 200
    assert project.id in {row["id"] for row in response.json()["items"]}


@pytest.mark.asyncio
async def test_add_team_different_company_rejected_service_level(db_session: AsyncSession):
    company_a = Company(name="A", slug=f"a-{uuid4().hex[:6]}", email="a@example.com")
    company_b = Company(name="B", slug=f"b-{uuid4().hex[:6]}", email="b@example.com")
    db_session.add_all([company_a, company_b])
    await db_session.flush()

    actor = await _make_user(db_session, company_id=company_b.id)
    team_a = await _make_team(db_session, await _make_user(db_session, company_id=company_a.id), "A-Team", company_id=company_a.id)
    team_b = await _make_team(db_session, actor, "B-Team", company_id=company_b.id)
    project = await _make_project(db_session, team_a, "Cross")
    await db_session.commit()

    ok, error = await add_team_to_project(
        project_id=project.id,
        team_id=team_b.id,
        acting_user_id=actor.id,
        acting_user_email=actor.email,
        company_id=None,
        db=db_session,
    )
    assert ok is False
    assert error == "different_company"


def test_migration_036_backfill_sql_present():
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "036_project_teams_association.py"
    text = migration_path.read_text(encoding="utf-8")
    assert "INSERT INTO project_teams" in text
    assert "SELECT id, team_id" in text
