from decimal import Decimal

from app.utils.pay_rate import get_overtime_multiplier, normalize_rate_to_hourly


def test_normalize_rate_to_hourly_hourly_daily_monthly_annual():
    assert normalize_rate_to_hourly(Decimal("30"), "hourly") == Decimal("30")
    assert normalize_rate_to_hourly(Decimal("240"), "daily") == Decimal("30")
    assert normalize_rate_to_hourly(Decimal("1200"), "monthly") == Decimal("6.923076923076923076923076923")
    assert normalize_rate_to_hourly(Decimal("62400"), "annual") == Decimal("30")


def test_normalize_rate_to_hourly_unsupported_returns_none():
    assert normalize_rate_to_hourly(Decimal("500"), "project_based") is None


def test_get_overtime_multiplier_prefers_company_when_enabled():
    assert get_overtime_multiplier(
        pay_rate_multiplier=Decimal("1.25"),
        company_overtime_enabled=True,
        company_overtime_multiplier=Decimal("2.0"),
    ) == Decimal("2.0")


def test_get_overtime_multiplier_falls_back_to_pay_rate_then_default():
    assert get_overtime_multiplier(Decimal("1.75")) == Decimal("1.75")
    assert get_overtime_multiplier(None) == Decimal("1.5")
