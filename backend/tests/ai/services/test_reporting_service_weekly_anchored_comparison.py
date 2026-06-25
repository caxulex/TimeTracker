from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.ai.services.reporting_service import AIReportingService
from app.models import Company, Project, Team, TimeEntry, User


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


async def _prepare_weekly_service(db_session, monkeypatch: pytest.MonkeyPatch, test_user: User, fixed_now: datetime, today_local: date, tenant_tz: str = "UTC") -> tuple[AIReportingService, Project]:
    import app.ai.services.reporting_service as reporting_service_module

    monkeypatch.setattr(reporting_service_module, "datetime", _fixed_datetime_class(fixed_now))
    monkeypatch.setattr(reporting_service_module, "local_today", lambda _tz: today_local, raising=False)

    async def _fake_resolve_tenant_tz(_db, _user_id):
        return tenant_tz

    monkeypatch.setattr(
        reporting_service_module,
        "resolve_tenant_timezone_for_user",
        _fake_resolve_tenant_tz,
        raising=False,
    )

    unique = uuid4().hex[:8]
    company = Company(
        name=f"Anchored Compare Co {unique}",
        slug=f"anchored-compare-{unique}",
        email=f"anchored-{unique}@example.com",
        timezone=tenant_tz,
    )
    db_session.add(company)
    await db_session.flush()

    test_user.company_id = company.id

    team = Team(name=f"Anchored Team {unique}", owner_id=test_user.id, company_id=company.id)
    db_session.add(team)
    await db_session.flush()

    project = Project(name=f"Anchored Project {unique}", team_id=team.id, color="#3B82F6")
    db_session.add(project)
    await db_session.flush()

    service = AIReportingService(db=db_session, ai_client=None, cache_manager=None)

    async def _fake_feature_manager():
        return _EnabledFeatureManager()

    monkeypatch.setattr(service, "_get_feature_manager", _fake_feature_manager)
    return service, project


def _dt(y: int, m: int, d: int, hh: int = 9, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def _hours_to_timedelta(hours: float) -> timedelta:
    return timedelta(seconds=int(round(hours * 3600)))


async def _add_entry(db_session, user_id: int, project_id: int, start: datetime, hours: float, description: str) -> None:
    end = start + _hours_to_timedelta(hours)
    db_session.add(
        TimeEntry(
            user_id=user_id,
            project_id=project_id,
            start_time=start,
            end_time=end,
            duration_seconds=int(round(hours * 3600)),
            description=description,
            is_running=False,
        )
    )


@pytest.mark.asyncio
async def test_weekly_summary_anchored_comparison_daniel_like(monkeypatch: pytest.MonkeyPatch, db_session, test_user: User):
    service, project = await _prepare_weekly_service(
        db_session,
        monkeypatch,
        test_user,
        fixed_now=_dt(2026, 6, 11, 18, 0),  # Thursday
        today_local=date(2026, 6, 11),
    )

    # This week through Thu cutoff = 28.2h
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 8, 8, 0), 9.0, "this-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 9, 9, 0), 7.0, "this-tue")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 10, 9, 0), 6.0, "this-wed")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 11, 9, 0), 6.2, "this-thu")

    # Last week through same Thu cutoff = 25.5h; full last week = 41.1h
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 1, 9, 0), 6.5, "last-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 2, 9, 0), 6.0, "last-tue")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 3, 9, 0), 6.5, "last-wed")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 4, 9, 0), 6.5, "last-thu")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 5, 9, 0), 8.0, "last-fri")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 6, 9, 0), 7.6, "last-sat")

    await db_session.commit()

    result = await service.generate_weekly_summary(user_id=test_user.id, include_ai=False)

    assert result["success"] is True
    summary = result["summary"]
    metrics = summary["metrics"]

    assert metrics["last_week_hours"] == pytest.approx(41.1, abs=0.1)
    assert metrics["hours_change_pct"] == pytest.approx(10.6, abs=0.2)
    assert all(item["title"] != "Hours Decreased" for item in summary["attention_needed"])
    assert all(item["title"] != "Hours Decreased" for item in summary["insights"])


