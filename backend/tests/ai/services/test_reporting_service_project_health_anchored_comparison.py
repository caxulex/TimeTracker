from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.ai.services.reporting_service import AIReportingService
from app.models import Company, Project, Task, Team, TimeEntry, User
from app.services.auth_service import AuthService


class _EnabledFeatureManager:
    async def is_enabled(self, _feature: str, _user_id: int) -> bool:
        return True

    async def log_usage(self, **_kwargs) -> None:
        return None


def _fixed_datetime_class(fixed_now: datetime):
    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    return _FixedDateTime


def _dt(y: int, m: int, d: int, hh: int = 9, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def _hours_to_timedelta(hours: float) -> timedelta:
    return timedelta(seconds=int(round(hours * 3600)))


async def _add_entry(db_session, user_id: int, project_id: int, start: datetime, hours: float, description: str) -> None:
    db_session.add(
        TimeEntry(
            user_id=user_id,
            project_id=project_id,
            start_time=start,
            end_time=start + _hours_to_timedelta(hours),
            duration_seconds=int(round(hours * 3600)),
            description=description,
            is_running=False,
        )
    )


async def _prepare_project_health_service(db_session, monkeypatch: pytest.MonkeyPatch, test_user: User, fixed_now: datetime):
    import app.ai.services.reporting_service as reporting_service_module

    monkeypatch.setattr(reporting_service_module, "datetime", _fixed_datetime_class(fixed_now))

    unique = uuid4().hex[:8]
    company = Company(
        name=f"Project Health Co {unique}",
        slug=f"project-health-{unique}",
        email=f"project-health-{unique}@example.com",
        timezone="UTC",
    )
    db_session.add(company)
    await db_session.flush()

    test_user.company_id = company.id

    second_user = User(
        email=f"second-{unique}@example.com",
        name="Second Contributor",
        password_hash=AuthService.hash_password("testpassword123"),
        role="regular_user",
        is_active=True,
        company_id=company.id,
    )
    db_session.add(second_user)
    await db_session.flush()

    team = Team(name=f"Project Health Team {unique}", owner_id=test_user.id, company_id=company.id)
    db_session.add(team)
    await db_session.flush()

    project = Project(name=f"Project Health Project {unique}", team_id=team.id, color="#3B82F6")
    db_session.add(project)
    await db_session.flush()

    for index in range(5):
        db_session.add(Task(project_id=project.id, name=f"Done Task {index}", status="DONE"))

    # Add an older second-contributor entry so contributor_count=2 without
    # affecting the compared week windows.
    await _add_entry(db_session, second_user.id, project.id, _dt(2026, 4, 1, 9, 0), 1.0, "historic-contributor")
    await db_session.commit()

    service = AIReportingService(db=db_session, ai_client=None, cache_manager=None)

    async def _fake_feature_manager():
        return _EnabledFeatureManager()

    monkeypatch.setattr(service, "_get_feature_manager", _fake_feature_manager)
    return service, project


def _insight_titles(result: dict) -> list[str]:
    return [item["title"] for item in result.get("insights", [])]


@pytest.mark.asyncio
async def test_project_health_false_midweek_penalty_is_removed_and_displayed_hours_stay_raw(
    db_session,
    monkeypatch,
    test_user: User,
):
    service, project = await _prepare_project_health_service(
        db_session,
        monkeypatch,
        test_user,
        fixed_now=_dt(2026, 6, 19, 12, 0),
    )

    # This week so far = 32.3h (Mon-Fri noon-ish)
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 15, 8, 0), 8.0, "this-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 16, 8, 0), 8.0, "this-tue")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 17, 8, 0), 8.0, "this-wed")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 18, 8, 0), 6.0, "this-thu")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 19, 9, 0), 2.3, "this-fri-am")

    # Last week full = 40.6h, but through same Fri-noon cutoff = 33.2h.
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 8, 8, 0), 8.0, "last-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 9, 8, 0), 8.0, "last-tue")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 10, 8, 0), 8.0, "last-wed")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 11, 8, 0), 7.0, "last-thu")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 12, 9, 0), 2.2, "last-fri-am")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 12, 13, 0), 4.0, "last-fri-pm")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 13, 9, 0), 3.4, "last-sat")

    await db_session.commit()

    result = await service.generate_project_health(user_id=test_user.id, project_id=project.id)

    assert result["success"] is True
    assert result["metrics"]["this_week_hours"] == pytest.approx(32.3, abs=0.1)
    assert result["metrics"]["last_week_hours"] == pytest.approx(40.6, abs=0.1)
    assert result["metrics"]["activity_trend"] == "stable"
    assert result["health_score"] == 100
    assert "Decreasing Activity" not in _insight_titles(result)


