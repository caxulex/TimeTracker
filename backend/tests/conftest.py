# ============================================
# TIME TRACKER - TEST CONFIGURATION
# Uses PostgreSQL test database. Connection string is env-driven;
# see backend/.env.example and backend/scripts/DEV_SETUP.md.
# ============================================
import logging
import os
from typing import AsyncGenerator
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Set test environment before importing app
os.environ["TESTING"] = "1"

from app.main import app
from app.database import get_db
from app.models import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Resolve the test database URL in this order:
#   1. TEST_DATABASE_URL (explicit, preferred for local dev + CI)
#   2. DATABASE_URL       (legacy CI compatibility)
#   3. Hardcoded fallback  (debug-logged; should be avoided)
_DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/time_tracker_test"
)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
if not TEST_DATABASE_URL:
    logger.debug(
        "conftest: TEST_DATABASE_URL / DATABASE_URL unset, "
        "falling back to default %s",
        _DEFAULT_TEST_DATABASE_URL,
    )
    TEST_DATABASE_URL = _DEFAULT_TEST_DATABASE_URL


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async test engine using the real database."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _truncate_tables_around_test(async_engine) -> AsyncGenerator[None, None]:
    """
    Test isolation via TRUNCATE-before-test (Option B).

    Individual tests exercise FastAPI route handlers that call
    ``session.commit()`` directly, which means a naive
    ``begin()``/``rollback()`` wrapper in ``db_session`` cannot
    prevent cross-test data leakage. Running TRUNCATE against every
    user table (except ``alembic_version``) *before* each test
    guarantees a clean slate regardless of what the previous test or
    a previous pytest run committed. ``CASCADE`` handles FK chains;
    ``RESTART IDENTITY`` resets sequences so autoincrement IDs do
    not drift.
    """
    async with async_engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT tablename "
                "FROM pg_tables "
                "WHERE schemaname = 'public' "
                "  AND tablename <> 'alembic_version'"
            )
        )
        tables = [row[0] for row in result.fetchall()]
        if tables:
            quoted = ", ".join(f'"{t}"' for t in tables)
            await conn.execute(
                text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")
            )

    yield


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Test DB session. No transaction wrapping: app handlers commit
    their own work, and the ``_truncate_tables_after_test`` autouse
    fixture guarantees isolation by wiping all rows after each test.
    """
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database session override."""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    import uuid
    unique_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=unique_email,
        name="Test User",
        password_hash=AuthService.hash_password("testpassword123"),
        role="regular_user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin test user."""
    import uuid
    unique_email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=unique_email,
        name="Admin User",
        password_hash=AuthService.hash_password("adminpassword123"),
        role="super_admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test user."""
    token = AuthService.create_access_token({"sub": str(test_user.id), "email": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def admin_auth_headers(admin_user: User) -> dict:
    """Create authentication headers for admin user."""
    token = AuthService.create_access_token({"sub": str(admin_user.id), "email": admin_user.email})
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture(scope="function")
async def auth_token(test_user: User) -> str:
    """Create authentication token for test user."""
    token = AuthService.create_access_token({"sub": str(test_user.id), "email": test_user.email})
    return token


@pytest_asyncio.fixture(scope="function")
async def admin_token(admin_user: User) -> str:
    """Create authentication token for admin user."""
    token = AuthService.create_access_token({"sub": str(admin_user.id), "email": admin_user.email})
    return token
