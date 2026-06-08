import uuid

import pytest
from sqlalchemy import select, text

from app.models import Category, Company, Project, Task, TaskCategory, Team, TeamMember, User
from app.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def _bypass_blacklist_check(monkeypatch):
    async def _fake_check(_jti: str) -> bool:  # noqa: ARG001
        return False

    monkeypatch.setattr("app.dependencies._check_blacklist_or_fail_closed", _fake_check)


@pytest.fixture(autouse=True)
async def _ensure_category_tables(db_session):
    await db_session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES companies(id),
                name VARCHAR(50) NOT NULL,
                color VARCHAR(20) NOT NULL DEFAULT '#6B7280',
                description TEXT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                created_by INTEGER NULL REFERENCES users(id),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_by INTEGER NULL REFERENCES users(id),
                deleted_at TIMESTAMPTZ NULL,
                deleted_by INTEGER NULL REFERENCES users(id)
            )
            """
        )
    )
    await db_session.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_company_name_active
            ON categories (company_id, name)
            WHERE deleted_at IS NULL
            """
        )
    )
    await db_session.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_categories_company_id_deleted_at
            ON categories (company_id, deleted_at)
            """
        )
    )
    await db_session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS task_categories (
                task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                created_by INTEGER NULL REFERENCES users(id),
                PRIMARY KEY (task_id, category_id)
            )
            """
        )
    )
    await db_session.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_task_categories_category_id_task_id
            ON task_categories (category_id, task_id)
            """
        )
    )
    await db_session.commit()


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
async def test_create_task_with_category_ids(client, db_session):
    company = await _create_company(db_session, "Task Create Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    category = Category(company_id=company.id, name="Dev", color="#3B82F6", created_by=user.id, updated_by=user.id)
    db_session.add(category)
    await db_session.commit()

    response = await client.post(
        "/api/tasks",
        headers=_headers_for_user(user),
        json={
            "name": "Build integration",
            "project_id": project.id,
            "status": "TODO",
            "category_ids": [category.id],
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert [c["id"] for c in data["categories"]] == [category.id]


@pytest.mark.asyncio
async def test_update_task_replaces_category_set(client, db_session):
    company = await _create_company(db_session, "Task Update Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    task = Task(project_id=project.id, name="Task", status="TODO")
    db_session.add(task)
    await db_session.flush()

    c1 = Category(company_id=company.id, name="SEO", color="#10B981", created_by=user.id, updated_by=user.id)
    c2 = Category(company_id=company.id, name="Admin", color="#F59E0B", created_by=user.id, updated_by=user.id)
    db_session.add_all([c1, c2])
    await db_session.flush()

    db_session.add(TaskCategory(task_id=task.id, category_id=c1.id, created_by=user.id))
    await db_session.commit()

    response = await client.put(
        f"/api/tasks/{task.id}",
        headers=_headers_for_user(user),
        json={"category_ids": [c2.id]},
    )

    assert response.status_code == 200, response.text
    assert [c["id"] for c in response.json()["categories"]] == [c2.id]


@pytest.mark.asyncio
async def test_update_task_with_empty_categories_clears(client, db_session):
    company = await _create_company(db_session, "Task Clear Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    task = Task(project_id=project.id, name="Task", status="TODO")
    category = Category(company_id=company.id, name="Dev", color="#3B82F6", created_by=user.id, updated_by=user.id)
    db_session.add_all([task, category])
    await db_session.flush()
    db_session.add(TaskCategory(task_id=task.id, category_id=category.id, created_by=user.id))
    await db_session.commit()

    response = await client.put(
        f"/api/tasks/{task.id}",
        headers=_headers_for_user(user),
        json={"category_ids": []},
    )

    assert response.status_code == 200
    assert response.json()["categories"] == []


@pytest.mark.asyncio
async def test_list_tasks_filter_by_single_category(client, db_session):
    company = await _create_company(db_session, "Task Filter Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    task_a = Task(project_id=project.id, name="A", status="TODO")
    task_b = Task(project_id=project.id, name="B", status="TODO")
    cat = Category(company_id=company.id, name="SEO", color="#10B981", created_by=user.id, updated_by=user.id)
    db_session.add_all([task_a, task_b, cat])
    await db_session.flush()
    db_session.add(TaskCategory(task_id=task_a.id, category_id=cat.id, created_by=user.id))
    await db_session.commit()

    response = await client.get(
        f"/api/tasks?category_ids={cat.id}",
        headers=_headers_for_user(user),
    )

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == ["A"]


@pytest.mark.asyncio
async def test_list_tasks_filter_by_multiple_categories_or_logic(client, db_session):
    company = await _create_company(db_session, "Task Filter OR Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    task_a = Task(project_id=project.id, name="A", status="TODO")
    task_b = Task(project_id=project.id, name="B", status="TODO")
    task_c = Task(project_id=project.id, name="C", status="TODO")
    c1 = Category(company_id=company.id, name="Dev", color="#3B82F6", created_by=user.id, updated_by=user.id)
    c2 = Category(company_id=company.id, name="Admin", color="#F59E0B", created_by=user.id, updated_by=user.id)
    db_session.add_all([task_a, task_b, task_c, c1, c2])
    await db_session.flush()
    db_session.add_all([
        TaskCategory(task_id=task_a.id, category_id=c1.id, created_by=user.id),
        TaskCategory(task_id=task_b.id, category_id=c2.id, created_by=user.id),
    ])
    await db_session.commit()

    response = await client.get(
        f"/api/tasks?category_ids={c1.id},{c2.id}",
        headers=_headers_for_user(user),
    )

    assert response.status_code == 200
    names = sorted(item["name"] for item in response.json()["items"])
    assert names == ["A", "B"]


@pytest.mark.asyncio
async def test_task_response_includes_categories_array(client, db_session):
    company = await _create_company(db_session, "Task Response Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    task = Task(project_id=project.id, name="Task", status="TODO")
    category = Category(company_id=company.id, name="Reporting", color="#8B5CF6", created_by=user.id, updated_by=user.id)
    db_session.add_all([task, category])
    await db_session.flush()
    db_session.add(TaskCategory(task_id=task.id, category_id=category.id, created_by=user.id))
    await db_session.commit()

    response = await client.get(f"/api/tasks/{task.id}", headers=_headers_for_user(user))
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert data["categories"][0]["name"] == "Reporting"
