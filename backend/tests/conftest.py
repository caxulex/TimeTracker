# ============================================
# TIME TRACKER - TEST CONFIGURATION
# Uses PostgreSQL test database (requires Docker containers running)
# ============================================
import os
from typing import AsyncGenerator
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Set test environment before importing app
os.environ["TESTING"] = "1"

from app.main import app
from app.database import get_db
from app.models import User
from app.services.auth_service import AuthService

# Use the real database (running in Docker)
# Try DATABASE_URL first (used in CI), then TEST_DATABASE_URL (local), then default
TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5434/time_tracker"
    )
)


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


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with transaction rollback."""
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    
    async with async_session_factory() as session:
        # Start a transaction
        await session.begin()
        try:
            yield session
        finally:
            # Rollback to clean up test data
            await session.rollback()


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
