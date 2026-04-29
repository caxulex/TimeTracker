"""Tests for B86 / Prompt 8.6 — per-company overtime configuration.

Covers three scopes:

1. ``CompanyUpdate`` schema validation (threshold/multiplier bounds).
2. ``group_hours_by_workweek`` pure helper.
3. ``PayrollPeriodService.process_period`` end-to-end:
   - Regression: ``overtime_enabled=False`` matches legacy per-period behavior.
   - FLSA path: ``overtime_enabled=True`` applies per-workweek overtime.
   - C3 timezone fix: pay-period boundaries respect company timezone.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models import (
    Company,
    PayRate,
    PayrollEntry,
    PayrollPeriod,
    TimeEntry,
    User,
)
from app.routers.companies import CompanyUpdate
from app.services.auth_service import AuthService
from app.services.payroll_service import (
    PayrollPeriodService,
    group_hours_by_workweek,
)
from sqlalchemy import select


# ============================================================================
# 1. CompanyUpdate schema validation
# ============================================================================

class TestCompanyUpdateOvertimeValidation:
    def test_valid_full_update(self):
        m = CompanyUpdate(
            overtime_enabled=True,
            overtime_threshold_hours_per_week=Decimal("40"),
            overtime_multiplier=Decimal("1.5"),
        )
        assert m.overtime_enabled is True
        assert m.overtime_threshold_hours_per_week == Decimal("40")
        assert m.overtime_multiplier == Decimal("1.5")

    @pytest.mark.parametrize("threshold", ["0", "-1", "200"])
    def test_threshold_invalid(self, threshold):
        with pytest.raises(ValidationError):
            CompanyUpdate(overtime_threshold_hours_per_week=Decimal(threshold))

    @pytest.mark.parametrize("threshold", ["0.01", "40", "168"])
    def test_threshold_boundary_accepts(self, threshold):
        m = CompanyUpdate(overtime_threshold_hours_per_week=Decimal(threshold))
        assert m.overtime_threshold_hours_per_week == Decimal(threshold)

    @pytest.mark.parametrize("multiplier", ["0.5", "0", "4.0", "3.01"])
    def test_multiplier_invalid(self, multiplier):
        with pytest.raises(ValidationError):
            CompanyUpdate(overtime_multiplier=Decimal(multiplier))

    @pytest.mark.parametrize("multiplier", ["1.0", "1.5", "2.0", "3.0"])
    def test_multiplier_boundary_accepts(self, multiplier):
        m = CompanyUpdate(overtime_multiplier=Decimal(multiplier))
        assert m.overtime_multiplier == Decimal(multiplier)


# ============================================================================
# 2. group_hours_by_workweek pure unit tests
# ============================================================================

def _fake_entry(start_utc: datetime, hours: float) -> SimpleNamespace:
    """Build a duck-typed object that satisfies the helper's attribute access."""
    return SimpleNamespace(
        start_time=start_utc,
        duration_seconds=int(hours * 3600),
    )


class TestGroupHoursByWorkweek:
    def test_single_week_aggregates(self):
        # Wednesday + Thursday in same ISO week (Mon=2026-01-05)
        e1 = _fake_entry(datetime(2026, 1, 7, 14, 0, tzinfo=timezone.utc), 5)
        e2 = _fake_entry(datetime(2026, 1, 8, 14, 0, tzinfo=timezone.utc), 3)
        out = group_hours_by_workweek([e1, e2], "UTC")
        assert out == {date(2026, 1, 5): Decimal("8")}

    def test_two_weeks_split(self):
        e1 = _fake_entry(datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc), 4)
        e2 = _fake_entry(datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc), 6)
        out = group_hours_by_workweek([e1, e2], "UTC")
        assert out[date(2026, 1, 5)] == Decimal("4")
        assert out[date(2026, 1, 12)] == Decimal("6")

    def test_local_tz_shifts_week(self):
        # Sunday 23:00 LA local = Monday 06:00 UTC the next day -> week starts
        # at LA-local Monday because we group in LA tz.
        # 2026-01-04 (Sun) 23:00 LA = 2026-01-05 07:00 UTC -> still Sun in LA
        # which belongs to ISO week starting Mon 2025-12-29.
        e = _fake_entry(datetime(2026, 1, 5, 7, 0, tzinfo=timezone.utc), 1)
        out = group_hours_by_workweek([e], "America/Los_Angeles")
        # Sunday 2026-01-04 in LA -> Monday-anchor 2025-12-29
        assert out == {date(2025, 12, 29): Decimal("1")}

    def test_naive_start_treated_as_utc(self):
        e = _fake_entry(datetime(2026, 1, 7, 14, 0), 2)  # naive
        out = group_hours_by_workweek([e], "UTC")
        assert out == {date(2026, 1, 5): Decimal("2")}

    def test_skips_running_or_null_duration(self):
        e = _fake_entry(datetime(2026, 1, 7, 14, 0, tzinfo=timezone.utc), 2)
        e_null = SimpleNamespace(
            start_time=datetime(2026, 1, 7, 14, 0, tzinfo=timezone.utc),
            duration_seconds=None,
        )
        out = group_hours_by_workweek([e, e_null], "UTC")
        assert out == {date(2026, 1, 5): Decimal("2")}


