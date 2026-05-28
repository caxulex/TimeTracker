import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Project, Task, Team, TeamMember, TimeEntry, User, WorkSession


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


@pytest_asyncio.fixture
async def audit_team(db_session: AsyncSession, test_user: User) -> Team:
    team = Team(
        name="Audit Team",
        owner_id=test_user.id,
    )
    db_session.add(team)
    await db_session.flush()

    db_session.add(
        TeamMember(
            team_id=team.id,
            user_id=test_user.id,
            role="owner",
        )
    )
    await db_session.flush()
    await db_session.refresh(team)
    return team


@pytest_asyncio.fixture
async def audit_project(db_session: AsyncSession, audit_team: Team) -> Project:
    project = Project(
        name="Audit Project",
        description="Project for audit coverage",
        team_id=audit_team.id,
        color="#3B82F6",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def audit_task(db_session: AsyncSession, audit_project: Project) -> Task:
    task = Task(name="Audit Task", project_id=audit_project.id)
    db_session.add(task)
    await db_session.flush()
    await db_session.refresh(task)
    return task


@pytest_asyncio.fixture
async def completed_entry(
    db_session: AsyncSession, test_user: User, audit_project: Project, audit_task: Task
) -> TimeEntry:
    now = datetime.now(timezone.utc)
    entry = TimeEntry(
        user_id=test_user.id,
        project_id=audit_project.id,
        task_id=audit_task.id,
        description="Completed entry",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=1),
        duration_seconds=3600,
        is_running=False,
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    return entry


@pytest_asyncio.fixture
async def running_entry(
    db_session: AsyncSession, test_user: User, audit_project: Project
) -> TimeEntry:
    session = WorkSession(
        user_id=test_user.id,
        company_id=test_user.company_id,
        status="active",
        start_time=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.flush()

    entry = TimeEntry(
        user_id=test_user.id,
        project_id=audit_project.id,
        work_session_id=session.id,
        description="Running entry",
        start_time=datetime.now(timezone.utc) - timedelta(minutes=20),
        end_time=None,
        duration_seconds=None,
        is_running=True,
    )
    db_session.add(entry)
    await db_session.flush()
    await db_session.refresh(entry)
    return entry


async def _latest_audit_for(
    db_session: AsyncSession,
    *,
    resource_type: str,
    action: str,
    resource_id: int | None = None,
) -> AuditLog | None:
    query = select(AuditLog).where(
        AuditLog.resource_type == resource_type,
        AuditLog.action == action,
    )
    if resource_id is not None:
        query = query.where(AuditLog.resource_id == resource_id)
    query = query.order_by(AuditLog.id.desc())
    result = await db_session.execute(query)
    return result.scalars().first()


@pytest.mark.asyncio
async def test_start_timer_writes_time_entry_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
    audit_project: Project,
):
    response = await client.post(
        "/api/time/start",
        json={
            "project_id": audit_project.id,
            "description": "Start for audit",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    entry_id = response.json()["id"]

    audit_row = await _latest_audit_for(
        db_session,
        resource_type="time_entry",
        action="CREATE",
        resource_id=entry_id,
    )
    assert audit_row is not None
    assert audit_row.user_id == test_user.id
    assert audit_row.user_email == test_user.email
    assert "Started timer" in (audit_row.details or "")


@pytest.mark.asyncio
async def test_stop_timer_writes_update_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
    running_entry: TimeEntry,
):
    response = await client.post("/api/time/stop", headers=auth_headers)
    assert response.status_code == 200, response.text

    audit_row = await _latest_audit_for(
        db_session,
        resource_type="time_entry",
        action="UPDATE",
        resource_id=running_entry.id,
    )
    assert audit_row is not None
    assert audit_row.user_id == test_user.id
    assert "Stopped timer" in (audit_row.details or "")


@pytest.mark.asyncio
async def test_stop_timer_no_running_writes_forensic_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
):
    response = await client.post("/api/time/stop", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "No running timer found"

    audit_row = await _latest_audit_for(
        db_session,
        resource_type="time_entry.stop.no_running",
        action="UPDATE",
    )
    assert audit_row is not None
    assert audit_row.user_id == test_user.id
    assert audit_row.user_email == test_user.email
    assert "no running timer" in (audit_row.details or "").lower()


@pytest.mark.asyncio
async def test_switch_timer_writes_update_and_create_audit_logs(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
    audit_team: Team,
    running_entry: TimeEntry,
):
    new_project = Project(
        name="Switch Target Project",
        description="Switch target",
        team_id=audit_team.id,
        color="#10B981",
    )
    db_session.add(new_project)
    await db_session.flush()

    new_task = Task(name="Switch target task", project_id=new_project.id)
    db_session.add(new_task)
    await db_session.flush()

    response = await client.post(
        "/api/time/switch",
        json={
            "project_id": new_project.id,
            "task_id": new_task.id,
            "description": "Switched task",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    new_entry_id = response.json()["id"]

    old_entry_audit = await _latest_audit_for(
        db_session,
        resource_type="time_entry",
        action="UPDATE",
        resource_id=running_entry.id,
    )
    assert old_entry_audit is not None
    assert old_entry_audit.user_id == test_user.id
    assert "Switched timer away" in (old_entry_audit.details or "")

    new_entry_audit = await _latest_audit_for(
        db_session,
        resource_type="time_entry",
        action="CREATE",
        resource_id=new_entry_id,
    )
    assert new_entry_audit is not None
    assert new_entry_audit.user_id == test_user.id
    assert "Switched timer started new" in (new_entry_audit.details or "")


@pytest.mark.asyncio
async def test_manual_entry_create_writes_create_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
    audit_project: Project,
):
    response = await client.post(
        "/api/time",
        json={
            "project_id": audit_project.id,
            "description": "Manual audit entry",
            "duration_seconds": 1800,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    entry_id = response.json()["id"]

    audit_row = await _latest_audit_for(
        db_session,
        resource_type="time_entry",
        action="CREATE",
        resource_id=entry_id,
    )
    assert audit_row is not None
    assert audit_row.user_id == test_user.id
    assert "Created manual time entry" in (audit_row.details or "")


@pytest.mark.asyncio
async def test_put_update_writes_update_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
    completed_entry: TimeEntry,
):
    response = await client.put(
        f"/api/time/{completed_entry.id}",
        json={"description": "Updated by PUT"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    audit_row = await _latest_audit_for(
        db_session,
        resource_type="time_entry",
        action="UPDATE",
        resource_id=completed_entry.id,
    )
    assert audit_row is not None
    assert audit_row.user_id == test_user.id
    assert "via PUT" in (audit_row.details or "")


@pytest.mark.asyncio
async def test_patch_adjust_end_time_writes_update_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
    completed_entry: TimeEntry,
):
    new_end = completed_entry.start_time + timedelta(minutes=45)
    response = await client.patch(
        f"/api/time/entries/{completed_entry.id}",
        json={"end_time": new_end.isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    audit_row = await _latest_audit_for(
        db_session,
        resource_type="time_entry",
        action="UPDATE",
        resource_id=completed_entry.id,
    )
    assert audit_row is not None
    assert audit_row.user_id == test_user.id
    assert "via PATCH" in (audit_row.details or "")


@pytest.mark.asyncio
async def test_delete_entry_writes_delete_audit_log(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
    completed_entry: TimeEntry,
):
    response = await client.delete(f"/api/time/{completed_entry.id}", headers=auth_headers)
    assert response.status_code in [200, 204]

    audit_row = await _latest_audit_for(
        db_session,
        resource_type="time_entry",
        action="DELETE",
        resource_id=completed_entry.id,
    )
    assert audit_row is not None
    assert audit_row.user_id == test_user.id
    assert audit_row.user_email == test_user.email
    assert "Deleted time entry" in (audit_row.details or "")
