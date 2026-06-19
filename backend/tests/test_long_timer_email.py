"""Tests for the hourly long-timer warning email job.

Covers ``backend/scripts/send_long_timer_warnings.py``. The SMTP layer
is mocked - no real emails are sent.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Make ``scripts`` importable: it sits next to ``app`` under ``backend/``.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.models import Company, EmailLog, Project, Task, Team, TimeEntry, User
from app.services.auth_service import AuthService
from scripts import send_long_timer_warnings as job  # type: ignore  # noqa: E402


# ---------- helpers ---------------------------------------------------------


def _make_email_service(
    *, configured: bool = True, send_result: bool = True, raise_exc: Optional[Exception] = None
) -> MagicMock:
    """Build a mocked ``EmailService`` with the surface the job uses."""
    svc = MagicMock()
    svc.is_configured = configured
    svc.from_name = "Time Tracker"
    svc.from_email = "noreply@example.com"
    if raise_exc is not None:
        svc.send_email = AsyncMock(side_effect=raise_exc)
    else:
        svc.send_email = AsyncMock(return_value=send_result)
    return svc


async def _seed_company_user_project_task(db: AsyncSession) -> tuple[Company, User, Project, Task]:
    company = Company(
        name="Acme",
        slug=f"acme-{os.urandom(3).hex()}",
        email="ops@acme.test",
        timezone="UTC",
    )
    db.add(company)
    await db.flush()

    user = User(
        email=f"alice-{os.urandom(3).hex()}@acme.test",
        name="Alice Example",
        password_hash=AuthService.hash_password("x"),
        role="regular_user",
        is_active=True,
        company_id=company.id,
    )
    db.add(user)
    await db.flush()

    team = Team(
        name="Engineering",
        owner_id=user.id,
        company_id=company.id,
    )
    db.add(team)
    await db.flush()

    project = Project(
        name="Website Redesign",
        team_id=team.id,
    )
    db.add(project)
    await db.flush()

    task = Task(
        name="Implement landing page",
        project_id=project.id,
    )
    db.add(task)
    await db.flush()

    return company, user, project, task


async def _make_running_entry(
    db: AsyncSession,
    *,
    user: User,
    project: Project,
    task: Optional[Task],
    started_hours_ago: float,
    end_time: Optional[datetime] = None,
    pause_seconds: int = 0,
    is_paused: bool = False,
    paused_at: Optional[datetime] = None,
    long_timer_email_sent_at: Optional[datetime] = None,
) -> TimeEntry:
    now = datetime.now(timezone.utc)
    if is_paused and paused_at is None:
        paused_at = now
    entry = TimeEntry(
        user_id=user.id,
        project_id=project.id,
        task_id=task.id if task else None,
        start_time=now - timedelta(hours=started_hours_ago),
        end_time=end_time,
        is_running=end_time is None,
        is_paused=is_paused,
        paused_at=paused_at,
        pause_seconds=pause_seconds,
        long_timer_email_sent_at=long_timer_email_sent_at,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


# ---------- tests -----------------------------------------------------------


@pytest.mark.asyncio
async def test_email_sent_for_timer_over_9_hours(db_session: AsyncSession) -> None:
    """Happy path: a 10-hour-old running timer triggers exactly one send."""
    _, user, project, task = await _seed_company_user_project_task(db_session)
    entry = await _make_running_entry(
        db_session, user=user, project=project, task=task, started_hours_ago=10
    )
    await db_session.commit()

    svc = _make_email_service()

    summary = await job.send_long_timer_warnings(db_session, svc)

    assert summary == {"sent": 1, "skipped": 0, "candidates": 1}
    svc.send_email.assert_awaited_once()
    call_kwargs = svc.send_email.await_args.kwargs
    assert call_kwargs["to_email"] == user.email
    assert "9 hours" in call_kwargs["subject"] or "10 hours" in call_kwargs["subject"]


@pytest.mark.asyncio
async def test_no_email_for_timer_under_9_hours(db_session: AsyncSession) -> None:
    """Boundary: 8h59m must not trigger."""
    _, user, project, task = await _seed_company_user_project_task(db_session)
    await _make_running_entry(
        db_session,
        user=user,
        project=project,
        task=task,
        started_hours_ago=8 + 59 / 60,  # 8h59m
    )
    await db_session.commit()

    svc = _make_email_service()
    summary = await job.send_long_timer_warnings(db_session, svc)

    assert summary["candidates"] == 0
    svc.send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_email_for_running_timer_with_large_pause_seconds(db_session: AsyncSession) -> None:
    """Gross elapsed over 9h must not trigger if net on-task time is below 9h."""
    _, user, project, task = await _seed_company_user_project_task(db_session)
    await _make_running_entry(
        db_session,
        user=user,
        project=project,
        task=task,
        started_hours_ago=10,
        pause_seconds=2 * 3600,
    )
    await db_session.commit()

    svc = _make_email_service()
    summary = await job.send_long_timer_warnings(db_session, svc)

    assert summary["sent"] == 0
    svc.send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_email_for_actively_paused_timer_under_net_threshold(db_session: AsyncSession) -> None:
    """A running entry frozen on pause must not trigger if the paused elapsed is under 9h."""
    _, user, project, task = await _seed_company_user_project_task(db_session)
    now = datetime.now(timezone.utc)
    await _make_running_entry(
        db_session,
        user=user,
        project=project,
        task=task,
        started_hours_ago=10,
        is_paused=True,
        paused_at=now - timedelta(hours=8),
    )
    await db_session.commit()

    svc = _make_email_service()
    summary = await job.send_long_timer_warnings(db_session, svc)

    assert summary["sent"] == 0
    svc.send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_email_for_completed_timer(db_session: AsyncSession) -> None:
    """A timer with end_time set, even if started >9h ago, is ignored."""
    _, user, project, task = await _seed_company_user_project_task(db_session)
    now = datetime.now(timezone.utc)
    await _make_running_entry(
        db_session,
        user=user,
        project=project,
        task=task,
        started_hours_ago=12,
        end_time=now - timedelta(hours=1),
    )
    await db_session.commit()

    svc = _make_email_service()
    summary = await job.send_long_timer_warnings(db_session, svc)

    assert summary["candidates"] == 0
    svc.send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_duplicate_email_on_subsequent_runs(db_session: AsyncSession) -> None:
    """After a successful send, the next hourly run skips the same entry."""
    _, user, project, task = await _seed_company_user_project_task(db_session)
    await _make_running_entry(
        db_session, user=user, project=project, task=task, started_hours_ago=10
    )
    await db_session.commit()

    svc = _make_email_service()
    s1 = await job.send_long_timer_warnings(db_session, svc)
    assert s1["sent"] == 1

    s2 = await job.send_long_timer_warnings(db_session, svc)
    assert s2 == {"sent": 0, "skipped": 0, "candidates": 0}
    # Total sends across both runs is exactly 1.
    assert svc.send_email.await_count == 1


@pytest.mark.asyncio
async def test_email_sent_at_correctly_set(db_session: AsyncSession) -> None:
    _, user, project, task = await _seed_company_user_project_task(db_session)
    entry = await _make_running_entry(
        db_session, user=user, project=project, task=task, started_hours_ago=10
    )
    await db_session.commit()

    before = datetime.now(timezone.utc)
    svc = _make_email_service()
    await job.send_long_timer_warnings(db_session, svc)
    after = datetime.now(timezone.utc)

    refreshed = (
        await db_session.execute(select(TimeEntry).where(TimeEntry.id == entry.id))
    ).scalar_one()
    assert refreshed.long_timer_email_sent_at is not None
    assert before - timedelta(seconds=1) <= refreshed.long_timer_email_sent_at <= after + timedelta(seconds=1)


@pytest.mark.asyncio
async def test_failed_email_does_not_set_sent_at(db_session: AsyncSession) -> None:
    """SMTP failure leaves long_timer_email_sent_at NULL so retry can fire."""
    _, user, project, task = await _seed_company_user_project_task(db_session)
    entry = await _make_running_entry(
        db_session, user=user, project=project, task=task, started_hours_ago=10
    )
    await db_session.commit()

    svc = _make_email_service(raise_exc=RuntimeError("smtp blew up"))
    summary = await job.send_long_timer_warnings(db_session, svc)
    assert summary == {"sent": 0, "skipped": 1, "candidates": 1}

    refreshed = (
        await db_session.execute(select(TimeEntry).where(TimeEntry.id == entry.id))
    ).scalar_one()
    assert refreshed.long_timer_email_sent_at is None

    # And the failure was recorded in EmailLog with status=failed.
    failed_logs = (
        await db_session.execute(
            select(EmailLog).where(EmailLog.email_type == job.EMAIL_TYPE)
        )
    ).scalars().all()
    assert len(failed_logs) == 1
    assert failed_logs[0].status == "failed"


@pytest.mark.asyncio
async def test_email_logged_in_emaillog(db_session: AsyncSession) -> None:
    _, user, project, task = await _seed_company_user_project_task(db_session)
    await _make_running_entry(
        db_session, user=user, project=project, task=task, started_hours_ago=10
    )
    await db_session.commit()

    svc = _make_email_service()
    await job.send_long_timer_warnings(db_session, svc)

    logs = (
        await db_session.execute(
            select(EmailLog).where(EmailLog.email_type == job.EMAIL_TYPE)
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].to_email == user.email
    assert logs[0].status == "sent"
    assert logs[0].company_id == user.company_id


@pytest.mark.asyncio
async def test_email_includes_correct_user_data(db_session: AsyncSession) -> None:
    _, user, project, task = await _seed_company_user_project_task(db_session)
    await _make_running_entry(
        db_session, user=user, project=project, task=task, started_hours_ago=10
    )
    await db_session.commit()

    svc = _make_email_service()
    await job.send_long_timer_warnings(db_session, svc)

    kwargs = svc.send_email.await_args.kwargs
    assert kwargs["to_email"] == user.email
    assert user.name in kwargs["body_html"]
    assert user.name in kwargs["body_text"]
    assert project.name in kwargs["body_html"]
    assert project.name in kwargs["body_text"]
    assert task.name in kwargs["body_html"]


@pytest.mark.asyncio
async def test_unconfigured_email_service_is_noop(db_session: AsyncSession) -> None:
    """If SMTP is not configured the job must not crash and must not stamp."""
    _, user, project, task = await _seed_company_user_project_task(db_session)
    entry = await _make_running_entry(
        db_session, user=user, project=project, task=task, started_hours_ago=10
    )
    await db_session.commit()

    svc = _make_email_service(configured=False)
    summary = await job.send_long_timer_warnings(db_session, svc)

    assert summary == {"sent": 0, "skipped": 0, "candidates": 0}
    svc.send_email.assert_not_awaited()
    refreshed = (
        await db_session.execute(select(TimeEntry).where(TimeEntry.id == entry.id))
    ).scalar_one()
    assert refreshed.long_timer_email_sent_at is None