@pytest.mark.asyncio
async def test_project_health_real_decline_stays_penalized_after_anchoring(
    db_session,
    monkeypatch,
    test_user: User,
):
    service, project = await _prepare_project_health_service(
        db_session,
        monkeypatch,
        test_user,
        fixed_now=_dt(2026, 6, 19, 12, 0),
    )

    # This week so far = 24.0h
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 15, 8, 0), 6.0, "this-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 16, 8, 0), 6.0, "this-tue")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 17, 8, 0), 6.0, "this-wed")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 18, 8, 0), 4.0, "this-thu")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 19, 9, 0), 2.0, "this-fri-am")

    # Last week full = 40.6h, through same cutoff = 33.2h.
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 8, 8, 0), 8.0, "last-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 9, 8, 0), 8.0, "last-tue")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 10, 8, 0), 8.0, "last-wed")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 11, 8, 0), 7.0, "last-thu")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 12, 9, 0), 2.2, "last-fri-am")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 12, 13, 0), 4.0, "last-fri-pm")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 13, 9, 0), 3.4, "last-sat")

    await db_session.commit()

    result = await service.generate_project_health(user_id=test_user.id, project_id=project.id)

    assert result["success"] is True
    assert result["metrics"]["activity_trend"] == "decreasing"
    assert result["health_score"] == 85
    assert "Decreasing Activity" in _insight_titles(result)


@pytest.mark.asyncio
async def test_project_health_zero_prior_cutoff_becomes_new_without_penalty(
    db_session,
    monkeypatch,
    test_user: User,
):
    service, project = await _prepare_project_health_service(
        db_session,
        monkeypatch,
        test_user,
        fixed_now=_dt(2026, 6, 19, 12, 0),
    )

    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 15, 9, 0), 3.0, "this-mon")

    # Prior week activity exists only after the comparable cutoff (Saturday),
    # so the anchored prior baseline should be zero.
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 13, 9, 0), 8.0, "last-sat-only")

    await db_session.commit()

    result = await service.generate_project_health(user_id=test_user.id, project_id=project.id)

    assert result["success"] is True
    assert result["metrics"]["activity_trend"] == "new"
    assert result["health_score"] == 95
    assert "Decreasing Activity" not in _insight_titles(result)


@pytest.mark.asyncio
async def test_project_health_week_complete_converges_to_full_vs_full(
    db_session,
    monkeypatch,
    test_user: User,
):
    service, project = await _prepare_project_health_service(
        db_session,
        monkeypatch,
        test_user,
        fixed_now=_dt(2026, 6, 21, 23, 0),
    )

    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 15, 9, 0), 7.0, "this-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 16, 9, 0), 7.0, "this-tue")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 8, 9, 0), 5.0, "last-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 9, 9, 0), 5.0, "last-tue")

    await db_session.commit()

    result = await service.generate_project_health(user_id=test_user.id, project_id=project.id)

    assert result["success"] is True
    assert result["metrics"]["this_week_hours"] == pytest.approx(14.0, abs=0.1)
    assert result["metrics"]["last_week_hours"] == pytest.approx(10.0, abs=0.1)
    assert result["metrics"]["activity_trend"] == "increasing"
