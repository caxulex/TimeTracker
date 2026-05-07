# ============================================
# TIME TRACKER - PATCH /api/time/entries/{id} TESTS
# Personal-scope edit endpoint with strict ownership +
# running-timer / time-logic / project-task validations.
# ============================================
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Task, Team, TeamMember, TimeEntry, User, WorkSession
from app.services.auth_service import AuthService


PATCH_URL = "/api/time/entries/{entry_id}"


# ---------- local Redis stub ----------
#
# CI provides a real Redis service; local dev environments often don't.
# The token-blacklist check is fail-closed (returns 401 if Redis is
# unreachable), which would block every test in this module. We can't
# touch conftest.py per the spec, so we install a tiny in-memory stub
# scoped to this module that satisfies the ``exists`` / ``ping``
# protocol used by ``token_blacklist.get_redis``. Tests that genuinely
# care about blacklist semantics live elsewhere.

class _StubRedis:
    async def exists(self, _key: str) -> int:
        return 0

    async def ping(self) -> bool:
        return True


@pytest_asyncio.fixture(autouse=True)
async def _stub_token_blacklist_redis():
    from app.services import token_blacklist as _tb_module

    _tb_module.token_blacklist._redis = _StubRedis()
    yield
    _tb_module.token_blacklist._redis = None


# ---------- fixtures ----------

@pytest_asyncio.fixture
async def test_team(db_session: AsyncSession, test_user: User) -> Team:
    team = Team(name="Edit Test Team", owner_id=test_user.id)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMember(team_id=team.id, user_id=test_user.id, role="owner"))
    await db_session.flush()
    await db_session.refresh(team)
    return team