# ============================================================================
# 3. process_period integration tests
# ============================================================================

@pytest.fixture
def hourly_setup():
    """Factory that creates a company + worker + active hourly pay rate."""

    async def _make(
        db_session,
        *,
        timezone_name: str = "UTC",
        overtime_enabled: bool = False,
        threshold: Decimal = Decimal("40.00"),
        multiplier: Decimal = Decimal("1.50"),
        rate_pay_multiplier: Decimal = Decimal("1.50"),  # legacy per-rate field
        base_rate: Decimal = Decimal("20.00"),
    ):
        slug = uuid.uuid4().hex[:8]
        company = Company(
            name=f"Co-{slug}",
            slug=f"co-{slug}",
            email=f"{slug}@example.com",
            timezone=timezone_name,
            overtime_enabled=overtime_enabled,
            overtime_threshold_hours_per_week=threshold,
            overtime_multiplier=multiplier,
        )
        db_session.add(company)
        await db_session.flush()

        admin = User(
            email=f"admin-{slug}@example.com",
            name="Admin",
            password_hash=AuthService.hash_password("x" * 12),
            role="admin",
            is_active=True,
            company_id=company.id,
        )
        worker = User(
            email=f"worker-{slug}@example.com",
            name="Worker",
            password_hash=AuthService.hash_password("x" * 12),
            role="regular_user",
            is_active=True,
            company_id=company.id,
        )
        db_session.add_all([admin, worker])
        await db_session.flush()

        rate = PayRate(
            user_id=worker.id,
            rate_type="hourly",
            base_rate=base_rate,
            currency="USD",
            overtime_multiplier=rate_pay_multiplier,
            effective_from=date(2025, 1, 1),
            is_active=True,
            created_by=admin.id,
        )
        db_session.add(rate)
        await db_session.flush()

        return company, worker

    return _make


async def _add_hours(
    db_session,
    *,
    user: User,
    start_utc: datetime,
    hours: float,
):
    end = start_utc + timedelta(hours=hours)
    te = TimeEntry(
        user_id=user.id,
        start_time=start_utc,
        end_time=end,
        duration_seconds=int(hours * 3600),
        is_running=False,
    )
    db_session.add(te)
    await db_session.flush()
    return te


async def _create_period(
    db_session,
    *,
    start: date,
    end: date,
    period_type: str = "bi_weekly",
):
    period = PayrollPeriod(
        name=f"P-{start}-{end}",
        period_type=period_type,
        start_date=start,
        end_date=end,
        status="draft",
    )
    db_session.add(period)
    await db_session.flush()
    return period


@pytest.mark.asyncio
class TestProcessPeriodOvertimeOff:
    """overtime_enabled=False: behavior must match the legacy per-period code."""

    async def test_below_threshold_total_pay_unchanged(self, db_session, hourly_setup):
        # Shae-Marcus-style: 100 hours over 2-week (bi_weekly) period @ $20/hr.
        # Legacy threshold = 40 * 2 = 80. So 80 reg + 20 OT*1.5 = 80*20 + 20*30 = 2200.
        # We instead structure the test so total stays UNDER threshold, where the
        # contract "no overtime change" is straightforward: 60 hours total.
        company, worker = await hourly_setup(db_session, overtime_enabled=False)
        # Spread 60h across 2 weeks
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            hours=30,
        )
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 12, 9, 0, tzinfo=timezone.utc),
            hours=30,
        )
        period = await _create_period(
            db_session, start=date(2026, 1, 5), end=date(2026, 1, 18)
        )
        await db_session.commit()

        svc = PayrollPeriodService(db_session)
        result = await svc.process_period(period.id, company_id=company.id)

        assert isinstance(result, PayrollPeriod)
        assert result.total_amount == Decimal("1200.00")  # 60 * 20
        _e = (await db_session.execute(select(PayrollEntry).where(PayrollEntry.payroll_period_id == result.id))).scalars().all(); entry = _e[0]
        assert entry.regular_hours == Decimal("60.00")
        assert entry.overtime_hours == Decimal("0.00")

    async def test_legacy_per_period_overtime_preserved(
        self, db_session, hourly_setup
    ):
        # bi_weekly threshold under legacy = 80. 100 hours -> 80 reg + 20 OT.
        # Per-rate overtime_multiplier = 1.5 (default).
        # Expected: 80*20 + 20*20*1.5 = 1600 + 600 = 2200.
        company, worker = await hourly_setup(db_session, overtime_enabled=False)
        # 50 hours week1, 50 hours week2
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            hours=50,
        )
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 12, 9, 0, tzinfo=timezone.utc),
            hours=50,
        )
        period = await _create_period(
            db_session, start=date(2026, 1, 5), end=date(2026, 1, 18)
        )
        await db_session.commit()

        svc = PayrollPeriodService(db_session)
        result = await svc.process_period(period.id, company_id=company.id)
        assert isinstance(result, PayrollPeriod)
        _e = (await db_session.execute(select(PayrollEntry).where(PayrollEntry.payroll_period_id == result.id))).scalars().all(); entry = _e[0]
        assert entry.regular_hours == Decimal("80.00")
        assert entry.overtime_hours == Decimal("20.00")
        assert result.total_amount == Decimal("2200.00")


