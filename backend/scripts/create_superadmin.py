"""
Create Superadmin Script - Run this to create/update a superadmin user.

Run inside backend container:
    docker exec -it timetracker-backend python -m scripts.create_superadmin

Required environment variables (no defaults):
    FIRST_SUPER_ADMIN_EMAIL     - email address for the bootstrap super_admin
    FIRST_SUPER_ADMIN_PASSWORD  - strong password meeting policy below

Password policy (enforced here AND by app.config):
    - Length >= 14 characters
    - At least 1 uppercase, 1 lowercase, 1 digit, 1 special character
    - Not present in the INSECURE_PASSWORDS denylist (app.config)

This script intentionally has NO hardcoded credentials. If either env var
is unset/empty, or the password fails policy, the script exits non-zero
with a clear diagnostic and makes no DB changes.
"""

import os
import re
import string
import sys

# Make ``app.*`` imports work whether the script is invoked as
# ``python -m scripts.create_superadmin`` from the backend WORKDIR or
# directly via ``python scripts/create_superadmin.py``.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SPECIAL_CHARS = set(string.punctuation)
MIN_PASSWORD_LENGTH = 14


class PasswordPolicyError(ValueError):
    """Raised when FIRST_SUPER_ADMIN_PASSWORD fails policy."""


def validate_password(password: str, denylist: set) -> None:
    """Enforce the strong-password policy. Raises PasswordPolicyError on failure."""
    if not password:
        raise PasswordPolicyError("password is empty")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"password must be at least {MIN_PASSWORD_LENGTH} characters "
            f"(got {len(password)})"
        )

    if not re.search(r"[A-Z]", password):
        raise PasswordPolicyError("password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise PasswordPolicyError("password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise PasswordPolicyError("password must contain at least one digit")
    if not any(c in SPECIAL_CHARS for c in password):
        raise PasswordPolicyError(
            "password must contain at least one special character"
        )

    # Denylist check is case-insensitive (matches app.config validator).
    if password.lower() in {p.lower() for p in denylist}:
        raise PasswordPolicyError(
            "password is in the insecure-password denylist"
        )


def _read_required_env():
    """Return (email, password) from required env vars or exit non-zero."""
    email = os.environ.get("FIRST_SUPER_ADMIN_EMAIL", "").strip()
    password = os.environ.get("FIRST_SUPER_ADMIN_PASSWORD", "")

    missing = []
    if not email:
        missing.append("FIRST_SUPER_ADMIN_EMAIL")
    if not password:
        missing.append("FIRST_SUPER_ADMIN_PASSWORD")

    if missing:
        raise SystemExit(
            "ERROR: required environment variable(s) unset or empty: "
            + ", ".join(missing)
        )

    return email, password


def create_superadmin() -> int:
    """Create or update the super_admin user. Returns process exit code."""
    email, password = _read_required_env()

    # Imports are deferred until after the env-var check so that a missing
    # env var produces a clear diagnostic instead of a config-validation
    # traceback (FIRST_SUPER_ADMIN_PASSWORD has its own pydantic validator).
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.config import INSECURE_PASSWORDS, settings
    from app.services.auth_service import AuthService

    try:
        validate_password(password, INSECURE_PASSWORDS)
    except PasswordPolicyError as exc:
        raise SystemExit(f"ERROR: FIRST_SUPER_ADMIN_PASSWORD rejected: {exc}")

    # Use sync URL for script
    sync_database_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")

    engine = create_engine(sync_database_url)
    try:
        with Session(engine) as session:
            existing = session.execute(
                text("SELECT id, email, role FROM users WHERE email = :email"),
                {"email": email},
            ).fetchone()

            password_hash = AuthService.hash_password(password)

            if existing:
                session.execute(
                    text(
                        """
                        UPDATE users
                        SET role = 'super_admin',
                            password_hash = :password_hash,
                            is_active = true,
                            updated_at = NOW()
                        WHERE email = :email
                        """
                    ),
                    {"email": email, "password_hash": password_hash},
                )
                session.commit()
                print(f"Updated existing user {email} to super_admin.")
            else:
                # NOTE: 'name' is NOT NULL. Derive a placeholder from the
                # email local-part; admins should rename via the UI.
                name = email.split("@", 1)[0]
                session.execute(
                    text(
                        """
                        INSERT INTO users (email, password_hash, name, role, is_active, created_at, updated_at)
                        VALUES (:email, :password_hash, :name, 'super_admin', true, NOW(), NOW())
                        """
                    ),
                    {
                        "email": email,
                        "password_hash": password_hash,
                        "name": name,
                    },
                )
                session.commit()
                print(f"Created super_admin user {email}.")
    finally:
        engine.dispose()

    print(f"Email: {email}")
    print("Password: (read from FIRST_SUPER_ADMIN_PASSWORD; not echoed)")
    print("Role:     super_admin")
    return 0


if __name__ == "__main__":
    raise SystemExit(create_superadmin())
