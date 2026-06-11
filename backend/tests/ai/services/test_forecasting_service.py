from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.ai.services.forecasting_service import ForecastingService, ProjectBudgetForecast, RiskLevel


class _Result:
    def __init__(self, items=None, scalar_value=None):
        self._items = items or []
        self._scalar_value = scalar_value

    def scalars(self):
        return self

    def all(self):
        return self._items

    def fetchall(self):
        return self._items

    def scalar(self):
        return self._scalar_value

    def scalar_one_or_none(self):
        return self._scalar_value


class _DB:
    def __init__(self, handler):
        self._handler = handler
        self.last_statement = None

    async def execute(self, statement):
        self.last_statement = statement
        return await self._handler(statement)


class _EnabledFeatureManager:
    async def is_enabled(self, _feature: str, _user_id: int) -> bool:
        return True

    async def log_usage(self, **_kwargs) -> None:
        return None


@dataclass
class _User:
    id: int
    name: str
    expected_hours_per_week: int = 40
    company_id: int | None = None
    is_active: bool = True


@dataclass
class _Project:
    id: int
    name: str
    team_id: int = 1
    budget_amount: Decimal | None = Decimal("1000.00")
    deadline: date | None = None
    is_archived: bool = False


@dataclass
class _Entry:
    start_time: datetime
    duration_seconds: int | None = 0


def _service(db) -> ForecastingService:
    return ForecastingService(db=db, cache_manager=None)


@pytest.mark.asyncio
async def test_assess_overtime_risk_uses_tenant_today_for_user_loop(monkeypatch: pytest.MonkeyPatch):
    tenant_today = date(2026, 6, 10)
    captures: dict[str, object] = {}

    async def fake_get_tenant_today(_db, _company_id):
        return tenant_today

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_execute(_statement):
        return _Result(items=[_User(id=7, name="Ava", expected_hours_per_week=40, company_id=1)])

    async def fake_get_user_hours(user_id: int, start_date: date, end_date: date):
        captures["hours"] = (user_id, start_date, end_date)
        return 38.0

    async def fake_get_avg_daily_hours(user_id: int, today: date, days: int = 30):
        captures["avg"] = (user_id, today, days)
        return 2.0

    async def fake_get_user_overtime_hourly_rate(user_id: int, today: date):
        captures["pay_rate"] = (user_id, today)
        return Decimal("30.00"), "ok"

    monkeypatch.setattr("app.ai.services.forecasting_service.get_tenant_today", fake_get_tenant_today)

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_get_user_hours", fake_get_user_hours)
    monkeypatch.setattr(service, "_get_avg_daily_hours", fake_get_avg_daily_hours)
    monkeypatch.setattr(service, "_get_user_overtime_hourly_rate", fake_get_user_overtime_hourly_rate)

    result = await service.assess_overtime_risk(user_id=99, company_id=1)

    assert captures["hours"] == (7, date(2026, 6, 8), tenant_today)
    assert captures["avg"] == (7, tenant_today, 30)
    assert captures["pay_rate"] == (7, tenant_today)
    assert result["enabled"] is True
    assert result["users_assessed"] == 1
    assert result["users_at_risk"] == 1


@pytest.mark.asyncio
async def test_get_user_pay_rate_compares_against_tenant_today(monkeypatch: pytest.MonkeyPatch):
    tenant_today = date(2026, 6, 10)
    seen: dict[str, object] = {}

    class _PayRate:
        base_rate = Decimal("42.00")
        rate_type = "hourly"
        overtime_multiplier = Decimal("1.50")

    async def fake_execute(statement):
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
        seen["compiled"] = compiled
        return _Result(scalar_value=_PayRate())

    service = _service(_DB(fake_execute))

    result, status = await service._get_user_overtime_hourly_rate(user_id=7, today=tenant_today)

    assert status == "ok"
    assert result == Decimal("63.000")
    assert "2026-06-10" in seen["compiled"]