@pytest.mark.asyncio
async def test_weekly_summary_anchored_comparison_laura_like(monkeypatch: pytest.MonkeyPatch, db_session, test_user: User):
    service, project = await _prepare_weekly_service(
        db_session,
        monkeypatch,
        test_user,
        fixed_now=_dt(2026, 6, 11, 18, 0),
        today_local=date(2026, 6, 11),
    )

    # This week through cutoff = 18.2h
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 8, 9, 0), 4.5, "this-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 9, 9, 0), 4.5, "this-tue")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 10, 9, 0), 4.6, "this-wed")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 11, 9, 0), 4.6, "this-thu")

    # Last week through cutoff = 15.0h; full last week = 21.7h
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 1, 9, 0), 4.0, "last-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 2, 9, 0), 4.0, "last-tue")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 3, 9, 0), 3.5, "last-wed")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 4, 9, 0), 3.5, "last-thu")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 5, 9, 0), 3.4, "last-fri")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 6, 9, 0), 3.3, "last-sat")

    await db_session.commit()

    result = await service.generate_weekly_summary(user_id=test_user.id, include_ai=False)

    assert result["success"] is True
    summary = result["summary"]
    metrics = summary["metrics"]

    assert metrics["last_week_hours"] == pytest.approx(21.7, abs=0.1)
    assert metrics["hours_change_pct"] == pytest.approx(21.3, abs=0.2)
    assert all(item["title"] != "Hours Decreased" for item in summary["attention_needed"])
    assert all(item["title"] != "Hours Decreased" for item in summary["insights"])


@pytest.mark.asyncio
async def test_weekly_summary_zero_prior_cutoff_sets_none_and_omits_change_copy(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    test_user: User,
):
    service, project = await _prepare_weekly_service(
        db_session,
        monkeypatch,
        test_user,
        fixed_now=_dt(2026, 6, 11, 18, 0),
        today_local=date(2026, 6, 11),
    )

    # This week through cutoff has activity.
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 8, 9, 0), 3.0, "this-mon")

    # Last week has only post-cutoff activity (Fri), so comparable prior window is zero.
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 5, 10, 0), 2.0, "last-fri-only")

    await db_session.commit()

    result = await service.generate_weekly_summary(user_id=test_user.id, include_ai=False)

    assert result["success"] is True
    summary = result["summary"]
    metrics = summary["metrics"]

    assert metrics["last_week_hours"] == pytest.approx(2.0, abs=0.1)
    assert metrics["hours_change_pct"] is None
    assert "more than last week" not in summary["summary_text"]
    assert "less than last week" not in summary["summary_text"]
    assert all("Productivity " not in text for text in summary["highlights"])
    assert all(item["title"] != "Hours Decreased" for item in summary["attention_needed"])
    assert all(item["title"] != "Hours Decreased" for item in summary["insights"])


@pytest.mark.asyncio
async def test_weekly_summary_week_complete_converges_to_full_vs_full(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    test_user: User,
):
    # local_today pinned to Sunday while now is just after local week end.
    service, project = await _prepare_weekly_service(
        db_session,
        monkeypatch,
        test_user,
        fixed_now=_dt(2026, 6, 15, 0, 30),
        today_local=date(2026, 6, 14),
    )

    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 8, 9, 0), 7.0, "this-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 9, 9, 0), 7.0, "this-tue")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 1, 9, 0), 5.0, "last-mon")
    await _add_entry(db_session, test_user.id, project.id, _dt(2026, 6, 2, 9, 0), 5.0, "last-tue")

    await db_session.commit()

    result = await service.generate_weekly_summary(user_id=test_user.id, include_ai=False)

    assert result["success"] is True
    metrics = result["summary"]["metrics"]

    expected_full_vs_full_pct = ((metrics["total_hours"] - metrics["last_week_hours"]) / metrics["last_week_hours"]) * 100
    assert metrics["hours_change_pct"] == pytest.approx(expected_full_vs_full_pct, abs=0.1)
