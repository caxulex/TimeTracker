#!/usr/bin/env python3
"""
Hourly long-timer warning email job.

Finds running TimeEntry rows whose timer has been running for more than
LONG_TIMER_THRESHOLD_HOURS and sends a single friendly reminder email
to the timer's owner. Idempotency is enforced by stamping
``time_entries.long_timer_email_sent_at`` after a successful send (see
migration ``024_add_long_timer_email_sent_at``).

Usage::

    # Run once (typically driven by an external hourly scheduler /
    # docker compose loop):
    python scripts/send_long_timer_warnings.py

Behavior contract (also covered by tests):

* Only running entries (``end_time IS NULL``) with
  ``start_time < now - 9h`` and ``long_timer_email_sent_at IS NULL`` are
  candidates. Anything failing those filters is skipped.
* Email is sent via ``EmailService.send_email`` and logged to
  ``email_logs`` via ``log_email_sent`` / ``log_email_failed``.
* On any send error the entry's stamp is **not** updated, so the next
  hourly run will retry. We never want to suppress a legitimately needed
  warning because of a transient SMTP issue.
* If the email service is unconfigured (``is_configured`` is ``False``)
  we log a single warning and skip every candidate without crashing -
  the scheduler container must not crash on misconfig.
* The recipient is always the timer's owner (``user.email``). v1 has
  no admin/configurable recipient and no env-var threshold knob.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

# Allow running as ``python scripts/send_long_timer_warnings.py``.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload

from app.models import Project, Task, TimeEntry, User
from app.services.email_log_utils import log_email_failed, log_email_sent
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

# Hardcoded in v1 per spec - no env knobs.
LONG_TIMER_THRESHOLD_HOURS = 9
EMAIL_TYPE = "long_timer_warning"


def _format_start_time(start_time: datetime, company_timezone: str) -> str:
    """Render the start_time in the company's timezone, falling back to UTC.

    Best effort: if the configured ``company_timezone`` cannot be resolved
    we emit the UTC value rather than crashing the job for one bad row.
    """
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(company_timezone or "UTC")
    except Exception:  # pragma: no cover - defensive
        tz = timezone.utc
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    local = start_time.astimezone(tz)
    return local.strftime("%Y-%m-%d %H:%M %Z")


def _build_email_bodies(
    *,
    user_name: str,
    project_name: str,
    task_name: Optional[str],
    duration_hours: float,
    start_time_display: str,
    dashboard_url: str,
    from_name: str,
) -> tuple[str, str, str]:
    """Return ``(subject, body_html, body_text)``."""
    hours_int = int(duration_hours)
    subject = f"Reminder: your timer has been running for {hours_int} hours"

    target_label = project_name
    if task_name:
        target_label = f"{project_name} \u2014 {task_name}"

    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2563eb;">Just a friendly reminder</h1>
            <p>Hi {user_name},</p>
            <p>
                Your timer for <strong>{target_label}</strong> has been
                running for about <strong>{hours_int} hours</strong>
                (started {start_time_display}).
            </p>
            <p>
                If you're still working, no action is needed. If you
                wrapped up earlier and forgot to stop the timer, you
                can either stop it now or adjust the end time from
                your time entries page.
            </p>
            <p>
                <a href="{dashboard_url}"
                   style="display: inline-block; padding: 12px 24px;
                          background-color: #2563eb; color: white;
                          text-decoration: none; border-radius: 6px;">
                    Open TimeTracker
                </a>
            </p>
            <p style="color: #666; font-size: 13px; margin-top: 24px;">
                You're receiving this because a timer on your account
                has been running for more than {LONG_TIMER_THRESHOLD_HOURS} hours.
                We only send this reminder once per timer.
            </p>
            <p>Best regards,<br>{from_name} Team</p>
        </div>
    </body>
    </html>
    """.strip()

    body_text = (
        f"Just a friendly reminder\n\n"
        f"Hi {user_name},\n\n"
        f"Your timer for {target_label} has been running for about "
        f"{hours_int} hours (started {start_time_display}).\n\n"
        f"If you're still working, no action is needed. If you wrapped\n"
        f"up earlier and forgot to stop the timer, you can either stop\n"
        f"it now or adjust the end time from your time entries page.\n\n"
        f"Open TimeTracker: {dashboard_url}\n\n"
        f"You're receiving this because a timer on your account has\n"
        f"been running for more than {LONG_TIMER_THRESHOLD_HOURS} hours.\n"
        f"We only send this reminder once per timer.\n\n"
        f"Best regards,\n{from_name} Team\n"
    )

    return subject, body_html, body_text


