from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.ai.services.ml_anomaly_service import MLAnomalyService


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _EntriesResult:
    def __init__(self, entries):
        self._entries = entries

    def scalars(self):
        return self

    def all(self):
        return self._entries


class _DB:
    def __init__(self, user, entries):
        self._user = user
        self._entries = entries
        self._calls = 0

    async def execute(self, _statement):
        self._calls += 1
        if self._calls == 1:
            return _ScalarResult(self._user)
        return _EntriesResult(self._entries)


@dataclass
class _User:
    id: int
    name: str
    company_id: int | None = None


def _make_entry(base_now: datetime, days_ago: int, start_hour: int, duration_hours: float, end_hour: int | None = None):
    start = (base_now - timedelta(days=days_ago)).replace(
        hour=start_hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    if end_hour is not None:
        end = start.replace(hour=end_hour)
    else:
        end = start + timedelta(hours=duration_hours)
    return SimpleNamespace(
        start_time=start,
        end_time=end,
        duration_seconds=int(duration_hours * 3600),
        is_running=False,
    )


@pytest.fixture
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    base_now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.ai.services.ml_anomaly_service.now_utc", lambda: base_now)
    return base_now


async def _assess(entries, fixed_now: datetime):
    user = _User(id=1, name="Burnout Test User")
    db = _DB(user=user, entries=entries)
    service = MLAnomalyService(db=db, cache_manager=None)
    return await service.assess_burnout_risk(user_id=1, period_days=30)


@pytest.mark.asyncio
@pytest.mark.parametrize("work_days", [0, 1, 2])
async def test_burnout_flags_insufficient_data_below_threshold(work_days: int, fixed_now: datetime):
    entries = [
        _make_entry(fixed_now, days_ago=day, start_hour=9, duration_hours=8)
        for day in range(1, work_days + 1)
    ]

    assessment = await _assess(entries, fixed_now)

    assert assessment.insufficient_data is True
    assert assessment.min_work_days_threshold == 3
    assert assessment.risk_level is None
    assert assessment.risk_score is None
    assert assessment.trend is None
    assert assessment.recommendations == [
        "Log at least 3 working days to receive a burnout assessment"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("work_days", [3, 6])
async def test_burnout_runs_full_assessment_at_or_above_threshold(work_days: int, fixed_now: datetime):
    entries = [
        _make_entry(fixed_now, days_ago=day, start_hour=9, duration_hours=8)
        for day in range(1, work_days + 1)
    ]

    assessment = await _assess(entries, fixed_now)

    assert assessment.insufficient_data is False
    assert assessment.min_work_days_threshold == 3
    assert assessment.risk_level is not None
    assert assessment.risk_score is not None


@pytest.mark.asyncio
async def test_burnout_risk_level_low_with_sufficient_data(fixed_now: datetime):
    entries = [
        _make_entry(fixed_now, days_ago=3, start_hour=9, duration_hours=8),
        _make_entry(fixed_now, days_ago=4, start_hour=9, duration_hours=8),
        _make_entry(fixed_now, days_ago=5, start_hour=9, duration_hours=8),
    ]

    assessment = await _assess(entries, fixed_now)

    assert assessment.insufficient_data is False
    assert assessment.risk_level.value == "low"


@pytest.mark.asyncio
async def test_burnout_risk_level_moderate_with_sufficient_data(fixed_now: datetime):
    entries = [
        _make_entry(fixed_now, days_ago=3, start_hour=9, duration_hours=10),
        _make_entry(fixed_now, days_ago=4, start_hour=9, duration_hours=10),
        _make_entry(fixed_now, days_ago=5, start_hour=9, duration_hours=10),
    ]

    assessment = await _assess(entries, fixed_now)

    assert assessment.insufficient_data is False
    assert assessment.risk_level.value == "moderate"


@pytest.mark.asyncio
async def test_burnout_risk_level_high_with_sufficient_data(fixed_now: datetime):
    entries = [
        _make_entry(fixed_now, days_ago=3, start_hour=9, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=3, start_hour=12, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=3, start_hour=15, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=3, start_hour=18, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=4, start_hour=9, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=4, start_hour=12, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=4, start_hour=15, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=4, start_hour=18, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=5, start_hour=9, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=5, start_hour=12, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=5, start_hour=15, duration_hours=3, end_hour=21),
        _make_entry(fixed_now, days_ago=5, start_hour=18, duration_hours=3, end_hour=21),
    ]

    assessment = await _assess(entries, fixed_now)

    assert assessment.insufficient_data is False
    assert assessment.risk_level.value == "high"


@pytest.mark.asyncio
async def test_burnout_risk_level_critical_with_sufficient_data(fixed_now: datetime):
    # Fixed now is Monday (2026-06-15), so offsets 1/2/8/9 are weekend days.
    entries = [
        _make_entry(fixed_now, days_ago=1, start_hour=9, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=1, start_hour=13, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=1, start_hour=17, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=2, start_hour=9, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=2, start_hour=13, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=2, start_hour=17, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=8, start_hour=9, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=8, start_hour=13, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=8, start_hour=17, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=9, start_hour=9, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=9, start_hour=13, duration_hours=4, end_hour=21),
        _make_entry(fixed_now, days_ago=9, start_hour=17, duration_hours=4, end_hour=21),
    ]

    assessment = await _assess(entries, fixed_now)

    assert assessment.insufficient_data is False
    assert assessment.risk_level.value == "critical"
