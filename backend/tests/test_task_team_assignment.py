import uuid

import pytest

from app.models import Company, Project, Task, Team, TeamMember, User
from app.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def _bypass_blacklist_check(monkeypatch):
    async def _fake_check(_jti: str) -> bool:  # noqa: ARG001
        return False

    monkeypatch.setattr("app.dependencies._check_blacklist_or_fail_closed", _fake_check)


async def _create_company(db_session, name: str) -> Company:
    company = Company(
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
    )
    db_session.add(company)
    await db_session.flush()
    return company


async def _create_user(db_session, company_id: int) -> User:
    user = User(
        email=f"task-user-{uuid.uuid4().hex[:8]}@example.com",
        name="Task User",
        password_hash=AuthService.hash_password("testpassword123"),
        role="regular_user",
        is_active=True,
        company_id=company_id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


def _headers_for_user(user: User) -> dict[str, str]:
    token = AuthService.create_access_token({"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


async def _create_project_for_user(db_session, user: User, name: str = "Project A") -> Project:
    team = Team(name=f"Team-{uuid.uuid4().hex[:6]}", owner_id=user.id, company_id=user.company_id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=user.id, role="owner"))
    await db_session.flush()

    project = Project(team_id=team.id, name=name, color="#3B82F6")
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.mark.asyncio
async def test_create_task_with_team_ids(client, db_session):
    company = await _create_company(db_session, "Task Create Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    extra_team = Team(name="SEO Team", owner_id=user.id, company_id=company.id, color="#10B981")
    db_session.add(extra_team)
    await db_session.flush()

    response = await client.post(
        "/api/tasks",
        headers=_headers_for_user(user),
        json={
            "name": "Build integration",
            "project_id": project.id,
            "status": "TODO",
            "team_ids": [extra_team.id],
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert [t["id"] for t in data["teams"]] == [extra_team.id]


@pytest.mark.asyncio
async def test_update_task_replaces_team_set(client, db_session):
    company = await _create_company(db_session, "Task Update Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    task = Task(project_id=project.id, name="Task", status="TODO")
    db_session.add(task)
    await db_session.flush()

    t1 = Team(name="SEO", owner_id=user.id, company_id=company.id, color="#10B981")
    t2 = Team(name="Admin", owner_id=user.id, company_id=company.id, color="#F59E0B")
    db_session.add_all([t1, t2])
    await db_session.flush()

    first_update = await client.put(
        f"/api/tasks/{task.id}",
        headers=_headers_for_user(user),
        json={"team_ids": [t1.id]},
    )
    assert first_update.status_code == 200, first_update.text

    second_update = await client.put(
        f"/api/tasks/{task.id}",
        headers=_headers_for_user(user),
        json={"team_ids": [t2.id]},
    )

    assert second_update.status_code == 200, second_update.text
    assert [t["id"] for t in second_update.json()["teams"]] == [t2.id]


@pytest.mark.asyncio
async def test_update_task_with_empty_teams_clears(client, db_session):
    company = await _create_company(db_session, "Task Clear Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    task = Task(project_id=project.id, name="Task", status="TODO")
    team = Team(name="Dev", owner_id=user.id, company_id=company.id)
    db_session.add_all([task, team])
    await db_session.flush()
    await db_session.commit()

    assign_response = await client.put(
        f"/api/tasks/{task.id}",
        headers=_headers_for_user(user),
        json={"team_ids": [team.id]},
    )
    assert assign_response.status_code == 200, assign_response.text

    response = await client.put(
        f"/api/tasks/{task.id}",
        headers=_headers_for_user(user),
        json={"team_ids": []},
    )

    assert response.status_code == 200
    assert response.json()["teams"] == []


@pytest.mark.asyncio
async def test_list_tasks_filter_by_single_team(client, db_session):
    company = await _create_company(db_session, "Task Filter Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    task_a = Task(project_id=project.id, name="A", status="TODO")
    task_b = Task(project_id=project.id, name="B", status="TODO")
    team = Team(name="SEO", owner_id=user.id, company_id=company.id)
    db_session.add_all([task_a, task_b, team])
    await db_session.flush()
    await db_session.commit()

    assign_response = await client.put(
        f"/api/tasks/{task_a.id}",
        headers=_headers_for_user(user),
        json={"team_ids": [team.id]},
    )
    assert assign_response.status_code == 200, assign_response.text

    response = await client.get(
        f"/api/tasks?team_ids={team.id}",
        headers=_headers_for_user(user),
    )

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == ["A"]


@pytest.mark.asyncio
async def test_task_response_includes_teams_array(client, db_session):
    company = await _create_company(db_session, "Task Response Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    task = Task(project_id=project.id, name="Task", status="TODO")
    team = Team(name="Reporting", owner_id=user.id, company_id=company.id, color="#8B5CF6")
    db_session.add_all([task, team])
    await db_session.flush()
    await db_session.commit()

    assign_response = await client.put(
        f"/api/tasks/{task.id}",
        headers=_headers_for_user(user),
        json={"team_ids": [team.id]},
    )
    assert assign_response.status_code == 200, assign_response.text

    response = await client.get(f"/api/tasks/{task.id}", headers=_headers_for_user(user))
    assert response.status_code == 200
    data = response.json()
    assert "teams" in data
    assert data["teams"][0]["name"] == "Reporting"