async def _process_entry(
    *,
    db: AsyncSession,
    email_service: EmailService,
    entry: TimeEntry,
    now: datetime,
) -> bool:
    """Send the warning for one entry. Returns True if email was sent
    (and the idempotency stamp was set), False otherwise.

    Never raises: any exception is logged and swallowed so a single bad
    row cannot abort the whole hourly run.
    """
    user = entry.user
    if user is None or not user.email:
        logger.warning(
            "Skipping long-timer warning: no user/email",
            extra={"entry_id": entry.id, "user_id": entry.user_id},
        )
        return False

    project_name = entry.project.name if entry.project else "(no project)"
    task_name = entry.task.name if entry.task else None
    company_tz = (
        user.company.timezone
        if (user.company is not None and getattr(user.company, "timezone", None))
        else "UTC"
    )
    start_time_display = _format_start_time(entry.start_time, company_tz)
    duration_hours = (now - entry.start_time).total_seconds() / 3600.0

    dashboard_url = os.getenv("APP_DASHBOARD_URL", "http://localhost:5173/dashboard")

    subject, body_html, body_text = _build_email_bodies(
        user_name=user.name or user.email,
        project_name=project_name,
        task_name=task_name,
        duration_hours=duration_hours,
        start_time_display=start_time_display,
        dashboard_url=dashboard_url,
        from_name=email_service.from_name or "Time Tracker",
    )

    try:
        sent = await email_service.send_email(
            to_email=user.email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )
    except Exception as exc:  # EmailSendError, EmailConfigurationError, transport
        logger.warning(
            "Failed to send long-timer warning email",
            extra={
                "entry_id": entry.id,
                "user_id": user.id,
                "duration_hours": round(duration_hours, 2),
                "error": str(exc)[:200],
            },
        )
        try:
            await log_email_failed(
                db=db,
                to_email=user.email,
                subject=subject,
                email_type=EMAIL_TYPE,
                error_message=str(exc)[:500],
                company_id=user.company_id,
                metadata={
                    "entry_id": entry.id,
                    "user_id": user.id,
                    "duration_hours": round(duration_hours, 2),
                },
            )
        except Exception:  # pragma: no cover - logging-of-logging
            logger.exception("Failed to record EmailLog (failed) row")
        return False

    if not sent:
        # send_email returns False when SMTP is not configured.
        logger.warning(
            "Email service not configured; skipping long-timer warning",
            extra={"entry_id": entry.id, "user_id": user.id},
        )
        return False

    # Stamp first, then log: a successful send must always be reflected
    # in time_entries so we never re-email. If EmailLog write fails, the
    # send is still recorded against the entry (idempotency wins).
    entry.long_timer_email_sent_at = now
    await db.flush()

    try:
        await log_email_sent(
            db=db,
            to_email=user.email,
            subject=subject,
            email_type=EMAIL_TYPE,
            company_id=user.company_id,
            metadata={
                "entry_id": entry.id,
                "user_id": user.id,
                "duration_hours": round(duration_hours, 2),
            },
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to record EmailLog (sent) row")

    logger.info(
        "Sent long-timer warning email",
        extra={
            "user_id": user.id,
            "entry_id": entry.id,
            "duration_hours": round(duration_hours, 2),
        },
    )
    return True


async def send_long_timer_warnings(
    db: AsyncSession,
    email_service: EmailService,
    now: Optional[datetime] = None,
) -> dict:
    """Find candidate entries and email their owners.

    Importable from tests; ``main()`` is the cron-style entry point.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=LONG_TIMER_THRESHOLD_HOURS)

    if not email_service.is_configured:
        logger.warning(
            "Email service not configured; long-timer warning job is a no-op"
        )
        return {"sent": 0, "skipped": 0, "candidates": 0}

    result = await db.execute(
        select(TimeEntry)
        .where(
            TimeEntry.end_time.is_(None),
            TimeEntry.long_timer_email_sent_at.is_(None),
            TimeEntry.start_time < cutoff,
        )
        .options(
            selectinload(TimeEntry.user).selectinload(User.company),
            selectinload(TimeEntry.project),
            selectinload(TimeEntry.task),
        )
    )
    candidates = list(result.scalars().all())

    sent_count = 0
    skipped_count = 0
    for entry in candidates:
        ok = await _process_entry(
            db=db, email_service=email_service, entry=entry, now=now
        )
        if ok:
            sent_count += 1
        else:
            skipped_count += 1

    await db.commit()

    logger.info(
        "long-timer warning job complete",
        extra={
            "candidates": len(candidates),
            "sent": sent_count,
            "skipped": skipped_count,
        },
    )
    return {
        "sent": sent_count,
        "skipped": skipped_count,
        "candidates": len(candidates),
    }


async def main() -> None:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/time_tracker",
    )
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )

    engine = create_async_engine(database_url, echo=False)
    Session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    email_service = EmailService()
    try:
        async with Session() as db:
            try:
                summary = await send_long_timer_warnings(db, email_service)
                print(f"[long-timer-warnings] {summary}")
            except Exception:
                logger.exception("long-timer warning job crashed")
                # Do not re-raise: the scheduler container must keep running.
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
