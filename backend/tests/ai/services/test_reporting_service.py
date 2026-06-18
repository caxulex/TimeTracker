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
@pytest.mark.skip(reason="Phase 2e removed module-level tenant timezone helper patch points; coverage moved to integration-level weekly summary behavior")
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
@pytest.mark.skip(reason="Phase 2e removed module-level tenant timezone helper patch points; coverage moved to integration-level weekly summary behavior")
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
@pytest.mark.skip(reason="Phase 2e removed module-level tenant timezone helper patch points; coverage moved to integration-level weekly summary behavior")
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

    async def fake_project_metrics(*_args):
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


@pytest.mark.asyncio
async def test_generate_project_health_marks_sparse_projects_as_insufficient_data(monkeypatch: pytest.MonkeyPatch):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=77, name="Aloha"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(*_args):
        return {
            "total_hours": 1.1,
            "this_week_hours": 1.1,
            "last_week_hours": 0,
            "activity_trend": "new",
            "total_tasks": 0,
            "completed_tasks": 0,
            "task_completion_rate": 0,
            "contributor_count": 1,
            "activity_days": 1,
        }

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=77)

    assert result["success"] is True
    assert result["insufficient_data"] is True
    assert result["health_score"] is None
    assert result["health_status"] is None
    assert result["data_thresholds"] == {"min_hours": 2, "min_tasks": 5}
    assert result["recommendations"] == [
        "Need at least 2 hours of logged work OR 5 defined tasks to provide a health assessment."
    ]
    assert result["insights"][0]["description"] == "Project doesn't have enough activity yet to assess."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metrics", "expected_insufficient"),
    [
        (
            {
                "total_hours": 1.1,
                "this_week_hours": 1.1,
                "last_week_hours": 0,
                "activity_trend": "new",
                "total_tasks": 0,
                "completed_tasks": 0,
                "task_completion_rate": 0,
                "contributor_count": 1,
                "days_with_activity": 4,
            },
            True,
        ),
        (
            {
                "total_hours": 1.9,
                "this_week_hours": 4.9,
                "last_week_hours": 0,
                "activity_trend": "new",
                "total_tasks": 4,
                "completed_tasks": 0,
                "task_completion_rate": 0,
                "contributor_count": 1,
                "days_with_activity": 10,
            },
            True,
        ),
        (
            {
                "total_hours": 0,
                "this_week_hours": 0,
                "last_week_hours": 0,
                "activity_trend": "new",
                "total_tasks": 0,
                "completed_tasks": 0,
                "task_completion_rate": 0,
                "contributor_count": 0,
                "days_with_activity": 0,
            },
            True,
        ),
        (
            {
                "total_hours": 2.0,
                "this_week_hours": 5.0,
                "last_week_hours": 0,
                "activity_trend": "new",
                "total_tasks": 0,
                "completed_tasks": 0,
                "task_completion_rate": 0,
                "contributor_count": 0,
                "days_with_activity": 0,
            },
            False,
        ),
        (
            {
                "total_hours": 0,
                "this_week_hours": 0,
                "last_week_hours": 0,
                "activity_trend": "new",
                "total_tasks": 5,
                "completed_tasks": 0,
                "task_completion_rate": 0,
                "contributor_count": 0,
                "days_with_activity": 0,
            },
            False,
        ),
        (
            {
                "total_hours": 100,
                "this_week_hours": 20,
                "last_week_hours": 80,
                "activity_trend": "stable",
                "total_tasks": 10,
                "completed_tasks": 6,
                "task_completion_rate": 0.6,
                "contributor_count": 6,
                "days_with_activity": 30,
            },
            False,
        ),
        (
            {
                "total_hours": 6,
                "this_week_hours": 6,
                "last_week_hours": 0,
                "activity_trend": "increasing",
                "total_tasks": 6,
                "completed_tasks": 2,
                "task_completion_rate": 0.33,
                "contributor_count": 2,
                "days_with_activity": 2,
            },
            False,
        ),
    ],
)
async def test_generate_project_health_threshold_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    metrics: dict,
    expected_insufficient: bool,
):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=77, name="Boundary Project"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(*_args):
        return metrics

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=77)

    assert result["insufficient_data"] is expected_insufficient
    if expected_insufficient:
        assert result["health_score"] is None
        assert result["health_status"] is None
    else:
        assert isinstance(result["health_score"], int)
        assert result["health_status"] in {"healthy", "moderate", "at_risk", "critical"}


@pytest.mark.asyncio
async def test_aloha_like_sparse_data(monkeypatch: pytest.MonkeyPatch):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=128, name="Aloha"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(*_args):
        return {
            "total_hours": 1.1,
            "this_week_hours": 1.1,
            "last_week_hours": 0,
            "activity_trend": "new",
            "total_tasks": 0,
            "completed_tasks": 0,
            "task_completion_rate": 0,
            "contributor_count": 1,
            "days_with_activity": 4,
        }

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=128)

    assert result["insufficient_data"] is True


