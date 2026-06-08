from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Project, Team, TeamMember, User
from app.services.auth_service import AuthService
from app.services.project_service import find_similar_projects, normalize_for_comparison


async def _make_company(db_session: AsyncSession, name: str) -> Company:
    company = Company(
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{uuid4().hex[:6]}",
        email=f"{uuid4().hex[:8]}@example.com",
    )
    db_session.add(company)
    await db_session.flush()
    return company


async def _make_user(
    db_session: AsyncSession,
    *,
    role: str = "regular_user",
    company_id: int | None = None,
) -> User:
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


async def _make_team(db_session: AsyncSession, *, owner: User, name: str, company_id: int | None) -> Team:
    team = Team(name=name, owner_id=owner.id, company_id=company_id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=owner.id, role="owner"))
    await db_session.flush()
    return team


async def _make_project(
    db_session: AsyncSession,
    *,
    team: Team,
    name: str,
    archived: bool = False,
) -> Project:
    project = Project(
        name=name,
        description="",
        color="#3B82F6",
        team_id=team.id,
        is_archived=archived,
    )
    db_session.add(project)
    await db_session.flush()
    return project


def _headers_for(user: User) -> dict[str, str]:
    token = AuthService.create_access_token({"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


def test_normalize_for_comparison_strips_whitespace_and_punctuation():
    assert normalize_for_comparison("  Shae Marcus - Consulting! ") == "shaemarcusconsulting"


def test_normalize_for_comparison_lowercases():
    assert normalize_for_comparison("Email INVESTIGATION") == "emailinvestigation"


@pytest.mark.asyncio
async def test_find_similar_exact_match_returns_score_1(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    await _make_project(db_session, team=team, name="Email Investigation")
    await db_session.commit()

    matches = await find_similar_projects(db_session, company.id, "Email Investigation")

    assert len(matches) == 1
    assert matches[0].match_type == "exact"
    assert matches[0].match_score == 1.0


@pytest.mark.asyncio
async def test_find_similar_substring_returns_high_score(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    await _make_project(db_session, team=team, name="Shae Marcus Consulting")
    await db_session.commit()

    matches = await find_similar_projects(db_session, company.id, "ShaeMarcusCon")

    assert len(matches) == 1
    assert matches[0].match_type == "substring"
    assert 0.8 <= matches[0].match_score <= 0.9


@pytest.mark.asyncio
async def test_substring_does_not_match_when_ratio_too_low(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    await _make_project(db_session, team=team, name="Development")
    await db_session.commit()

    matches_for_de = await find_similar_projects(db_session, company.id, "de")
    matches_for_dev = await find_similar_projects(db_session, company.id, "dev")

    assert matches_for_de == []
    assert matches_for_dev == []


@pytest.mark.asyncio
async def test_substring_matches_when_ratio_sufficient(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    development = await _make_project(db_session, team=team, name="Development")
    shae = await _make_project(db_session, team=team, name="ShaeMarcusConsulting")
    await db_session.commit()

    develop_matches = await find_similar_projects(db_session, company.id, "develop")
    shae_matches = await find_similar_projects(db_session, company.id, "ShaeMarcus")

    assert any(match.id == development.id and match.match_type == "substring" for match in develop_matches)
    assert any(match.id == shae.id and match.match_type == "substring" for match in shae_matches)


@pytest.mark.asyncio
async def test_substring_ratio_exact_50_percent_matches(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    project = await _make_project(db_session, team=team, name="1234567890abcdefghij")
    await db_session.commit()

    matches = await find_similar_projects(db_session, company.id, "1234567890")

    assert any(match.id == project.id and match.match_type == "substring" for match in matches)


@pytest.mark.asyncio
async def test_find_similar_fuzzy_within_levenshtein_threshold(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    await _make_project(db_session, team=team, name="Email Investigation")
    await db_session.commit()

    matches = await find_similar_projects(db_session, company.id, "Email Investigaton")

    assert len(matches) == 1
    assert matches[0].match_type == "fuzzy"
    assert matches[0].match_score == 0.7


@pytest.mark.asyncio
async def test_find_similar_dated_variants_do_not_match(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    await _make_project(db_session, team=team, name="Monthly Security Report - May 2026")
    await _make_project(db_session, team=team, name="Patch SMC Wordpress sites - April")
    await db_session.commit()

    monthly_matches = await find_similar_projects(db_session, company.id, "Monthly Security Report - June 2026")
    patch_matches = await find_similar_projects(db_session, company.id, "Patch SMC Wordpress sites - May")

    assert monthly_matches == []
    assert patch_matches == []


@pytest.mark.asyncio
async def test_find_similar_excludes_self_when_exclude_id_provided(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    original = await _make_project(db_session, team=team, name="Email Investigation")
    await db_session.commit()

    matches = await find_similar_projects(
        db_session,
        company.id,
        "Email Investigation",
        exclude_id=original.id,
    )

    assert matches == []


@pytest.mark.asyncio
async def test_find_similar_excludes_archived_by_default(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    await _make_project(db_session, team=team, name="Email Investigation", archived=True)
    await db_session.commit()

    matches = await find_similar_projects(db_session, company.id, "Email Investigation")

    assert matches == []


@pytest.mark.asyncio
async def test_find_similar_includes_archived_with_param(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    archived = await _make_project(db_session, team=team, name="Email Investigation", archived=True)
    await db_session.commit()

    matches = await find_similar_projects(
        db_session,
        company.id,
        "Email Investigation",
        include_archived=True,
    )

    assert len(matches) == 1
    assert matches[0].id == archived.id
    assert matches[0].is_archived is True


@pytest.mark.asyncio
async def test_find_similar_scoped_to_same_company(db_session: AsyncSession):
    company_a = await _make_company(db_session, "Company A")
    company_b = await _make_company(db_session, "Company B")

    owner_a = await _make_user(db_session, company_id=company_a.id)
    owner_b = await _make_user(db_session, company_id=company_b.id)

    team_a = await _make_team(db_session, owner=owner_a, name="A Team", company_id=company_a.id)
    team_b = await _make_team(db_session, owner=owner_b, name="B Team", company_id=company_b.id)

    await _make_project(db_session, team=team_a, name="Email Investigation")
    await _make_project(db_session, team=team_b, name="Email Investigation")
    await db_session.commit()

    matches = await find_similar_projects(db_session, company_a.id, "Email Investigation")

    assert len(matches) == 1
    assert matches[0].team_name == "A Team"


@pytest.mark.asyncio
async def test_find_similar_returns_max_10_results_ordered_by_score(db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)

    await _make_project(db_session, team=team, name="Email Investigation")
    for index in range(12):
        await _make_project(db_session, team=team, name=f"Email Investigation {index}")
    await db_session.commit()

    matches = await find_similar_projects(db_session, company.id, "Email Investigation")

    assert len(matches) == 10
    assert matches[0].match_type == "exact"
    assert matches[0].match_score == 1.0
    assert matches == sorted(matches, key=lambda row: (-row.match_score, row.name.lower(), row.id))


@pytest.mark.asyncio
async def test_find_similar_endpoint_unauthorized_returns_401(client: AsyncClient):
    response = await client.get(
        "/api/projects/similar",
        params={"name": "Email Investigation"},
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_similar_endpoint_returns_expected_shape(client: AsyncClient, db_session: AsyncSession):
    company = await _make_company(db_session, "SMC")
    owner = await _make_user(db_session, company_id=company.id)
    team = await _make_team(db_session, owner=owner, name="SEO Team", company_id=company.id)
    project = await _make_project(db_session, team=team, name="Email Investigation")
    await db_session.commit()

    response = await client.get(
        "/api/projects/similar",
        params={"name": "Email Investigation"},
        headers=_headers_for(owner),
    )

    assert response.status_code == 200
    payload = response.json()
    assert "matches" in payload
    assert len(payload["matches"]) == 1
    row = payload["matches"][0]
    assert row["id"] == project.id
    assert row["name"] == "Email Investigation"
    assert row["team_id"] == team.id
    assert row["team_name"] == "SEO Team"
    assert row["is_archived"] is False
    assert row["match_type"] == "exact"
    assert row["match_score"] == 1.0
