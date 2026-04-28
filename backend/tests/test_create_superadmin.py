"""Tests for backend/scripts/create_superadmin.py.

Covers env-var requirements, password policy, denylist, and successful
bootstrap into the test DB. The script uses a SYNC SQLAlchemy engine via
``psycopg2``, so it does not interact with the async test session
directly. We invoke ``create_superadmin()`` (which reads env vars and
talks to the configured DATABASE_URL) and then assert via the async
session that the row exists.

The autouse TRUNCATE fixture in ``conftest.py`` resets DB state between
tests; we only need to ensure the sync engine targets the same DB.
"""

import os
from contextlib import contextmanager

import pytest
from sqlalchemy import text

from scripts.create_superadmin import (
    PasswordPolicyError,
    create_superadmin,
    validate_password,
)


@contextmanager
def _env(**overrides):
    """Set env vars for the duration of the block; restore prior values."""
    sentinel = object()
    prior = {k: os.environ.get(k, sentinel) for k in overrides}
    try:
        for k, v in overrides.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in prior.items():
            if v is sentinel:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Pure validation tests (no DB)
# ---------------------------------------------------------------------------

DENYLIST = {"admin123", "password123", "changeme", "password", "admin"}


def test_validate_password_accepts_strong_password():
    validate_password("CorrectHorse!9Battery", DENYLIST)


@pytest.mark.parametrize(
    "pw,fragment",
    [
        ("Short1!", "at least 14"),
        ("alllowercase1!aaaaaa", "uppercase"),
        ("ALLUPPERCASE1!AAAAAA", "lowercase"),
        ("NoDigitsHere!!!!!", "digit"),
        ("NoSpecial1Aaaaaaaa", "special"),
        ("", "empty"),
    ],
)
def test_validate_password_rejects_weak(pw, fragment):
    with pytest.raises(PasswordPolicyError) as exc:
        validate_password(pw, DENYLIST)
    assert fragment.lower() in str(exc.value).lower()


def test_validate_password_rejects_denylist():
    """Denylist match is case-insensitive on the whole-password value."""
    # Use a value that passes structural rules (>=14, upper, lower, digit,
    # special) so the denylist branch is the cause of rejection. The
    # denylist check is case-insensitive on the whole password.
    pw = "Aaaaaaaaaaaa1!"  # 14 chars; A + a + 1 + !
    denylist = {pw.lower()}
    with pytest.raises(PasswordPolicyError) as exc:
        validate_password(pw, denylist)
    assert "denylist" in str(exc.value).lower()


def test_create_superadmin_rejects_denylist_password_admin123():
    """Smoke-check: the canonical insecure password is rejected before
    any DB connection is attempted (admin123 fails length first, so it
    surfaces as a length error - both behaviours are acceptable; what
    matters is the non-zero exit)."""
    with _env(
        FIRST_SUPER_ADMIN_EMAIL="bootstrap@example.com",
        FIRST_SUPER_ADMIN_PASSWORD="admin123",
    ):
        with pytest.raises(SystemExit):
            create_superadmin()


# ---------------------------------------------------------------------------
# Env-var enforcement (no DB writes occur because we exit before the import
# of app.config / sqlalchemy in the failure paths).
# ---------------------------------------------------------------------------


def test_create_superadmin_exits_when_email_missing():
    with _env(FIRST_SUPER_ADMIN_EMAIL=None, FIRST_SUPER_ADMIN_PASSWORD="StrongPass1!Word"):
        with pytest.raises(SystemExit) as exc:
            create_superadmin()
        assert "FIRST_SUPER_ADMIN_EMAIL" in str(exc.value)


def test_create_superadmin_exits_when_password_missing():
    with _env(
        FIRST_SUPER_ADMIN_EMAIL="bootstrap@example.com",
        FIRST_SUPER_ADMIN_PASSWORD=None,
    ):
        with pytest.raises(SystemExit) as exc:
            create_superadmin()
        assert "FIRST_SUPER_ADMIN_PASSWORD" in str(exc.value)


def test_create_superadmin_exits_when_password_in_denylist():
    with _env(
        FIRST_SUPER_ADMIN_EMAIL="bootstrap@example.com",
        FIRST_SUPER_ADMIN_PASSWORD="admin123",
    ):
        with pytest.raises(SystemExit) as exc:
            create_superadmin()
        msg = str(exc.value)
        assert "rejected" in msg.lower()


def test_create_superadmin_exits_when_password_too_short():
    with _env(
        FIRST_SUPER_ADMIN_EMAIL="bootstrap@example.com",
        FIRST_SUPER_ADMIN_PASSWORD="Short1!",
    ):
        with pytest.raises(SystemExit) as exc:
            create_superadmin()
        assert "14" in str(exc.value)


# ---------------------------------------------------------------------------
# Happy-path: requires the test DB. The script uses a SYNC psycopg2 engine
# pointed at settings.DATABASE_URL. In CI/local that resolves to the same
# database used by the async test fixtures, so the row created here is
# visible via the async db_session, and the autouse TRUNCATE fixture
# cleans it up after the test.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_superadmin_succeeds_with_strong_password(db_session):
    """End-to-end: env-driven bootstrap inserts a super_admin row."""
    # Point the sync engine at the same DB the async fixtures use. The
    # script replaces ``+asyncpg`` with ``+psycopg2`` internally, so we
    # pass an asyncpg URL.
    test_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not test_url:
        pytest.skip("TEST_DATABASE_URL/DATABASE_URL not set; cannot run sync bootstrap")

    # The script reads settings.DATABASE_URL at call time. Override it
    # via the env so both async fixtures and sync script target the
    # same DB.
    with _env(
        FIRST_SUPER_ADMIN_EMAIL="bootstrap-test@example.com",
        FIRST_SUPER_ADMIN_PASSWORD="VeryStrongP@ssword9",
        DATABASE_URL=test_url,
    ):
        # Re-import to pick up the patched DATABASE_URL via settings.
        from importlib import reload

        from app import config as _config

        reload(_config)
        rc = create_superadmin()
        assert rc == 0

    row = (
        await db_session.execute(
            text("SELECT email, role, is_active FROM users WHERE email = :e"),
            {"e": "bootstrap-test@example.com"},
        )
    ).fetchone()
    assert row is not None
    assert row.role == "super_admin"
    assert row.is_active is True
