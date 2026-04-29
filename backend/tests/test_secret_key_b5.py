"""B5 — production refuses to start with an unset/empty SECRET_KEY.

Until B5, a missing ``SECRET_KEY`` env var caused the Settings field
validator to silently auto-generate a random key, which produced a
running-but-broken prod (every restart rotated the signing key,
invalidating all sessions). The production model validator now hard-fails
on missing or empty secrets.
"""

import pytest

from app.config import Settings


_GOOD_SECRET = "x" * 64
_GOOD_ENCRYPTION_KEY = "y" * 64


def _set_env(monkeypatch, environment: str, *, secret_key=None, encryption_key=None):
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("DEBUG", "false")
    if secret_key is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", secret_key)
    if encryption_key is None:
        monkeypatch.delenv("API_KEY_ENCRYPTION_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY_ENCRYPTION_KEY", encryption_key)


class TestProductionSecretKeyRequired:
    def test_production_no_secret_key_raises(self, monkeypatch):
        _set_env(
            monkeypatch,
            "production",
            secret_key=None,
            encryption_key=_GOOD_ENCRYPTION_KEY,
        )
        with pytest.raises(ValueError, match="SECRET_KEY must be explicitly set"):
            Settings(_env_file=None)

    def test_production_whitespace_secret_key_raises(self, monkeypatch):
        # 64 spaces — long enough to pass the field validator's length
        # check (>=32) so the model validator gets a chance to run.
        _set_env(
            monkeypatch,
            "production",
            secret_key=" " * 64,
            encryption_key=_GOOD_ENCRYPTION_KEY,
        )
        with pytest.raises(ValueError, match="SECRET_KEY must be explicitly set"):
            Settings(_env_file=None)

    def test_production_no_encryption_key_raises(self, monkeypatch):
        _set_env(
            monkeypatch,
            "production",
            secret_key=_GOOD_SECRET,
            encryption_key=None,
        )
        with pytest.raises(
            ValueError, match="API_KEY_ENCRYPTION_KEY must be explicitly set"
        ):
            Settings(_env_file=None)

    def test_production_with_valid_secrets_succeeds(self, monkeypatch):
        _set_env(
            monkeypatch,
            "production",
            secret_key=_GOOD_SECRET,
            encryption_key=_GOOD_ENCRYPTION_KEY,
        )
        cfg = Settings(_env_file=None)
        assert cfg.ENVIRONMENT == "production"
        assert cfg.SECRET_KEY == _GOOD_SECRET

    def test_development_no_secret_key_ok(self, monkeypatch):
        """B5: dev still auto-generates SECRET_KEY for convenience."""
        _set_env(monkeypatch, "development", secret_key=None, encryption_key=None)
        cfg = Settings(_env_file=None)
        assert cfg.ENVIRONMENT == "development"
        assert len(cfg.SECRET_KEY) >= 32

    def test_test_env_no_secret_key_ok(self, monkeypatch):
        _set_env(monkeypatch, "test", secret_key=None, encryption_key=None)
        cfg = Settings(_env_file=None)
        assert cfg.ENVIRONMENT == "test"
        assert len(cfg.SECRET_KEY) >= 32