@pytest.mark.asyncio
async def test_analyze_project_budget_no_entries_uses_tenant_today(monkeypatch: pytest.MonkeyPatch):
    tenant_today = date(2026, 6, 10)

    async def fake_execute(_statement):
        return _Result(items=[])

    service = _service(_DB(fake_execute))
    project = _Project(id=1, name="Apollo", deadline=date(2026, 6, 12))

    forecast = await service._analyze_project_budget(project, tenant_today)

    assert forecast is not None
    assert forecast.days_remaining == 2
    assert forecast.projected_completion == date(2026, 6, 12)


@pytest.mark.asyncio
async def test_analyze_project_budget_with_entries_uses_tenant_today_for_burn_and_deadline(monkeypatch: pytest.MonkeyPatch):
    tenant_today = date(2026, 6, 10)

    async def fake_execute(_statement):
        return _Result(items=[_Entry(start_time=datetime(2026, 6, 9, 9, 0), duration_seconds=72000)])

    service = _service(_DB(fake_execute))
    project = _Project(id=2, name="Budget", deadline=date(2026, 6, 15))

    forecast = await service._analyze_project_budget(project, tenant_today)

    assert forecast is not None
    assert forecast.days_remaining == 5
    assert forecast.projected_completion == date(2026, 6, 15)
    assert forecast.risk_level == RiskLevel.CRITICAL


@pytest.mark.asyncio
async def test_analyze_project_budget_without_deadline_uses_tenant_today_for_completion(monkeypatch: pytest.MonkeyPatch):
    tenant_today = date(2026, 6, 10)

    async def fake_execute(_statement):
        return _Result(items=[_Entry(start_time=datetime(2026, 6, 8, 9, 0), duration_seconds=7200)])

    service = _service(_DB(fake_execute))
    project = _Project(id=3, name="NoDeadline", deadline=None)

    forecast = await service._analyze_project_budget(project, tenant_today)

    assert forecast is not None
    assert forecast.days_remaining == 18
    assert forecast.projected_completion == date(2026, 6, 28)


@pytest.mark.asyncio
async def test_forecast_project_budget_threads_tenant_today_into_project_loop(monkeypatch: pytest.MonkeyPatch):
    tenant_today = date(2026, 6, 10)
    captured: dict[str, object] = {}

    async def fake_get_tenant_today(_db, _company_id):
        return tenant_today

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_execute(_statement):
        return _Result(items=[_Project(id=1, name="Apollo", deadline=date(2026, 6, 12))])

    async def fake_analyze(project, today: date):
        captured["args"] = (project.id, today)
        return ProjectBudgetForecast(
            project_id=project.id,
            project_name=project.name,
            budget_total=Decimal("100.00"),
            spent_to_date=Decimal("50.00"),
            projected_total=Decimal("75.00"),
            burn_rate_daily=Decimal("25.00"),
            days_remaining=2,
            projected_completion=today,
            risk_level=RiskLevel.MEDIUM,
            recommendations=[],
        )

    monkeypatch.setattr("app.ai.services.forecasting_service.get_tenant_today", fake_get_tenant_today)

    service = _service(_DB(fake_execute))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_analyze_project_budget", fake_analyze)

    result = await service.forecast_project_budget(user_id=11, company_id=1)

    assert captured["args"] == (1, tenant_today)
    assert result["projects_analyzed"] == 1
    assert result["forecasts"][0]["project_id"] == 1


