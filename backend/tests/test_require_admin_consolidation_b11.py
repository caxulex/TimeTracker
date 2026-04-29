"""B11 — single canonical ``require_admin``.

Before B11, ``app.routers.admin`` had its own inline ``require_admin``
(super_admin | admin | company_admin) and ``app.middleware.role_check``
defined a *divergent* version (super_admin only). Importing the wrong
one would silently lock out company_admin users from admin endpoints.

After B11, both modules re-use the canonical helper from
``app.dependencies``. These regression tests exercise admin endpoints
with a ``company_admin`` user to make sure the consolidation didn't
narrow the accepted role set.
"""

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.auth_service import AuthService


@pytest_asyncio.fixture
async def company_admin_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"company-admin-{uuid.uuid4().hex[:8]}@example.com",
        name="Company Admin",
        password_hash=AuthService.hash_password("companypass123"),
        role="company_admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def company_admin_headers(company_admin_user: User) -> dict:
    token = AuthService.create_access_token(
        {"sub": str(company_admin_user.id), "email": company_admin_user.email}
    )
    return {"Authorization": f"Bearer {token}"}


class TestRequireAdminAcceptsCompanyAdmin:
    """B11: admin.py used to define its own inline ``require_admin``;
    now imports the canonical one. ``company_admin`` must still be
    accepted on every admin endpoint that uses it."""

    @pytest.mark.asyncio
    async def test_admin_time_entries_accepts_company_admin(
        self, client: AsyncClient, company_admin_headers: dict
    ):
        today = date.today()
        response = await client.get(
            "/api/admin/time-entries",
            params={
                "start_date": (today - timedelta(days=1)).isoformat(),
                "end_date": today.isoformat(),
            },
            headers=company_admin_headers,
        )
        # company_admin is permitted; success body shape is whatever the
        # endpoint returns (200) — never 403.
        assert response.status_code != 403

    @pytest.mark.asyncio
    async def test_canonical_require_admin_is_single_implementation(self):
        """B11: every public ``require_admin`` symbol must resolve to
        the canonical ``app.dependencies.require_admin``."""
        from app.dependencies import require_admin as canonical
        from app.middleware.role_check import require_admin as middleware_re_export
        from app.routers import admin as admin_router

        assert middleware_re_export is canonical
        assert admin_router.require_admin is canonical