@pytest.mark.asyncio
class TestProcessPeriodOvertimeOn:
    """overtime_enabled=True: per-workweek FLSA-compliant calculation."""

    async def test_single_week_50_hours(self, db_session, hourly_setup):
        company, worker = await hourly_setup(db_session, overtime_enabled=True)
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            hours=50,
        )
        period = await _create_period(
            db_session,
            start=date(2026, 1, 5),
            end=date(2026, 1, 11),
            period_type="weekly",
        )
        await db_session.commit()

        svc = PayrollPeriodService(db_session)
        result = await svc.process_period(period.id, company_id=company.id)
        assert isinstance(result, PayrollPeriod)
        _e = (await db_session.execute(select(PayrollEntry).where(PayrollEntry.payroll_period_id == result.id))).scalars().all(); entry = _e[0]
        assert entry.regular_hours == Decimal("40.00")
        assert entry.overtime_hours == Decimal("10.00")
        # 40*20 + 10*20*1.5 = 800 + 300 = 1100
        assert result.total_amount == Decimal("1100.00")

    async def test_two_weeks_each_45_hours(self, db_session, hourly_setup):
        company, worker = await hourly_setup(db_session, overtime_enabled=True)
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            hours=45,
        )
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 12, 9, 0, tzinfo=timezone.utc),
            hours=45,
        )
        period = await _create_period(
            db_session, start=date(2026, 1, 5), end=date(2026, 1, 18)
        )
        await db_session.commit()

        svc = PayrollPeriodService(db_session)
        result = await svc.process_period(period.id, company_id=company.id)
        _e = (await db_session.execute(select(PayrollEntry).where(PayrollEntry.payroll_period_id == result.id))).scalars().all(); entry = _e[0]
        assert entry.regular_hours == Decimal("80.00")
        assert entry.overtime_hours == Decimal("10.00")
        # (40*20 + 5*20*1.5) * 2 = (800+150)*2 = 1900
        assert result.total_amount == Decimal("1900.00")

    async def test_exactly_40_no_overtime(self, db_session, hourly_setup):
        company, worker = await hourly_setup(db_session, overtime_enabled=True)
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            hours=40,
        )
        period = await _create_period(
            db_session,
            start=date(2026, 1, 5),
            end=date(2026, 1, 11),
            period_type="weekly",
        )
        await db_session.commit()

        svc = PayrollPeriodService(db_session)
        result = await svc.process_period(period.id, company_id=company.id)
        _e = (await db_session.execute(select(PayrollEntry).where(PayrollEntry.payroll_period_id == result.id))).scalars().all(); entry = _e[0]
        assert entry.overtime_hours == Decimal("0.00")
        assert result.total_amount == Decimal("800.00")

    async def test_per_week_not_aggregated(self, db_session, hourly_setup):
        # 39h week 1, 41h week 2: only 1h OT (week 2 only).
        company, worker = await hourly_setup(db_session, overtime_enabled=True)
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            hours=39,
        )
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 12, 9, 0, tzinfo=timezone.utc),
            hours=41,
        )
        period = await _create_period(
            db_session, start=date(2026, 1, 5), end=date(2026, 1, 18)
        )
        await db_session.commit()

        svc = PayrollPeriodService(db_session)
        result = await svc.process_period(period.id, company_id=company.id)
        _e = (await db_session.execute(select(PayrollEntry).where(PayrollEntry.payroll_period_id == result.id))).scalars().all(); entry = _e[0]
        assert entry.regular_hours == Decimal("79.00")
        assert entry.overtime_hours == Decimal("1.00")
        # 39*20 + 40*20 + 1*20*1.5 = 780 + 800 + 30 = 1610
        assert result.total_amount == Decimal("1610.00")

    async def test_custom_threshold(self, db_session, hourly_setup):
        company, worker = await hourly_setup(
            db_session,
            overtime_enabled=True,
            threshold=Decimal("35.00"),
        )
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            hours=40,
        )
        period = await _create_period(
            db_session,
            start=date(2026, 1, 5),
            end=date(2026, 1, 11),
            period_type="weekly",
        )
        await db_session.commit()

        svc = PayrollPeriodService(db_session)
        result = await svc.process_period(period.id, company_id=company.id)
        _e = (await db_session.execute(select(PayrollEntry).where(PayrollEntry.payroll_period_id == result.id))).scalars().all(); entry = _e[0]
        assert entry.regular_hours == Decimal("35.00")
        assert entry.overtime_hours == Decimal("5.00")
        # 35*20 + 5*20*1.5 = 700 + 150 = 850
        assert result.total_amount == Decimal("850.00")

    async def test_custom_multiplier_double_time(self, db_session, hourly_setup):
        company, worker = await hourly_setup(
            db_session,
            overtime_enabled=True,
            multiplier=Decimal("2.00"),
        )
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            hours=50,
        )
        period = await _create_period(
            db_session,
            start=date(2026, 1, 5),
            end=date(2026, 1, 11),
            period_type="weekly",
        )
        await db_session.commit()

        svc = PayrollPeriodService(db_session)
        result = await svc.process_period(period.id, company_id=company.id)
        _e = (await db_session.execute(select(PayrollEntry).where(PayrollEntry.payroll_period_id == result.id))).scalars().all(); entry = _e[0]
        assert entry.regular_hours == Decimal("40.00")
        assert entry.overtime_hours == Decimal("10.00")
        # 40*20 + 10*20*2.0 = 800 + 400 = 1200
        assert result.total_amount == Decimal("1200.00")


