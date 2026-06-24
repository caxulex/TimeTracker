from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.ai.services.reporting_service import AIReportingService
from app.models import Company, Project, Team, TimeEntry, User


class _EnabledFeatureManager:
    async def is_enabled(self, _feature: str, _user_id: int) -> bool:
        return True

    async def log_usage(self, **_kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_weekly_summary_uses_tenant_local_week_boundaries(db_session, monkeypatch, test_user: User):
    import app.ai.services.reporting_service as reporting_service_module

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            fixed_now_utc = datetime(2026, 6, 15, 1, 30, tzinfo=timezone.utc)
            if tz is None:
                return fixed_now_utc.replace(tzinfo=None)
            return fixed_now_utc.astimezone(tz)

    monkeypatch.setattr(reporting_service_module, "datetime", _FixedDateTime)

    tenant_tz = "America/New_York"

    # Ensure deterministic tenant-local calendar date for this test.
    monkeypatch.setattr(
        reporting_service_module,
        "local_today",
        lambda _tz: date(2026, 6, 14),
        raising=False,
    )

    async def _fake_resolve_tenant_tz(_db, _user_id):
        return tenant_tz

    monkeypatch.setattr(
        reporting_service_module,
        "resolve_tenant_timezone_for_user",
        _fake_resolve_tenant_tz,
        raising=False,
    )

    company = Company(
        name="Tenant TZ Co",
        slug=f"tenant-tz-{test_user.id}",
        email=f"tenant-tz-{test_user.id}@example.com",
        timezone=tenant_tz,
    )
    db_session.add(company)
    await db_session.flush()

    test_user.company_id = company.id

    team = Team(name="Tenant TZ Team", owner_id=test_user.id, company_id=company.id)
    db_session.add(team)
    await db_session.flush()

    project = Project(name="Tenant TZ Project", team_id=team.id, color="#3B82F6")
    db_session.add(project)
    await db_session.flush()

    ny = ZoneInfo(tenant_tz)

    # Sunday 23:00 local (in the tenant-local week ending Sunday 2026-06-14).
    sunday_local_start = datetime(2026, 6, 14, 23, 0, tzinfo=ny)
    # Monday 00:30 local (belongs to next tenant-local week).
    monday_local_start = datetime(2026, 6, 15, 0, 30, tzinfo=ny)

    db_session.add_all(
        [
            TimeEntry(
                user_id=test_user.id,
                project_id=project.id,
                start_time=sunday_local_start.astimezone(timezone.utc),
                end_time=(sunday_local_start + timedelta(minutes=30)).astimezone(timezone.utc),
                duration_seconds=1800,
                description="sunday-late-local",
                is_running=False,
            ),
            TimeEntry(
                user_id=test_user.id,
                project_id=project.id,
                start_time=monday_local_start.astimezone(timezone.utc),
                end_time=(monday_local_start + timedelta(minutes=30)).astimezone(timezone.utc),
                duration_seconds=1800,
                description="monday-early-local",
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

    # With tenant-local week boundaries and fixed now=2026-06-15 01:30 UTC,
    # local date is still Sunday 2026-06-14 in America/New_York.
    assert summary["period_start"] == "2026-06-08"
    assert summary["period_end"] == "2026-06-14"

    metrics = summary["metrics"]
    # Only the Sunday-late-local entry belongs to this tenant-local week.
    assert metrics["total_hours"] == pytest.approx(0.5, abs=0.01)
    assert metrics["entry_count"] == 1
    assert len(metrics["daily_hours"]) == 1
