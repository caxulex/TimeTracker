from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.utils import tenant_time
from app.models import Company, User
from app.services.auth_service import AuthService


def _freeze_now(monkeypatch: pytest.MonkeyPatch, frozen_utc: datetime) -> None:
    assert frozen_utc.tzinfo is not None
    monkeypatch.setattr(tenant_time, "now_utc", lambda: frozen_utc)


@pytest.mark.asyncio
async def test_resolve_tenant_timezone_returns_company_timezone_when_set(
    db_session: AsyncSession,
):
    company = Company(
        name="Tokyo Co",
        slug=f"tokyo-{uuid.uuid4().hex[:8]}",
        email="tokyo@example.com",
        timezone="Asia/Tokyo",
    )
    db_session.add(company)
    await db_session.commit()

    result = await tenant_time.resolve_tenant_timezone(db_session, company.id)

    assert result == "Asia/Tokyo"


@pytest.mark.asyncio
async def test_resolve_tenant_timezone_falls_back_to_utc_when_company_timezone_none(
    caplog: pytest.LogCaptureFixture,
):
    class _Result:
        def scalar_one_or_none(self):
            return None

    class _StubSession:
        async def execute(self, _statement):
            return _Result()

    caplog.set_level("WARNING")

    result = await tenant_time.resolve_tenant_timezone(_StubSession(), 123)

    assert result == "UTC"
    assert "falling back to UTC" in caplog.text


