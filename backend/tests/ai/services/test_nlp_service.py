from __future__ import annotations

from datetime import date, datetime

import pytest

from app.ai.services.nlp_service import NLPService


class _EnabledFeatureManager:
    async def is_enabled(self, _feature: str, _user_id: int) -> bool:
        return True

    async def log_usage(self, **_kwargs) -> None:
        return None


class _StubAIClient:
    def __init__(self) -> None:
        self.last_user_prompt: str | None = None

    async def generate(self, **kwargs):
        self.last_user_prompt = kwargs.get("user_prompt")
        return {
            "data": {"raw_text": '{"duration_hours": null, "duration_minutes": null, "project_name": null, "description": "captured", "date": null}'},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }


def _service_with_mocks(monkeypatch: pytest.MonkeyPatch, ai_client=None) -> NLPService:
    service = NLPService(db=object(), ai_client=ai_client)

    async def _feature_manager():
        return _EnabledFeatureManager()

    async def _projects(_user_id: int):
        return []

    async def _tasks(_user_id: int):
        return []

    monkeypatch.setattr(service, "_get_feature_manager", _feature_manager)
    monkeypatch.setattr(service, "_get_user_projects", _projects)
    monkeypatch.setattr(service, "_get_user_tasks", _tasks)
    return service


def test_date_keywords_require_today_argument():
    with pytest.raises(TypeError):
        NLPService.DATE_KEYWORDS["today"]()


def test_date_keywords_resolve_with_provided_today():
    base_today = date(2026, 6, 10)

    assert NLPService.DATE_KEYWORDS["today"](base_today) == date(2026, 6, 10)
    assert NLPService.DATE_KEYWORDS["yesterday"](base_today) == date(2026, 6, 9)
    assert NLPService.DATE_KEYWORDS["tomorrow"](base_today) == date(2026, 6, 11)
    assert NLPService.DATE_KEYWORDS["last week"](base_today) == date(2026, 6, 3)
    assert NLPService.DATE_KEYWORDS["this morning"](base_today) == date(2026, 6, 10)
    assert NLPService.DATE_KEYWORDS["this afternoon"](base_today) == date(2026, 6, 10)
    assert NLPService.DATE_KEYWORDS["this evening"](base_today) == date(2026, 6, 10)


def test_parse_date_yesterday_uses_tenant_boundary_not_utc():
    service = NLPService(db=object(), ai_client=None)

    parsed = service._parse_date(
        "worked yesterday",
        tenant_today=date(2026, 6, 9),
    )

    assert parsed is not None
    assert parsed.date == date(2026, 6, 8)


def test_parse_date_today_can_be_tomorrow_in_utc_for_tokyo():
    service = NLPService(db=object(), ai_client=None)

    parsed = service._parse_date(
        "today",
        tenant_today=date(2026, 6, 11),
    )

    assert parsed is not None
    assert parsed.date == date(2026, 6, 11)


def test_parse_date_last_week_anchors_to_tenant_today():
    service = NLPService(db=object(), ai_client=None)

    parsed = service._parse_date(
        "last week",
        tenant_today=date(2026, 6, 10),
    )

    assert parsed is not None
    assert parsed.date == date(2026, 6, 3)


def test_parse_date_relative_weekday_uses_tenant_week_anchor():
    service = NLPService(db=object(), ai_client=None)

    parsed = service._parse_date(
        "worked monday",
        tenant_today=date(2026, 6, 10),
    )

    assert parsed is not None
    assert parsed.date == date(2026, 6, 8)


def test_parse_date_ignores_dateutil_default_today_using_tenant_today(monkeypatch: pytest.MonkeyPatch):
    service = NLPService(db=object(), ai_client=None)
    tenant_today = date(2026, 6, 9)

    def _fake_parse(*_args, **_kwargs):
        return datetime(2026, 6, 9, 12, 0)

    monkeypatch.setattr("app.ai.services.nlp_service.date_parser.parse", _fake_parse)

    parsed = service._parse_date("did docs", tenant_today=tenant_today)

    assert parsed is None


@pytest.mark.asyncio
async def test_parse_time_entry_fallback_defaults_to_tenant_today(monkeypatch: pytest.MonkeyPatch):
    service = _service_with_mocks(monkeypatch, ai_client=None)

    async def _tenant_today(_db, _user_id: int):
        return date(2026, 6, 9)

    monkeypatch.setattr("app.ai.services.nlp_service.get_tenant_today_for_user", _tenant_today)
    monkeypatch.setattr(service, "_parse_date", lambda _text, _timezone="UTC", tenant_today=None: None)

    result = await service.parse_time_entry(
        text="did planning",
        user_id=7,
        use_ai=False,
    )

    assert result["success"] is True
    assert result["result"]["start_time"].startswith("2026-06-09T00:00:00")


@pytest.mark.asyncio
async def test_ai_prompt_uses_tenant_local_date_from_helper(monkeypatch: pytest.MonkeyPatch):
    ai_client = _StubAIClient()
    service = _service_with_mocks(monkeypatch, ai_client=ai_client)

    async def _tenant_today(_db, _user_id: int):
        return date(2026, 6, 11)

    monkeypatch.setattr("app.ai.services.nlp_service.get_tenant_today_for_user", _tenant_today)

    result = await service.parse_time_entry(
        text="log work",
        user_id=5,
        use_ai=True,
    )

    assert result["success"] is True
    assert ai_client.last_user_prompt is not None
    assert "relative to today: 2026-06-11" in ai_client.last_user_prompt