@pytest.mark.asyncio
async def test_just_meets_hours_threshold(monkeypatch: pytest.MonkeyPatch):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=77, name="Hours Boundary"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(*_args):
        return {
            "total_hours": 2.0,
            "this_week_hours": 5.0,
            "last_week_hours": 0,
            "activity_trend": "new",
            "total_tasks": 0,
            "completed_tasks": 0,
            "task_completion_rate": 0,
            "contributor_count": 1,
            "days_with_activity": 0,
        }

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=77)

    assert result["insufficient_data"] is False


@pytest.mark.asyncio
async def test_just_meets_tasks_threshold(monkeypatch: pytest.MonkeyPatch):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=77, name="Tasks Boundary"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(*_args):
        return {
            "total_hours": 0.0,
            "this_week_hours": 0.0,
            "last_week_hours": 0,
            "activity_trend": "new",
            "total_tasks": 5,
            "completed_tasks": 0,
            "task_completion_rate": 0,
            "contributor_count": 1,
            "days_with_activity": 0,
        }

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=77)

    assert result["insufficient_data"] is False


@pytest.mark.asyncio
async def test_days_only_no_longer_counts_as_sufficient(monkeypatch: pytest.MonkeyPatch):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=77, name="Days Boundary"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(*_args):
        return {
            "total_hours": 0.0,
            "this_week_hours": 0.0,
            "last_week_hours": 0,
            "activity_trend": "new",
            "total_tasks": 0,
            "completed_tasks": 0,
            "task_completion_rate": 0,
            "contributor_count": 1,
            "days_with_activity": 3,
        }

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=77)

    assert result["insufficient_data"] is True


@pytest.mark.asyncio
async def test_none_meet_threshold(monkeypatch: pytest.MonkeyPatch):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=77, name="None Meet"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(*_args):
        return {
            "total_hours": 1.9,
            "this_week_hours": 4.9,
            "last_week_hours": 0,
            "activity_trend": "new",
            "total_tasks": 4,
            "completed_tasks": 0,
            "task_completion_rate": 0,
            "contributor_count": 1,
            "days_with_activity": 10,
        }

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=77)

    assert result["insufficient_data"] is True


@pytest.mark.asyncio
async def test_project_health_no_tasks_skips_completion_penalty_and_low_completion_insight(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=77, name="No Tasks Active"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(*_args):
        return {
            "total_hours": 12.0,
            "this_week_hours": 4.0,
            "last_week_hours": 6.0,
            "activity_trend": "decreasing",
            "total_tasks": 0,
            "completed_tasks": 0,
            "task_completion_rate": 0,
            "completion_measured": False,
            "contributor_count": 1,
            "days_with_activity": 5,
        }

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=77)

    assert result["insufficient_data"] is False
    assert result["metrics"]["completion_measured"] is False
    assert result["health_score"] == 75
    descriptions = [insight["description"] for insight in result["insights"]]
    assert "Only 0% of tasks completed" not in descriptions
    action_items = [item for insight in result["insights"] for item in insight.get("action_items") or []]
    assert "Review blocked tasks" not in action_items
    assert "Reassess task priorities" not in action_items


@pytest.mark.asyncio
async def test_project_health_zero_done_with_measured_completion_keeps_penalty_and_actions(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=77, name="Measured Zero Done"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(*_args):
        return {
            "total_hours": 18.0,
            "this_week_hours": 9.0,
            "last_week_hours": 9.0,
            "activity_trend": "stable",
            "total_tasks": 10,
            "completed_tasks": 0,
            "task_completion_rate": 0,
            "completion_measured": True,
            "contributor_count": 2,
            "days_with_activity": 7,
        }

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=77)

    assert result["insufficient_data"] is False
    assert result["metrics"]["completion_measured"] is True
    assert result["health_score"] == 80
    low_completion_insight = next(
        insight for insight in result["insights"] if insight["title"] == "Low Task Completion"
    )
    assert low_completion_insight["description"] == "Only 0% of tasks completed"
    assert "Review blocked tasks" in low_completion_insight["action_items"]
    assert "Reassess task priorities" in low_completion_insight["action_items"]


@pytest.mark.asyncio
async def test_project_health_partial_done_keeps_existing_scoring(monkeypatch: pytest.MonkeyPatch):
    async def fake_execute(_statement):
        return _Result(scalar_value=SimpleNamespace(id=77, name="Partial Done"))

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_project_metrics(*_args):
        return {
            "total_hours": 24.0,
            "this_week_hours": 12.0,
            "last_week_hours": 12.0,
            "activity_trend": "stable",
            "total_tasks": 10,
            "completed_tasks": 5,
            "task_completion_rate": 0.5,
            "completion_measured": True,
            "contributor_count": 2,
            "days_with_activity": 9,
        }

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_gather_project_metrics", fake_project_metrics)

    result = await service.generate_project_health(user_id=11, project_id=77)

    assert result["insufficient_data"] is False
    assert result["health_score"] == 100
    assert all(insight["title"] != "Low Task Completion" for insight in result["insights"])

