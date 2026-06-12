from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.models import Company, User
from app.utils.working_days import (
    count_working_days_in_range,
    get_user_working_days,
    is_working_day,
    normalize_working_days,
)


def test_normalize_working_days_sorts_values():
    assert normalize_working_days([4, 2, 0], allow_none=False) == [0, 2, 4]


def test_normalize_working_days_allows_none_when_configured():
    assert normalize_working_days(None, allow_none=True) is None


@pytest.mark.parametrize(
    "value",
    [
        [],
        [0, 0],
        [-1],
        [7],
        [0, "1"],
    ],
)
def test_normalize_working_days_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_working_days(value, allow_none=False)


def test_get_user_working_days_prefers_user_override():
    company = SimpleNamespace(working_days=[0, 1, 2, 3, 4])
    user = SimpleNamespace(working_days=[1, 3, 5], company=company)
    assert get_user_working_days(user) == [1, 3, 5]


def test_get_user_working_days_falls_back_to_company():
    company = SimpleNamespace(working_days=[0, 1, 2, 3])
    user = SimpleNamespace(working_days=None, company=company)
    assert get_user_working_days(user) == [0, 1, 2, 3]


def test_get_user_working_days_defaults_to_mon_to_fri():
    user = SimpleNamespace(working_days=None, company=None)
    assert get_user_working_days(user) == [0, 1, 2, 3, 4]


def test_is_working_day_respects_effective_schedule():
    company = SimpleNamespace(working_days=[0, 1, 2, 3, 4])
    user = SimpleNamespace(working_days=[0, 2, 4], company=company)

    assert is_working_day(user, date(2026, 6, 12)) is True  # Friday
    assert is_working_day(user, date(2026, 6, 11)) is False  # Thursday


def test_count_working_days_in_range_inclusive_and_excluding_today():
    company = SimpleNamespace(working_days=[0, 1, 2, 3, 4])
    user = SimpleNamespace(working_days=None, company=company)

    start = date(2026, 6, 8)  # Monday
    end = date(2026, 6, 12)  # Friday

    assert count_working_days_in_range(user, start, end) == 5
    assert (
        count_working_days_in_range(
            user,
            start,
            end,
            exclude_today=True,
            today=date(2026, 6, 10),
        )
        == 4
    )


def test_count_working_days_in_range_rejects_inverted_range():
    user = SimpleNamespace(working_days=None, company=None)
    with pytest.raises(ValueError, match="end must be on or after start"):
        count_working_days_in_range(user, date(2026, 6, 12), date(2026, 6, 11))


def test_company_model_working_days_is_canonicalized():
    company = Company(name="Acme", slug="acme", email="ops@acme.test", working_days=[4, 0, 2])
    assert company.working_days == [0, 2, 4]


def test_company_model_rejects_duplicates_in_working_days():
    with pytest.raises(ValueError):
        Company(name="Acme", slug="acme", email="ops@acme.test", working_days=[0, 0])


def test_user_model_allows_null_working_days():
    user = User(email="u@test.dev", name="U", password_hash="x", working_days=None)
    assert user.working_days is None


def test_user_model_working_days_is_canonicalized_and_validated():
    user = User(email="u2@test.dev", name="U2", password_hash="x", working_days=[5, 1, 3])
    assert user.working_days == [1, 3, 5]

    with pytest.raises(ValueError):
        user.working_days = [8]