@pytest.mark.asyncio
async def test_forecast_cash_flow_threads_tenant_today_into_weekly_loop(monkeypatch: pytest.MonkeyPatch):
    tenant_today = date(2026, 6, 10)
    captured: dict[str, object] = {}

    async def fake_get_tenant_today(_db, _company_id):
        return tenant_today

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_history(_period_type: str, limit: int = 6, company_id: int | None = None):
        return [{"gross_amount": 100.0}]

    def fake_get_week_start(today: date):
        captured["today"] = today
        return date(2026, 6, 8)

    monkeypatch.setattr("app.ai.services.forecasting_service.get_tenant_today", fake_get_tenant_today)

    service = _service(_DB(lambda _statement: _Result(items=[])))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_get_payroll_history", fake_history)
    monkeypatch.setattr(service, "_get_week_start", fake_get_week_start)

    result = await service.forecast_cash_flow(user_id=22, company_id=1)

    assert captured["today"] == tenant_today
    assert result["forecast"][0]["week_start"] == "2026-06-08"


@pytest.mark.asyncio
async def test_forecast_payroll_resolves_tenant_today_once(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, int] = {"calls": 0}

    async def fake_get_tenant_today_for_user(_db, _user_id):
        seen["calls"] += 1
        return date(2026, 6, 10)

    async def fake_feature_manager():
        return _EnabledFeatureManager()

    async def fake_history(_period_type: str, limit: int = 12, company_id: int | None = None):
        return [
            {"period_end": date(2026, 6, 7), "regular_hours": 40.0, "overtime_hours": 5.0, "gross_amount": 1000.0},
            {"period_end": date(2026, 6, 14), "regular_hours": 40.0, "overtime_hours": 5.0, "gross_amount": 1100.0},
            {"period_end": date(2026, 6, 21), "regular_hours": 40.0, "overtime_hours": 5.0, "gross_amount": 1200.0},
        ]

    async def fake_generate(*_args, **_kwargs):
        return ProjectBudgetForecast(
            project_id=1,
            project_name="x",
            budget_total=Decimal("1.00"),
            spent_to_date=Decimal("1.00"),
            projected_total=Decimal("1.00"),
            burn_rate_daily=Decimal("1.00"),
            days_remaining=1,
            projected_completion=date(2026, 6, 10),
            risk_level=RiskLevel.LOW,
            recommendations=[],
        )

    monkeypatch.setattr("app.ai.services.forecasting_service.get_tenant_today_for_user", fake_get_tenant_today_for_user)

    service = _service(_DB(lambda _statement: _Result(items=[])))
    monkeypatch.setattr(service, "_get_feature_manager", fake_feature_manager)
    monkeypatch.setattr(service, "_get_payroll_history", fake_history)
    monkeypatch.setattr(service, "_generate_payroll_forecast", fake_generate)

    result = await service.forecast_payroll(user_id=3)

    assert seen["calls"] == 1
    assert result["enabled"] is True

@pytest.mark.asyncio
async def test_get_user_overtime_hourly_rate_returns_missing_status_when_no_pay_rate():
    db = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    service = ForecastingService(db=db)

    rate, status = await service._get_user_overtime_hourly_rate(user_id=1, today=date(2026, 6, 10))

    assert rate is None
    assert status == "missing_pay_rate"


@pytest.mark.asyncio
async def test_get_user_overtime_hourly_rate_normalizes_monthly_and_applies_multiplier():
    db = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = SimpleNamespace(
        base_rate=Decimal("1200.00"),
        rate_type="monthly",
        overtime_multiplier=Decimal("1.5"),
    )
    db.execute.return_value = result

    service = ForecastingService(db=db)

    rate, status = await service._get_user_overtime_hourly_rate(user_id=1, today=date(2026, 6, 10))

    assert status == "ok"
    assert rate is not None
    assert rate.quantize(Decimal("0.01")) == Decimal("10.38")


@pytest.mark.asyncio
async def test_get_user_overtime_hourly_rate_returns_unsupported_status_for_project_based():
    db = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = SimpleNamespace(
        base_rate=Decimal("500.00"),
        rate_type="project_based",
        overtime_multiplier=Decimal("1.5"),
    )
    db.execute.return_value = result

    service = ForecastingService(db=db)

    rate, status = await service._get_user_overtime_hourly_rate(user_id=1, today=date(2026, 6, 10))

    assert rate is None
    assert status == "unsupported_rate_type"
