from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.ai.services.reporting_service import AIReportingService
from app.models import Company, Project, Team, TimeEntry, User


class _EnabledFeatureManager:
    async def is_enabled(self, _feature: str, _user_id: int) -> bool:
        return True

    async def log_usage(self, **_kwargs) -> None:
        return None


def _fixed_now_utc() -> datetime:
    return datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)


async def _patch_week_context(monkeypatch: pytest.MonkeyPatch):
    import app.ai.services.reporting_service as reporting_service_module

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            fixed = _fixed_now_utc()
            if tz is None:
                return fixed.replace(tzinfo=None)
            return fixed.astimezone(tz)

    monkeypatch.setattr(reporting_service_module, "datetime", _FixedDateTime)
    monkeypatch.setattr(reporting_service_module, "local_today", lambda _tz: date(2026, 6, 18), raising=False)

    async def _fake_resolve_tenant_tz(_db, _user_id):
        return "UTC"

    monkeypatch.setattr(
        reporting_service_module,
        "resolve_tenant_timezone_for_user",
        _fake_resolve_tenant_tz,
        raising=False,
    )


async def _seed_weekly_entries_with_optional_meeting(
    db_session,
    test_user: User,
    *,
    include_meeting: bool,
) -> tuple[Project, Project]:
    company = Company(
        name="Weekly Meeting Co",
        slug=f"weekly-meeting-{test_user.id}",
        email=f"weekly-meeting-{test_user.id}@example.com",
        timezone="UTC",
    )
    db_session.add(company)
    await db_session.flush()
    test_user.company_id = company.id

    team = Team(name="Weekly Team", owner_id=test_user.id, company_id=company.id)
    db_session.add(team)
    await db_session.flush()

    project_a = Project(name="Project Alpha", team_id=team.id, color="#3B82F6")
    project_b = Project(name="Project Beta", team_id=team.id, color="#10B981")
    db_session.add_all([project_a, project_b])
    await db_session.flush()

    # Week containing 2026-06-18 is 2026-06-15..2026-06-21 (UTC in this test).
    base = datetime(2026, 6, 16, 9, 0, tzinfo=timezone.utc)
    entries = [
        TimeEntry(
            user_id=test_user.id,
            project_id=project_a.id,
            start_time=base,
            end_time=base + timedelta(hours=20),
            duration_seconds=20 * 3600,
            description="Project Alpha work",
            is_running=False,
        ),
        TimeEntry(
            user_id=test_user.id,
            project_id=project_b.id,
            start_time=base + timedelta(hours=24),
            end_time=base + timedelta(hours=24, minutes=30),
            duration_seconds=30 * 60,
            description="Project Beta work",
            is_running=False,
        ),
    ]

    if include_meeting:
        entries.append(
            TimeEntry(
                user_id=test_user.id,
                project_id=None,
                start_time=base + timedelta(hours=30),
                end_time=base + timedelta(hours=34, minutes=30),
                duration_seconds=int(4.5 * 3600),
                description="[Meeting] Planning",
                is_running=False,
            )
        )

    db_session.add_all(entries)
    await db_session.commit()
    return project_a, project_b


@pytest.mark.asyncio
async def test_weekly_summary_includes_meeting_breakdown_and_reconciles(db_session, monkeypatch, test_user: User):
    await _patch_week_context(monkeypatch)
    project_a, _project_b = await _seed_weekly_entries_with_optional_meeting(
        db_session, test_user, include_meeting=True
    )

    service = AIReportingService(db=db_session, ai_client=None, cache_manager=None)

    async def _fake_feature_manager():
        return _EnabledFeatureManager()

    monkeypatch.setattr(service, "_get_feature_manager", _fake_feature_manager)

    result = await service.generate_weekly_summary(user_id=test_user.id, include_ai=False)
    assert result["success"] is True

    metrics = result["summary"]["metrics"]
    top_projects = metrics["top_projects"]

    meeting_row = next((p for p in top_projects if p.get("project_name") == "Meeting"), None)
    assert meeting_row is not None
    assert meeting_row.get("hours") == pytest.approx(4.5, abs=0.01)

    # Ensure real projects are still present and keyed by id.
    alpha_row = next((p for p in top_projects if p.get("project_id") == project_a.id), None)
    assert alpha_row is not None

    rows_hours_sum = sum(float(p.get("hours", 0)) for p in top_projects)
    assert rows_hours_sum == pytest.approx(float(metrics["total_hours"]), abs=0.01)

    percentage_sum = sum(float(p.get("percentage", 0)) for p in top_projects)
    assert percentage_sum == pytest.approx(100.0, abs=0.2)


@pytest.mark.asyncio
async def test_weekly_summary_project_percentage_uses_total_hours_denominator(db_session, monkeypatch, test_user: User):
    await _patch_week_context(monkeypatch)
    project_a, _project_b = await _seed_weekly_entries_with_optional_meeting(
        db_session, test_user, include_meeting=True
    )

    service = AIReportingService(db=db_session, ai_client=None, cache_manager=None)

    async def _fake_feature_manager():
        return _EnabledFeatureManager()

    monkeypatch.setattr(service, "_get_feature_manager", _fake_feature_manager)

    result = await service.generate_weekly_summary(user_id=test_user.id, include_ai=False)
    assert result["success"] is True

    metrics = result["summary"]["metrics"]
    top_projects = metrics["top_projects"]

    alpha_row = next(p for p in top_projects if p.get("project_id") == project_a.id)
    expected_pct = round((float(alpha_row["hours"]) / float(metrics["total_hours"])) * 100, 1)
    assert float(alpha_row.get("percentage", 0)) == pytest.approx(expected_pct, abs=0.1)


