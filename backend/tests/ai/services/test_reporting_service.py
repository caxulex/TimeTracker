from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.ai.services.reporting_service import AIReportingService
from app.utils.timewindow import range_bounds


class _Result:
    def __init__(self, *, scalar_value=None, row=None):
        self._scalar_value = scalar_value
        self._row = row

    def scalar(self):
        return self._scalar_value

    def scalar_one_or_none(self):
        return self._scalar_value

    def fetchone(self):
        return self._row


class _DB:
    def __init__(self, handler):
        self._handler = handler
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return await self._handler(statement)


@dataclass
class _User:
    id: int
    name: str
    expected_hours_per_week: int = 40


class _EnabledFeatureManager:
    async def is_enabled(self, _feature: str, _user_id: int) -> bool:
        return True

    async def log_usage(self, **_kwargs) -> None:
        return None


def _service(db) -> AIReportingService:
    return AIReportingService(db=db, ai_client=None, cache_manager=None)


@pytest.mark.asyncio
async def test_gather_project_metrics_uses_tenant_week_boundaries(monkeypatch: pytest.MonkeyPatch):
    tenant_today = date(2026, 6, 10)
    tenant_tz = "America/Los_Angeles"
    expected_week_start = tenant_today - timedelta(days=tenant_today.weekday())
    expected_week_end = expected_week_start + timedelta(days=6)
    expected_start_dt, _ = range_bounds(expected_week_start, expected_week_end, tenant_tz)

    captured = {"this_week_sql": ""}
    call_index = {"i": 0}

    async def fake_execute(statement):
        call_index["i"] += 1
        if call_index["i"] == 2:
            captured["this_week_sql"] = str(statement.compile(compile_kwargs={"literal_binds": True}))
        if call_index["i"] == 4:
            row = SimpleNamespace(total=0, completed=0)
            return _Result(row=row)
        return _Result(scalar_value=0)

    async def fake_resolve_tz(_db, _user_id):
        return tenant_tz

    async def fake_tenant_today(_db, _user_id):
        return tenant_today

    monkeypatch.setattr("app.ai.services.reporting_service.resolve_tenant_timezone_for_user", fake_resolve_tz)
    monkeypatch.setattr("app.ai.services.reporting_service.get_tenant_today_for_user", fake_tenant_today)

    service = _service(_DB(fake_execute))
    await service._gather_project_metrics(project_id=77, user_id=11)

    assert expected_start_dt.strftime("%Y-%m-%d %H:%M:%S") in captured["this_week_sql"]


@pytest.mark.asyncio
async def test_gather_user_metrics_uses_tenant_30_day_window(monkeypatch: pytest.MonkeyPatch):
    tenant_today = date(2026, 6, 10)
    tenant_tz = "America/Los_Angeles"
    thirty_days_ago = tenant_today - timedelta(days=30)
    expected_start_dt, expected_end_dt = range_bounds(thirty_days_ago, tenant_today, tenant_tz)

    captured = {"hours_sql": ""}
    call_index = {"i": 0}

    async def fake_execute(statement):
        call_index["i"] += 1
        if call_index["i"] == 2:
            captured["hours_sql"] = str(statement.compile(compile_kwargs={"literal_binds": True}))
            return _Result(scalar_value=0)
        if call_index["i"] == 1:
            return _Result(scalar_value=_User(id=5, name="Ava"))
        return _Result(scalar_value=0)

    async def fake_resolve_tz(_db, _user_id):
        return tenant_tz

    async def fake_tenant_today(_db, _user_id):
        return tenant_today

    monkeypatch.setattr("app.ai.services.reporting_service.resolve_tenant_timezone_for_user", fake_resolve_tz)
    monkeypatch.setattr("app.ai.services.reporting_service.get_tenant_today_for_user", fake_tenant_today)

    service = _service(_DB(fake_execute))
    await service._gather_user_metrics(user_id=5)

    sql = captured["hours_sql"]
    assert expected_start_dt.strftime("%Y-%m-%d %H:%M:%S") in sql
    assert expected_end_dt.strftime("%Y-%m-%d %H:%M:%S") in sql


@pytest.mark.asyncio
async def test_generate_weekly_summary_uses_shared_timezone_helper(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    async def fake_resolve_tz(_db, _user_id):
        return "America/Bogota"

    def fake_local_today(tz: str):
        captured["tz"] = tz
        return date(2026, 6, 10)

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_weekly_metrics(_user_id, week_start, week_end, _team_id, tz, reference_now_utc):
        captured["metrics_tz"] = tz
        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "total_hours": 0,
            "hours_change_pct": 0,
            "projects_count": 0,
            "top_projects": [],
            "daily_hours": [],
            "avg_daily_hours": 0,
            "max_daily_hours": 0,
            "min_daily_hours": 0,
            "tasks_completed": 0,
            "entry_count": 0,
            "trend": "stable",
            "comparison_label": "vs Last Week",
            "comparison_suffix": "vs last week",
            "comparison_range_label": "full week",
            "comparison_is_week_complete": True,
        }

    async def fake_generate_insights(*_args, **_kwargs):
        return []

    monkeypatch.setattr("app.ai.services.reporting_service.resolve_tenant_timezone_for_user", fake_resolve_tz)
    monkeypatch.setattr("app.ai.services.reporting_service.local_today", fake_local_today)

    async def fake_execute(_statement):
        return _Result(scalar_value=None)

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_weekly_metrics", fake_weekly_metrics)
    monkeypatch.setattr(service, "_generate_insights", fake_generate_insights)

    result = await service.generate_weekly_summary(user_id=99, include_ai=False)

    assert not hasattr(service, "_resolve_tenant_timezone")
    assert captured["tz"] == "America/Bogota"
    assert captured["metrics_tz"] == "America/Bogota"
    assert result["success"] is True


@pytest.mark.asyncio
async def test_generate_project_health_returns_flat_response_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=77, name="Apollo"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(_project_id, _user_id):
        return {
            "total_hours": 140.0,
            "this_week_hours": 28.0,
            "last_week_hours": 32.0,
            "activity_trend": "decreasing",
            "total_tasks": 20,
            "completed_tasks": 15,
            "task_completion_rate": 0.75,
            "contributor_count": 3,
        }

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=77)

    assert result["success"] is True
    assert result["project_id"] == 77
    assert result["project_name"] == "Apollo"
    assert isinstance(result["health_score"], int)
    assert result["health_status"] in {"healthy", "moderate", "at_risk", "critical"}
    assert result["metrics"]["task_completion_rate"] == 0.75
    assert isinstance(result["insights"], list)
    assert "generated_at" in result
    assert "health" not in result
