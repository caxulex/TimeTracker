import uuid

import pytest

from app.models import Company, User
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


async def _create_admin_user(db_session, company_id: int) -> User:
    user = User(
        email=f"team-admin-{uuid.uuid4().hex[:8]}@example.com",
        name="Team Admin",
        password_hash=AuthService.hash_password("testpassword123"),
        role="admin",
        is_active=True,
        company_id=company_id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


def _headers_for_user(user: User) -> dict[str, str]:
    token = AuthService.create_access_token({"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_team_returns_default_color(client, db_session):
    company = await _create_company(db_session, "Color Default Co")
    user = await _create_admin_user(db_session, company.id)
    await db_session.commit()

    response = await client.post(
        "/api/teams",
        headers=_headers_for_user(user),
        json={"name": "Design"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["color"] == "#6B7280"


@pytest.mark.asyncio
async def test_update_team_color_accepts_hex(client, db_session):
    company = await _create_company(db_session, "Color Update Co")
    user = await _create_admin_user(db_session, company.id)
    await db_session.commit()

    created = await client.post(
        "/api/teams",
        headers=_headers_for_user(user),
        json={"name": "Ops"},
    )
    assert created.status_code == 201, created.text
    team_id = created.json()["id"]

    response = await client.put(
        f"/api/teams/{team_id}",
        headers=_headers_for_user(user),
        json={"color": "#10B981"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["color"] == "#10B981"


@pytest.mark.asyncio
async def test_update_team_color_rejects_invalid_hex(client, db_session):
    company = await _create_company(db_session, "Color Invalid Co")
    user = await _create_admin_user(db_session, company.id)
    await db_session.commit()

    created = await client.post(
        "/api/teams",
        headers=_headers_for_user(user),
        json={"name": "QA"},
    )
    assert created.status_code == 201, created.text
    team_id = created.json()["id"]

    response = await client.put(
        f"/api/teams/{team_id}",
        headers=_headers_for_user(user),
        json={"color": "green"},
    )

    assert response.status_code == 422
