#!/usr/bin/env python3
"""
4-hourly Basecamp auto-sync job.

Iterates every ``basecamp_credentials`` row with ``auto_sync_enabled=True``
and runs the same one-way project mirror that the manual
``POST /api/integrations/basecamp/sync`` endpoint runs.

Driven by the ``scheduler-4hourly`` container in
``docker-compose.prod.yml`` (sleep loop, 14400 seconds).

Behavior contract (also covered by tests):

* Only rows with ``auto_sync_enabled = TRUE`` are processed; everything
  else is silently skipped. Opt-in semantics.
* Each company's sync is wrapped in its own ``try/except`` so one
  failing tenant cannot prevent the others from syncing.
* ``main()`` swallows any top-level exception so the scheduler
  container's ``while true`` loop keeps running across crashes.
* The sync code itself is idempotent (re-running a clean sync produces
  ``unchanged`` results), so no separate idempotency stamp is needed
  for the 4-hourly cadence.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Optional

# Allow ``python scripts/sync_basecamp_projects.py``.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import BasecampCredentials
from app.services.basecamp_service import BasecampError, BasecampService

logger = logging.getLogger(__name__)


async def sync_all_enabled_companies(db: AsyncSession) -> dict:
    """Run the Basecamp -> TimeTracker project mirror for every company
    whose credentials have ``auto_sync_enabled=True``.

    Returns a summary dict::

        {
          "companies_processed": int,
          "companies_succeeded": int,
          "companies_failed": int,
          "errors": [{"company_id": int, "error": str}, ...],
          "results": [
            {
              "company_id": int,
              "created": int, "updated": int, "unchanged": int,
              "errors": [str, ...],
            }, ...
          ],
        }
    """
    result = await db.execute(
        select(BasecampCredentials).where(
            BasecampCredentials.auto_sync_enabled.is_(True)
        )
    )
    # Snapshot (id, company_id) pairs up-front: a per-company rollback
    # below would otherwise expire every ORM-loaded attribute, breaking
    # attribute access on subsequent iterations.
    creds_ids: list[tuple[int, int]] = [
        (c.id, c.company_id) for c in result.scalars().all()
    ]

    summary: dict = {
        "companies_processed": len(creds_ids),
        "companies_succeeded": 0,
        "companies_failed": 0,
        "errors": [],
        "results": [],
    }

    for creds_id, company_id in creds_ids:
        # Drop any cached identity-map state from a prior iteration so a
        # previous rollback's expired instance cannot trigger a sync
        # lazy-load on attribute access.
        db.expunge_all()
        creds = await db.get(BasecampCredentials, creds_id)
        if creds is None:
            # Row was deleted between snapshot and processing.
            continue
        try:
            report = await BasecampService.sync_projects_to_company(
                creds, company_id, db, dry_run=False
            )
            todo_report = await BasecampService.sync_todos_for_company(
                creds, company_id, db, dry_run=False
            )
            await db.commit()
            summary["companies_succeeded"] += 1
            summary["results"].append(
                {
                    "company_id": company_id,
                    "created": report.get("created", 0),
                    "updated": report.get("updated", 0),
                    "unchanged": report.get("unchanged", 0),
                    "errors": report.get("errors", []),
                    "todos_created": todo_report.get("todos_created", 0),
                    "todos_updated": todo_report.get("todos_updated", 0),
                    "todos_unchanged": todo_report.get("todos_unchanged", 0),
                    "todo_errors": todo_report.get("todo_errors", []),
                }
            )
            proj_errs = len(report.get("errors", []) or [])
            todo_errs = len(todo_report.get("todo_errors", []) or [])
            logger.info(
                "basecamp.autosync.company_done company_id=%s "
                "projects=(%s/%s/%s) todos=(%s/%s/%s) errors=%s",
                company_id,
                report.get("created", 0),
                report.get("updated", 0),
                report.get("unchanged", 0),
                todo_report.get("todos_created", 0),
                todo_report.get("todos_updated", 0),
                todo_report.get("todos_unchanged", 0),
                proj_errs + todo_errs,
            )
        except BasecampError as exc:
            await db.rollback()
            summary["companies_failed"] += 1
            summary["errors"].append(
                {"company_id": company_id, "error": str(exc)}
            )
            logger.exception(
                "basecamp.autosync.company_failed company_id=%s", company_id
            )
        except Exception as exc:  # noqa: BLE001 — never crash the loop
            await db.rollback()
            summary["companies_failed"] += 1
            summary["errors"].append(
                {"company_id": company_id, "error": str(exc)}
            )
            logger.exception(
                "basecamp.autosync.company_crashed company_id=%s", company_id
            )

    return summary


async def main() -> Optional[dict]:
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

    try:
        async with Session() as db:
            try:
                summary = await sync_all_enabled_companies(db)
                print(f"[basecamp-autosync] {summary}")
                return summary
            except Exception:
                logger.exception("basecamp autosync job crashed")
                # Do not re-raise: scheduler container must stay up.
                return None
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
