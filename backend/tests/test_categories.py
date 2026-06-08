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


async def _create_user(db_session, company_id: int, email_prefix: str = "user") -> User:
    user = User(
        email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@example.com",
        name="Category User",
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
async def test_seed_creates_five_categories_per_company(db_session):
    company_a = await _create_company(db_session, "Alpha Co")
    company_b = await _create_company(db_session, "Beta Co")
    await db_session.commit()

    defaults = [
        ("IT Security", "#DC2626"),
        ("SEO", "#10B981"),
        ("Dev", "#3B82F6"),
        ("Admin", "#F59E0B"),
        ("Reporting", "#8B5CF6"),
    ]

    for name, color in defaults:
        await db_session.execute(
            text(
                """
                INSERT INTO categories (company_id, name, color, created_at, updated_at)
                SELECT c.id, :name, :color, now(), now()
                FROM companies c
                ON CONFLICT (company_id, name) WHERE deleted_at IS NULL DO NOTHING
                """
            ),
            {"name": name, "color": color},
        )
    await db_session.commit()

    rows = (await db_session.execute(select(Category.company_id, Category.name))).all()
    by_company: dict[int, set[str]] = {}
    for company_id, name in rows:
        by_company.setdefault(company_id, set()).add(name)

    assert by_company[company_a.id] == {item[0] for item in defaults}
    assert by_company[company_b.id] == {item[0] for item in defaults}


@pytest.mark.asyncio
async def test_create_category_returns_201(client, db_session):
    company = await _create_company(db_session, "Create Co")
    user = await _create_user(db_session, company.id)
    await db_session.commit()

    response = await client.post(
        "/api/categories",
        headers=_headers_for_user(user),
        json={"name": "IT Security", "color": "#DC2626", "description": "Security work"},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "IT Security"
    assert data["color"] == "#DC2626"
    assert data["task_count"] == 0


@pytest.mark.asyncio
async def test_create_category_unique_name_per_company(client, db_session):
    company = await _create_company(db_session, "Unique Co")
    user = await _create_user(db_session, company.id)
    await db_session.commit()

    payload = {"name": "SEO", "color": "#10B981"}
    first = await client.post("/api/categories", headers=_headers_for_user(user), json=payload)
    second = await client.post("/api/categories", headers=_headers_for_user(user), json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_create_category_cross_company_same_name_allowed(client, db_session):
    company_a = await _create_company(db_session, "A Co")
    company_b = await _create_company(db_session, "B Co")
    user_a = await _create_user(db_session, company_a.id, "a")
    user_b = await _create_user(db_session, company_b.id, "b")
    await db_session.commit()

    payload = {"name": "Dev", "color": "#3B82F6"}
    response_a = await client.post("/api/categories", headers=_headers_for_user(user_a), json=payload)
    response_b = await client.post("/api/categories", headers=_headers_for_user(user_b), json=payload)

    assert response_a.status_code == 201
    assert response_b.status_code == 201


@pytest.mark.asyncio
async def test_update_category_rename_works(client, db_session):
    company = await _create_company(db_session, "Rename Co")
    user = await _create_user(db_session, company.id)
    await db_session.commit()

    created = await client.post(
        "/api/categories",
        headers=_headers_for_user(user),
        json={"name": "Admin", "color": "#F59E0B"},
    )
    category_id = created.json()["id"]

    updated = await client.put(
        f"/api/categories/{category_id}",
        headers=_headers_for_user(user),
        json={"name": "Operations", "color": "#F59E0B"},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Operations"


@pytest.mark.asyncio
async def test_update_category_rename_to_existing_name_errors(client, db_session):
    company = await _create_company(db_session, "Rename Error Co")
    user = await _create_user(db_session, company.id)
    await db_session.commit()

    await client.post(
        "/api/categories",
        headers=_headers_for_user(user),
        json={"name": "SEO", "color": "#10B981"},
    )
    second = await client.post(
        "/api/categories",
        headers=_headers_for_user(user),
        json={"name": "Dev", "color": "#3B82F6"},
    )
    second_id = second.json()["id"]

    response = await client.put(
        f"/api/categories/{second_id}",
        headers=_headers_for_user(user),
        json={"name": "SEO"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_soft_delete_category_preserves_history(client, db_session):
    company = await _create_company(db_session, "Delete Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)
    task = Task(project_id=project.id, name="Monthly patch", status="TODO")
    db_session.add(task)
    await db_session.flush()

    category = Category(company_id=company.id, name="IT Security", color="#DC2626", created_by=user.id, updated_by=user.id)
    db_session.add(category)
    await db_session.flush()
    db_session.add(TaskCategory(task_id=task.id, category_id=category.id, created_by=user.id))
    await db_session.commit()

    response = await client.delete(f"/api/categories/{category.id}", headers=_headers_for_user(user))
    assert response.status_code == 200

    await db_session.refresh(task)
    await db_session.refresh(category)

    assert category.deleted_at is not None
    links = (await db_session.execute(select(TaskCategory).where(TaskCategory.task_id == task.id))).scalars().all()
    assert links == []
    assert task.id is not None


@pytest.mark.asyncio
async def test_soft_delete_returns_affected_task_count(client, db_session):
    company = await _create_company(db_session, "Delete Count Co")
    user = await _create_user(db_session, company.id)
    project = await _create_project_for_user(db_session, user)

    task_a = Task(project_id=project.id, name="Task A", status="TODO")
    task_b = Task(project_id=project.id, name="Task B", status="TODO")
    db_session.add_all([task_a, task_b])
    await db_session.flush()

    category = Category(company_id=company.id, name="Admin", color="#F59E0B", created_by=user.id, updated_by=user.id)
    db_session.add(category)
    await db_session.flush()
    db_session.add_all([
        TaskCategory(task_id=task_a.id, category_id=category.id, created_by=user.id),
        TaskCategory(task_id=task_b.id, category_id=category.id, created_by=user.id),
    ])
    await db_session.commit()

    response = await client.delete(f"/api/categories/{category.id}", headers=_headers_for_user(user))
    assert response.status_code == 200
    assert response.json()["task_count"] == 2


@pytest.mark.asyncio
async def test_list_categories_excludes_soft_deleted_by_default(client, db_session):
    company = await _create_company(db_session, "List Co")
    user = await _create_user(db_session, company.id)

    active = Category(company_id=company.id, name="Dev", color="#3B82F6", created_by=user.id, updated_by=user.id)
    deleted = Category(company_id=company.id, name="Old", color="#6B7280", created_by=user.id, updated_by=user.id)
    db_session.add_all([active, deleted])
    await db_session.flush()
    await db_session.execute(
        text("UPDATE categories SET deleted_at = now(), deleted_by = :uid WHERE id = :cid"),
        {"uid": user.id, "cid": deleted.id},
    )
    await db_session.commit()

    response = await client.get("/api/categories", headers=_headers_for_user(user))
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert "Dev" in names
    assert "Old" not in names


@pytest.mark.asyncio
async def test_categories_scoped_to_requester_company(client, db_session):
    company_a = await _create_company(db_session, "Scope A")
    company_b = await _create_company(db_session, "Scope B")
    user_a = await _create_user(db_session, company_a.id, "a")
    user_b = await _create_user(db_session, company_b.id, "b")

    db_session.add_all([
        Category(company_id=company_a.id, name="A-Only", color="#3B82F6", created_by=user_a.id, updated_by=user_a.id),
        Category(company_id=company_b.id, name="B-Only", color="#10B981", created_by=user_b.id, updated_by=user_b.id),
    ])
    await db_session.commit()

    response = await client.get("/api/categories", headers=_headers_for_user(user_a))
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == ["A-Only"]
