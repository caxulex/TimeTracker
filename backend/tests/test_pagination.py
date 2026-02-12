# ============================================
# TIME TRACKER - PAGINATION TESTS
# Task 6.2: Verify pagination logic for admin report queries
# ============================================
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, TimeEntry
from app.services.auth_service import AuthService


@pytest_asyncio.fixture
async def admin_with_users(db_session: AsyncSession, admin_user: User):
    """Create admin + multiple users with time entries for pagination tests."""
    import uuid
    users = []
    for i in range(5):
        u = User(
            email=f"pag-user-{uuid.uuid4().hex[:6]}@test.com",
            name=f"Pagination User {i+1}",
            password_hash=AuthService.hash_password("testpass123"),
            role="regular_user",
            is_active=True,
        )
        db_session.add(u)
        users.append(u)
    await db_session.flush()

    # Add time entries for each user
    now = datetime.now(timezone.utc)
    for u in users:
        for j in range(3):
            entry = TimeEntry(
                user_id=u.id,
                start_time=now - timedelta(hours=j+1),
                end_time=now - timedelta(hours=j),
                duration_seconds=3600,
                description=f"Entry {j+1} for {u.name}",
            )
            db_session.add(entry)
    await db_session.flush()

    return admin_user, users


@pytest_asyncio.fixture
async def admin_auth_headers(admin_user: User) -> dict:
    """Auth headers for admin user."""
    token = AuthService.create_access_token({"sub": str(admin_user.id), "email": admin_user.email})
    return {"Authorization": f"Bearer {token}"}


class TestPaginationLogic:
    """Unit tests for pagination math - no DB required."""

    def test_first_page_offsets(self):
        total, page, page_size = 100, 1, 20
        start = (page - 1) * page_size
        end = start + page_size
        total_pages = max(1, (total + page_size - 1) // page_size)
        assert start == 0
        assert end == 20
        assert total_pages == 5

    def test_last_page_offsets(self):
        total, page, page_size = 53, 3, 20
        start = (page - 1) * page_size
        total_pages = max(1, (total + page_size - 1) // page_size)
        assert start == 40
        assert total_pages == 3

    def test_empty_results_single_page(self):
        total, page_size = 0, 20
        total_pages = max(1, (total + page_size - 1) // page_size)
        assert total_pages == 1

    def test_has_next_and_prev(self):
        total, page, page_size = 100, 3, 20
        total_pages = max(1, (total + page_size - 1) // page_size)
        assert (page < total_pages) is True   # has_next
        assert (page > 1) is True             # has_prev

    def test_single_page_no_next(self):
        total, page, page_size = 15, 1, 20
        total_pages = max(1, (total + page_size - 1) // page_size)
        assert (page < total_pages) is False
        assert (page > 1) is False

    def test_invalid_page_detected(self):
        total, page, page_size = 50, 10, 20
        total_pages = max(1, (total + page_size - 1) // page_size)
        assert page > total_pages


@pytest.mark.asyncio
class TestAdminUsersPagination:
    """Integration tests for /api/reports/admin/users with pagination."""

    async def test_no_pagination_returns_list(self, client: AsyncClient, admin_with_users, admin_auth_headers):
        """When no page params, returns backward-compatible list."""
        response = await client.get(
            "/api/reports/admin/users?period=week",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_paginated_returns_object(self, client: AsyncClient, admin_with_users, admin_auth_headers):
        """When page params provided, returns paginated object."""
        response = await client.get(
            "/api/reports/admin/users?period=week&page=1&page_size=2",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "data" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "has_next" in data
        assert "has_prev" in data
        assert "total_pages" in data
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["data"]) <= 2

    async def test_first_page_no_prev(self, client: AsyncClient, admin_with_users, admin_auth_headers):
        """First page should have has_prev=False."""
        response = await client.get(
            "/api/reports/admin/users?period=week&page=1&page_size=2",
            headers=admin_auth_headers,
        )
        data = response.json()
        assert data["has_prev"] is False

    async def test_invalid_page_returns_400(self, client: AsyncClient, admin_with_users, admin_auth_headers):
        """Page beyond total should return 400."""
        response = await client.get(
            "/api/reports/admin/users?period=week&page=999&page_size=2",
            headers=admin_auth_headers,
        )
        assert response.status_code == 400

    async def test_page_size_respected(self, client: AsyncClient, admin_with_users, admin_auth_headers):
        """Page size should limit returned items."""
        response = await client.get(
            "/api/reports/admin/users?period=week&page=1&page_size=3",
            headers=admin_auth_headers,
        )
        data = response.json()
        assert len(data["data"]) <= 3