@pytest.mark.asyncio
async def test_resolve_tenant_timezone_falls_back_to_utc_when_company_missing(
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level("WARNING")

    result = await tenant_time.resolve_tenant_timezone(db_session, 999999)

    assert result == "UTC"
    assert "falling back to UTC" in caplog.text


@pytest.mark.asyncio
async def test_resolve_tenant_timezone_falls_back_to_utc_when_timezone_invalid(
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
):
    company = Company(
        name="Broken TZ Co",
        slug=f"broken-{uuid.uuid4().hex[:8]}",
        email="broken@example.com",
        timezone="Mars/Olympus",
    )
    db_session.add(company)
    await db_session.commit()
    caplog.set_level("WARNING")

    result = await tenant_time.resolve_tenant_timezone(db_session, company.id)

    assert result == "UTC"
    assert "Invalid tenant timezone" in caplog.text


@pytest.mark.asyncio
async def test_resolve_tenant_timezone_for_user_resolves_through_user_company_timezone(
    db_session: AsyncSession,
):
    company = Company(
        name="LA Co",
        slug=f"la-{uuid.uuid4().hex[:8]}",
        email="la@example.com",
        timezone="America/Los_Angeles",
    )
    db_session.add(company)
    await db_session.flush()

    user = User(
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        name="Timezone User",
        password_hash=AuthService.hash_password("pw1234567890"),
        role="regular_user",
        is_active=True,
        company_id=company.id,
    )
    db_session.add(user)
    await db_session.commit()

    result = await tenant_time.resolve_tenant_timezone_for_user(db_session, user.id)

    assert result == "America/Los_Angeles"


@pytest.mark.asyncio
async def test_resolve_tenant_timezone_for_user_falls_back_to_utc_when_user_missing(
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level("WARNING")

    result = await tenant_time.resolve_tenant_timezone_for_user(db_session, 999999)

    assert result == "UTC"
    assert "falling back to UTC" in caplog.text


def test_get_today_in_tz_returns_date_in_given_timezone(monkeypatch: pytest.MonkeyPatch):
    _freeze_now(monkeypatch, datetime(2026, 6, 10, 2, 0, tzinfo=timezone.utc))

    result = tenant_time.get_today_in_tz("Europe/London")

    assert result == date(2026, 6, 10)


def test_get_today_in_tz_with_invalid_tz_falls_back_to_utc_no_crash(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    _freeze_now(monkeypatch, datetime(2026, 6, 10, 2, 0, tzinfo=timezone.utc))
    caplog.set_level("WARNING")

    result = tenant_time.get_today_in_tz("Invalid/Zone")

    assert result == date(2026, 6, 10)
    assert "falling back to UTC" in caplog.text


def test_get_now_in_tz_returns_timezone_aware_datetime(monkeypatch: pytest.MonkeyPatch):
    _freeze_now(monkeypatch, datetime(2026, 6, 10, 2, 0, tzinfo=timezone.utc))

    result = tenant_time.get_now_in_tz("Asia/Tokyo")

    assert result.tzinfo is not None
    assert result.isoformat() == "2026-06-10T11:00:00+09:00"


def test_get_now_in_tz_with_invalid_tz_falls_back_to_utc(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    _freeze_now(monkeypatch, datetime(2026, 6, 10, 2, 0, tzinfo=timezone.utc))
    caplog.set_level("WARNING")

    result = tenant_time.get_now_in_tz("Invalid/Zone")

    assert result.tzinfo is not None
    assert result.utcoffset().total_seconds() == 0
    assert result.isoformat() == "2026-06-10T02:00:00+00:00"
    assert "falling back to UTC" in caplog.text


def test_get_today_in_tz_returns_yesterday_for_los_angeles_when_utc_is_ahead(
    monkeypatch: pytest.MonkeyPatch,
):
    _freeze_now(monkeypatch, datetime(2026, 6, 10, 2, 0, tzinfo=timezone.utc))

    result = tenant_time.get_today_in_tz("America/Los_Angeles")

    assert result == date(2026, 6, 9)


def test_get_today_in_tz_returns_today_for_tokyo_when_utc_is_early(
    monkeypatch: pytest.MonkeyPatch,
):
    _freeze_now(monkeypatch, datetime(2026, 6, 10, 2, 0, tzinfo=timezone.utc))

    result = tenant_time.get_today_in_tz("Asia/Tokyo")

    assert result == date(2026, 6, 10)


@pytest.mark.asyncio
async def test_get_tenant_today_calls_resolve_then_sync_helper(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
):
    seen: dict[str, object] = {}

    async def fake_resolve(db: AsyncSession, company_id: int) -> str:
        seen["db"] = db
        seen["company_id"] = company_id
        return "Asia/Tokyo"

    def fake_get_today(tz: str) -> date:
        seen["tz"] = tz
        return date(2026, 6, 10)

    monkeypatch.setattr(tenant_time, "resolve_tenant_timezone", fake_resolve)
    monkeypatch.setattr(tenant_time, "get_today_in_tz", fake_get_today)

    result = await tenant_time.get_tenant_today(db_session, 42)

    assert result == date(2026, 6, 10)
    assert seen["db"] is db_session
    assert seen["company_id"] == 42
    assert seen["tz"] == "Asia/Tokyo"


@pytest.mark.asyncio
async def test_get_tenant_now_returns_timezone_aware_datetime_in_tenant_zone(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
):
    company = Company(
        name="Now Co",
        slug=f"now-{uuid.uuid4().hex[:8]}",
        email="now@example.com",
        timezone="America/Los_Angeles",
    )
    db_session.add(company)
    await db_session.commit()
    _freeze_now(monkeypatch, datetime(2026, 6, 10, 2, 0, tzinfo=timezone.utc))

    result = await tenant_time.get_tenant_now(db_session, company.id)

    assert result.tzinfo is not None
    assert result.isoformat() == "2026-06-09T19:00:00-07:00"


@pytest.mark.asyncio
async def test_get_tenant_today_for_user_resolves_user_company_timezone_then_today(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
):
    seen: dict[str, object] = {}

    async def fake_resolve(db: AsyncSession, user_id: int) -> str:
        seen["db"] = db
        seen["user_id"] = user_id
        return "America/Los_Angeles"

    def fake_get_today(tz: str) -> date:
        seen["tz"] = tz
        return date(2026, 6, 9)

    monkeypatch.setattr(
        tenant_time,
        "resolve_tenant_timezone_for_user",
        fake_resolve,
    )
    monkeypatch.setattr(tenant_time, "get_today_in_tz", fake_get_today)

    result = await tenant_time.get_tenant_today_for_user(db_session, 7)

    assert result == date(2026, 6, 9)
    assert seen["db"] is db_session
    assert seen["user_id"] == 7
    assert seen["tz"] == "America/Los_Angeles"