@pytest_asyncio.fixture
async def test_project(
    db_session: AsyncSession, test_user: User, test_team: Team
) -> Project:
    project = Project(
        name="Edit Test Project",
        description="Project for edit tests",
        team_id=test_team.id,
        color="#3B82F6",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def second_project(
    db_session: AsyncSession, test_user: User, test_team: Team
) -> Project:
    project = Project(
        name="Second Project",
        description="Another project on same team",
        team_id=test_team.id,
        color="#10B981",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def test_task(db_session: AsyncSession, test_project: Project) -> Task:
    task = Task(name="Edit Test Task", project_id=test_project.id)
    db_session.add(task)
    await db_session.flush()
    await db_session.refresh(task)
    return task


@pytest_asyncio.fixture
async def task_in_second_project(
    db_session: AsyncSession, second_project: Project
) -> Task:
    task = Task(name="Other Project Task", project_id=second_project.id)
    db_session.add(task)
    await db_session.flush()
    await db_session.refresh(task)
    return task


@pytest_asyncio.fixture
async def completed_entry(
    db_session: AsyncSession, test_user: User, test_project: Project, test_task: Task
) -> TimeEntry:
    now = datetime.now(timezone.utc)
    entry = TimeEntry(
        user_id=test_user.id,
        project_id=test_project.id,
        task_id=test_task.id,
        description="Original description",
        start_time=now - timedelta(hours=3),
        end_time=now - timedelta(hours=1),
        duration_seconds=2 * 3600,
        is_running=False,
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    return entry


@pytest_asyncio.fixture
async def running_entry(
    db_session: AsyncSession, test_user: User, test_project: Project
) -> TimeEntry:
    work_session = WorkSession(
        user_id=test_user.id,
        company_id=test_user.company_id,
        start_time=datetime.now(timezone.utc) - timedelta(hours=1),
        status="active",
    )
    db_session.add(work_session)
    await db_session.flush()
    entry = TimeEntry(
        user_id=test_user.id,
        project_id=test_project.id,
        work_session_id=work_session.id,
        description="Running timer",
        start_time=datetime.now(timezone.utc) - timedelta(minutes=15),
        end_time=None,
        duration_seconds=None,
        is_running=True,
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    return entry


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    unique_email = f"other-{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=unique_email,
        name="Other User",
        password_hash=AuthService.hash_password("otherpassword123"),
        role="regular_user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user_entry(
    db_session: AsyncSession, other_user: User, test_project: Project
) -> TimeEntry:
    now = datetime.now(timezone.utc)
    entry = TimeEntry(
        user_id=other_user.id,
        project_id=test_project.id,
        description="Belongs to someone else",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=1),
        duration_seconds=3600,
        is_running=False,
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    return entry


# ---------- tests ----------


@pytest.mark.asyncio
async def test_user_can_edit_own_entry_description(
    client: AsyncClient, auth_headers: dict, completed_entry: TimeEntry
):
    """1. Happy path: change description only."""
    response = await client.patch(
        PATCH_URL.format(entry_id=completed_entry.id),
        json={"description": "Updated via PATCH"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["description"] == "Updated via PATCH"
    assert body["id"] == completed_entry.id


@pytest.mark.asyncio
async def test_user_can_edit_own_entry_full(
    client: AsyncClient,
    auth_headers: dict,
    completed_entry: TimeEntry,
    second_project: Project,
    task_in_second_project: Task,
):
    """2. Change all fields at once."""
    new_start = datetime.now(timezone.utc) - timedelta(hours=4)
    new_end = datetime.now(timezone.utc) - timedelta(hours=2)
    response = await client.patch(
        PATCH_URL.format(entry_id=completed_entry.id),
        json={
            "description": "Full update",
            "start_time": new_start.isoformat(),
            "end_time": new_end.isoformat(),
            "project_id": second_project.id,
            "task_id": task_in_second_project.id,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["description"] == "Full update"
    assert body["project_id"] == second_project.id
    assert body["task_id"] == task_in_second_project.id
    assert body["duration_seconds"] == 2 * 3600


@pytest.mark.asyncio
async def test_user_can_edit_completed_entry_end_time(
    client: AsyncClient, auth_headers: dict, completed_entry: TimeEntry
):
    """3. Fix a runaway timer that's already stopped."""
    # Move end_time to be 30 minutes after start (shorten the runaway).
    new_end = completed_entry.start_time + timedelta(minutes=30)
    response = await client.patch(
        PATCH_URL.format(entry_id=completed_entry.id),
        json={"end_time": new_end.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["duration_seconds"] == 30 * 60


@pytest.mark.asyncio
async def test_user_cannot_edit_others_entry(
    client: AsyncClient, auth_headers: dict, other_user_entry: TimeEntry
):
    """4. 403 when the entry belongs to another user."""
    response = await client.patch(
        PATCH_URL.format(entry_id=other_user_entry.id),
        json={"description": "Hacking attempt"},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_edit_others_entry_via_patch(
    client: AsyncClient, admin_auth_headers: dict, other_user_entry: TimeEntry
):
    """5. Admins are scoped to themselves on this personal endpoint."""
    response = await client.patch(
        PATCH_URL.format(entry_id=other_user_entry.id),
        json={"description": "Admin override"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cannot_edit_nonexistent_entry(
    client: AsyncClient, auth_headers: dict
):
    """6. 404 when the entry doesn't exist."""
    response = await client.patch(
        PATCH_URL.format(entry_id=999_999),
        json={"description": "ghost"},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_edit_running_timer_start_time(
    client: AsyncClient, auth_headers: dict, running_entry: TimeEntry
):
    """7. Running timer: start_time edits rejected with 400."""
    new_start = datetime.now(timezone.utc) - timedelta(hours=2)
    response = await client.patch(
        PATCH_URL.format(entry_id=running_entry.id),
        json={"start_time": new_start.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Stop the timer" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_edit_running_timer_end_time(
    client: AsyncClient, auth_headers: dict, running_entry: TimeEntry
):
    """8. Running timer: end_time edits rejected with 400 (must use /stop)."""
    new_end = datetime.now(timezone.utc)
    response = await client.patch(
        PATCH_URL.format(entry_id=running_entry.id),
        json={"end_time": new_end.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Stop the timer" in response.json()["detail"]


@pytest.mark.asyncio
async def test_can_edit_running_timer_description(
    client: AsyncClient, auth_headers: dict, running_entry: TimeEntry
):
    """9. Description-only edits on running timers still work at the API level.

    The frontend funnels users through a 'stop first' UX, but the backend
    accepts the edit since none of the running-timer guards apply.
    """
    response = await client.patch(
        PATCH_URL.format(entry_id=running_entry.id),
        json={"description": "Live update"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Live update"


@pytest.mark.asyncio
async def test_end_before_start_returns_400(
    client: AsyncClient, auth_headers: dict, completed_entry: TimeEntry
):
    """10. end_time <= start_time → 400."""
    bad_end = completed_entry.start_time - timedelta(minutes=5)
    response = await client.patch(
        PATCH_URL.format(entry_id=completed_entry.id),
        json={"end_time": bad_end.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_future_end_time_returns_400(
    client: AsyncClient, auth_headers: dict, completed_entry: TimeEntry
):
    """11. end_time more than 5 minutes in the future → 400."""
    future_end = datetime.now(timezone.utc) + timedelta(hours=1)
    response = await client.patch(
        PATCH_URL.format(entry_id=completed_entry.id),
        json={"end_time": future_end.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_invalid_project_returns_404(
    client: AsyncClient, auth_headers: dict, completed_entry: TimeEntry
):
    """12. Unknown project_id → 404."""
    response = await client.patch(
        PATCH_URL.format(entry_id=completed_entry.id),
        json={"project_id": 999_999},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_task_must_belong_to_project_returns_400(
    client: AsyncClient,
    auth_headers: dict,
    completed_entry: TimeEntry,
    task_in_second_project: Task,
):
    """13. Task whose project_id mismatches the resulting project_id → 400."""
    # completed_entry is on test_project; task_in_second_project is on second_project.
    response = await client.patch(
        PATCH_URL.format(entry_id=completed_entry.id),
        json={"task_id": task_in_second_project.id},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "project" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_description_max_length_enforced(
    client: AsyncClient, auth_headers: dict, completed_entry: TimeEntry
):
    """14. description longer than 500 chars → 422 from schema layer."""
    response = await client.patch(
        PATCH_URL.format(entry_id=completed_entry.id),
        json={"description": "x" * 501},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_partial_update_does_not_clear_unchanged_fields(
    client: AsyncClient, auth_headers: dict, completed_entry: TimeEntry
):
    """15. Sending only description leaves the rest intact."""
    original_start = completed_entry.start_time
    original_end = completed_entry.end_time
    original_project = completed_entry.project_id
    original_task = completed_entry.task_id

    response = await client.patch(
        PATCH_URL.format(entry_id=completed_entry.id),
        json={"description": "Just the description"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["description"] == "Just the description"
    assert body["project_id"] == original_project
    assert body["task_id"] == original_task
    # ISO datetime round-trip — compare on second precision.
    assert datetime.fromisoformat(body["start_time"]).replace(microsecond=0) == \
        original_start.replace(microsecond=0)
    assert datetime.fromisoformat(body["end_time"]).replace(microsecond=0) == \
        original_end.replace(microsecond=0)