@pytest.mark.asyncio
async def test_weekly_summary_no_meeting_row_when_no_meetings(db_session, monkeypatch, test_user: User):
    await _patch_week_context(monkeypatch)
    await _seed_weekly_entries_with_optional_meeting(db_session, test_user, include_meeting=False)

    service = AIReportingService(db=db_session, ai_client=None, cache_manager=None)

    async def _fake_feature_manager():
        return _EnabledFeatureManager()

    monkeypatch.setattr(service, "_get_feature_manager", _fake_feature_manager)

    result = await service.generate_weekly_summary(user_id=test_user.id, include_ai=False)
    assert result["success"] is True

    metrics = result["summary"]["metrics"]
    top_projects = metrics["top_projects"]

    assert not any(p.get("project_name") == "Meeting" for p in top_projects)
    rows_hours_sum = sum(float(p.get("hours", 0)) for p in top_projects)
    assert rows_hours_sum == pytest.approx(float(metrics["total_hours"]), abs=0.01)


@pytest.mark.asyncio
async def test_weekly_summary_meeting_can_dominate_breakdown_but_highlight_uses_top_real_project(
    db_session,
    monkeypatch,
    test_user: User,
):
    await _patch_week_context(monkeypatch)

    company = Company(
        name="Weekly Meeting Dom Co",
        slug=f"weekly-meeting-dom-{test_user.id}",
        email=f"weekly-meeting-dom-{test_user.id}@example.com",
        timezone="UTC",
    )
    db_session.add(company)
    await db_session.flush()
    test_user.company_id = company.id

    team = Team(name="Weekly Team", owner_id=test_user.id, company_id=company.id)
    db_session.add(team)
    await db_session.flush()

    project = Project(name="Project Alpha", team_id=team.id, color="#3B82F6")
    db_session.add(project)
    await db_session.flush()

    base = datetime(2026, 6, 16, 9, 0, tzinfo=timezone.utc)
    db_session.add_all(
        [
            TimeEntry(
                user_id=test_user.id,
                project_id=project.id,
                start_time=base,
                end_time=base + timedelta(hours=2),
                duration_seconds=2 * 3600,
                description="Project work",
                is_running=False,
            ),
            TimeEntry(
                user_id=test_user.id,
                project_id=None,
                start_time=base + timedelta(hours=3),
                end_time=base + timedelta(hours=9),
                duration_seconds=6 * 3600,
                description="[Meeting] Planning",
                is_running=False,
            ),
        ]
    )
    await db_session.commit()

    service = AIReportingService(db=db_session, ai_client=None, cache_manager=None)

    async def _fake_feature_manager():
        return _EnabledFeatureManager()

    monkeypatch.setattr(service, "_get_feature_manager", _fake_feature_manager)

    result = await service.generate_weekly_summary(user_id=test_user.id, include_ai=False)
    assert result["success"] is True

    summary = result["summary"]
    metrics = summary["metrics"]
    top_projects = metrics["top_projects"]

    meeting_row = next((p for p in top_projects if p.get("project_name") == "Meeting"), None)
    assert meeting_row is not None

    rows_hours_sum = sum(float(p.get("hours", 0)) for p in top_projects)
    assert rows_hours_sum == pytest.approx(float(metrics["total_hours"]), abs=0.01)

    highlights = summary.get("highlights", [])
    most_time_line = next((h for h in highlights if h.startswith("Most time on:")), None)
    assert most_time_line is not None
    assert "Project Alpha" in most_time_line
    assert "Meeting" not in most_time_line


@pytest.mark.asyncio
async def test_weekly_summary_meetings_only_omits_most_time_on_highlight(db_session, monkeypatch, test_user: User):
    await _patch_week_context(monkeypatch)

    company = Company(
        name="Weekly Meetings Only Co",
        slug=f"weekly-meetings-only-{test_user.id}",
        email=f"weekly-meetings-only-{test_user.id}@example.com",
        timezone="UTC",
    )
    db_session.add(company)
    await db_session.flush()
    test_user.company_id = company.id

    base = datetime(2026, 6, 16, 9, 0, tzinfo=timezone.utc)
    db_session.add(
        TimeEntry(
            user_id=test_user.id,
            project_id=None,
            start_time=base,
            end_time=base + timedelta(hours=4),
            duration_seconds=4 * 3600,
            description="[Meeting] All-hands",
            is_running=False,
        )
    )
    await db_session.commit()

    service = AIReportingService(db=db_session, ai_client=None, cache_manager=None)

    async def _fake_feature_manager():
        return _EnabledFeatureManager()

    monkeypatch.setattr(service, "_get_feature_manager", _fake_feature_manager)

    result = await service.generate_weekly_summary(user_id=test_user.id, include_ai=False)
    assert result["success"] is True

    summary = result["summary"]
    metrics = summary["metrics"]
    top_projects = metrics["top_projects"]

    meeting_row = next((p for p in top_projects if p.get("project_name") == "Meeting"), None)
    assert meeting_row is not None

    highlights = summary.get("highlights", [])
    assert not any(h.startswith("Most time on:") for h in highlights)
