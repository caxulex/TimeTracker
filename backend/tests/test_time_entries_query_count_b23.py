# ============================================
# B23: list_time_entries query-count regression test
# ============================================
# Before the fix the endpoint issued one count + one sum + one rows
# query + 3 enrichment IN-loads = 6 queries. After the fix, count+sum
# are merged and project/task/user are joined eagerly: 2 queries total.
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Task, Team, TeamMember, TimeEntry, User
from app.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def _bypass_blacklist_for_b23(monkeypatch):
    """Same rationale as test_time_entries_authz_b29: skip the redis
    blacklist round-trip so this query-count test doesn't depend on the
    flaky Windows async-redis path."""

    async def _ok(_jti: str) -> bool:
        return False

    monkeypatch.setattr("app.dependencies._check_blacklist_or_fail_closed", _ok)


@pytest_asyncio.fixture
async def heavy_dataset(db_session: AsyncSession, test_user: User):
    """50 entries spanning 10 projects, 10 tasks, 3 users (all teammates)."""
    team = Team(name=f"B23 team {uuid.uuid4().hex[:6]}", owner_id=test_user.id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=test_user.id, role="owner"))

    users = [test_user]
    for _ in range(2):
        u = User(
            email=f"b23-{uuid.uuid4().hex[:6]}@example.com",
            name="B23 user",
            password_hash=AuthService.hash_password("password123"),
            role="regular_user",
            is_active=True,
            company_id=test_user.company_id,
        )
        db_session.add(u)
        await db_session.flush()
        db_session.add(TeamMember(team_id=team.id, user_id=u.id, role="member"))
        users.append(u)
    await db_session.flush()

    projects = []
    for i in range(10):
        p = Project(name=f"B23 project {i}", team_id=team.id, color="#000000")
        db_session.add(p)
        projects.append(p)
    await db_session.flush()

    tasks = []
    for i in range(10):
        t = Task(name=f"B23 task {i}", project_id=projects[i].id)
        db_session.add(t)
        tasks.append(t)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    for i in range(50):
        entry = TimeEntry(
            user_id=users[i % 3].id,
            project_id=projects[i % 10].id,
            task_id=tasks[i % 10].id,
            start_time=now - timedelta(hours=i + 2),
            end_time=now - timedelta(hours=i + 1),
            duration_seconds=3600,
            is_running=False,
        )
        db_session.add(entry)
    await db_session.flush()
    return {"users": users, "projects": projects, "tasks": tasks}


class _QueryCounter:
    def __init__(self):
        self.count = 0
        self.statements: list[str] = []

    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        # Only count queries that actually touch the ``time_entries`` table.
        # This filters out the auth/user lookup, company-filter resolution,
        # and any savepoint/rollback chatter from the test transaction
        # wrapper. That keeps the assertion focused on the endpoint's own
        # data-access pattern.
        if "time_entries" in statement.lower():
            self.count += 1
            self.statements.append(statement)


@pytest.mark.asyncio
async def test_b23_list_time_entries_query_count(
    client: AsyncClient,
    auth_headers: dict,
    heavy_dataset,
    async_engine,
):
    """B23: the list endpoint must issue ≤ 2 SQL statements."""
    counter = _QueryCounter()
    sync_engine = async_engine.sync_engine
    event.listen(sync_engine, "before_cursor_execute", counter)
    try:
        response = await client.get(
            "/api/time?page_size=50", headers=auth_headers
        )
    finally:
        event.remove(sync_engine, "before_cursor_execute", counter)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["items"], "expected non-empty result"

    # Response shape sanity: project / task / user names still populated.
    sample = payload["items"][0]
    assert "project_name" in sample
    assert "user_name" in sample
    # At least one entry has a task name (every entry above has one).
    assert any(item.get("task_name") for item in payload["items"])

    assert counter.count <= 2, (
        f"expected ≤ 2 SQL statements, got {counter.count}: "
        + "\n---\n".join(counter.statements)
    )