@pytest.mark.asyncio
class TestPeriodBoundaryTimezone:
    """C3: pay-period bounds use company timezone, not naive UTC."""

    async def test_la_company_includes_local_evening_entry(
        self, db_session, hourly_setup
    ):
        # Pay period 2026-01-01..2026-01-07 for an LA-tz company.
        # Entry: 2026-01-08 02:00 UTC = 2026-01-07 18:00 PST (in period, local).
        # Naive UTC bounds would have placed period end at 2026-01-07 23:59:59 UTC
        # and excluded this entry. With the C3 fix the LA-local end is
        # 2026-01-08 00:00 PST = 2026-01-08 08:00 UTC, so the entry is included.
        company, worker = await hourly_setup(
            db_session,
            timezone_name="America/Los_Angeles",
            overtime_enabled=False,
        )
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 8, 2, 0, tzinfo=timezone.utc),
            hours=2,
        )
        period = await _create_period(
            db_session,
            start=date(2026, 1, 1),
            end=date(2026, 1, 7),
            period_type="weekly",
        )
        await db_session.commit()

        svc = PayrollPeriodService(db_session)
        result = await svc.process_period(period.id, company_id=company.id)
        _e = (await db_session.execute(select(PayrollEntry).where(PayrollEntry.payroll_period_id == result.id))).scalars().all(); entry = _e[0]
        assert entry.regular_hours == Decimal("2.00")
        assert result.total_amount == Decimal("40.00")

    async def test_la_company_excludes_entry_after_local_period_end(
        self, db_session, hourly_setup
    ):
        # Same company; entry 2026-01-08 09:00 UTC = 2026-01-08 01:00 PST,
        # which is *after* the local period-end midnight (2026-01-08 00:00 PST).
        # Should be excluded.
        company, worker = await hourly_setup(
            db_session,
            timezone_name="America/Los_Angeles",
            overtime_enabled=False,
        )
        await _add_hours(
            db_session,
            user=worker,
            start_utc=datetime(2026, 1, 8, 9, 0, tzinfo=timezone.utc),
            hours=2,
        )
        period = await _create_period(
            db_session,
            start=date(2026, 1, 1),
            end=date(2026, 1, 7),
            period_type="weekly",
        )
        await db_session.commit()

        svc = PayrollPeriodService(db_session)
        result = await svc.process_period(period.id, company_id=company.id)
        # No entries in period -> entry created with 0 hours
        _e = (await db_session.execute(select(PayrollEntry).where(PayrollEntry.payroll_period_id == result.id))).scalars().all(); entry = _e[0]
        assert entry.regular_hours == Decimal("0.00")
        assert result.total_amount == Decimal("0.00")

