"""Tenant-local time helpers for AI services.

This module centralizes the safe way to derive tenant-local civil dates and
timezone-aware datetimes for AI features. It exists to eliminate
``date.today()`` drift, where server-local calendar math produces different
results than the tenant's configured timezone near UTC and DST boundaries.

Use these helpers when behavior is tenant-facing or depends on a tenant's
civil day, such as natural-language date parsing, reporting windows, anomaly
scan ranges, and forecast periods. Keep using raw UTC instants for absolute
elapsed-time arithmetic, logging timestamps, and other server-relative work.

Context:
- ``audit/ai-honesty-2026-06-10.md``
- ``audit/date-today-sweep-inventory.md``
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.timewindow import now_utc

logger = logging.getLogger(__name__)

_UTC = "UTC"


def _normalize_timezone(tz: str | None, *, context: str) -> str:
    if not tz:
        logger.warning("Missing tenant timezone for %s; falling back to UTC", context)
        return _UTC

    try:
        ZoneInfo(tz)
        return tz
    except ZoneInfoNotFoundError:
        logger.warning(
            "Invalid tenant timezone %r for %s; falling back to UTC",
            tz,
            context,
        )
        return _UTC


def get_today_in_tz(tz: str) -> date:
    """Return the civil date observed right now in the supplied IANA timezone."""
    return get_now_in_tz(tz).date()


def get_now_in_tz(tz: str) -> datetime:
    """Return a tz-aware current datetime in the supplied IANA timezone."""
    normalized_tz = _normalize_timezone(tz, context="sync timezone helper")
    return now_utc().astimezone(ZoneInfo(normalized_tz))


async def resolve_tenant_timezone(db: AsyncSession, company_id: int) -> str:
    """Resolve a company's configured IANA timezone, falling back to UTC."""
    from app.models import Company

    try:
        result = await db.execute(
            select(Company.timezone).where(Company.id == company_id)
        )
    except Exception:
        logger.warning(
            "Failed to resolve tenant timezone for company_id=%s; falling back to UTC",
            company_id,
            exc_info=True,
        )
        return _UTC

    timezone_name = result.scalar_one_or_none()
    if timezone_name is None:
        logger.warning(
            "Company %s not found or timezone is unset; falling back to UTC",
            company_id,
        )
        return _UTC

    return _normalize_timezone(timezone_name, context=f"company_id={company_id}")


async def resolve_tenant_timezone_for_user(db: AsyncSession, user_id: int) -> str:
    """Resolve a user's company timezone, falling back to UTC."""
    from app.models import User

    try:
        result = await db.execute(select(User.company_id).where(User.id == user_id))
    except Exception:
        logger.warning(
            "Failed to resolve tenant timezone for user_id=%s; falling back to UTC",
            user_id,
            exc_info=True,
        )
        return _UTC

    company_id = result.scalar_one_or_none()
    if company_id is None:
        logger.warning(
            "User %s not found or has no company; falling back to UTC",
            user_id,
        )
        return _UTC

    return await resolve_tenant_timezone(db, company_id)


async def get_tenant_today(db: AsyncSession, company_id: int) -> date:
    """Resolve company timezone and return its current civil date."""
    tenant_tz = await resolve_tenant_timezone(db, company_id)
    return get_today_in_tz(tenant_tz)


async def get_tenant_now(db: AsyncSession, company_id: int) -> datetime:
    """Resolve company timezone and return its current tz-aware datetime."""
    tenant_tz = await resolve_tenant_timezone(db, company_id)
    return get_now_in_tz(tenant_tz)


async def get_tenant_today_for_user(db: AsyncSession, user_id: int) -> date:
    """Resolve user company timezone and return its current civil date."""
    tenant_tz = await resolve_tenant_timezone_for_user(db, user_id)
    return get_today_in_tz(tenant_tz)