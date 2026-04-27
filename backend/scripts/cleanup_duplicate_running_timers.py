#!/usr/bin/env python3
"""
Cleanup script for duplicate running timers (audit finding B2).

Background:
    Until the partial-unique index ``ux_time_entries_one_running_per_user``
    was introduced, two simultaneous ``POST /time-entries/start`` calls
    could each pass the SELECT-then-INSERT pre-check and create
    overlapping running rows for the same user. This script detects and
    optionally closes those duplicates so the migration that creates
    the index can succeed.

Behavior:
    - Default mode is ``--dry-run`` (no writes). Running with no flags
      is safe.
    - In dry-run, lists every user_id with more than one running entry
      (``end_time IS NULL``) plus the entry IDs and start timestamps.
    - In ``--apply`` mode, keeps the most recent running entry per user
      (highest ``start_time``) and closes all others by setting
      ``end_time = start_time + 1 second`` and ``duration_seconds = 1``.
      Idempotent: a second ``--apply`` run on a clean DB is a no-op.

Usage:
    python scripts/cleanup_duplicate_running_timers.py            # dry-run
    python scripts/cleanup_duplicate_running_timers.py --dry-run  # explicit
    python scripts/cleanup_duplicate_running_timers.py --apply    # writes

Exit codes:
    0 - success (no duplicates, or all closed)
    1 - error during execution
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import timedelta
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("cleanup_duplicate_running_timers")


def _resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/time_tracker")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def _find_duplicates(db: AsyncSession) -> List[Tuple[int, int]]:
    """Return [(user_id, count), ...] for users with >1 running entries."""
    from app.models import TimeEntry

    result = await db.execute(
        select(TimeEntry.user_id, func.count(TimeEntry.id).label("n"))
        .where(TimeEntry.end_time.is_(None))
        .group_by(TimeEntry.user_id)
        .having(func.count(TimeEntry.id) > 1)
        .order_by(TimeEntry.user_id)
    )
    return [(row[0], row[1]) for row in result.all()]


async def _list_running_entries_for_user(db: AsyncSession, user_id: int):
    from app.models import TimeEntry

    result = await db.execute(
        select(TimeEntry)
        .where(TimeEntry.user_id == user_id, TimeEntry.end_time.is_(None))
        .order_by(TimeEntry.start_time.desc())
    )
    return list(result.scalars().all())


async def run(apply: bool) -> int:
    engine = create_async_engine(_resolve_database_url(), echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    mode = "APPLY" if apply else "DRY-RUN"
    logger.info("Starting duplicate-running-timer cleanup (%s mode)", mode)

    closed_total = 0
    affected_users = 0

    try:
        async with session_factory() as db:
            duplicates = await _find_duplicates(db)
            if not duplicates:
                logger.info("No users with duplicate running timers. Nothing to do.")
                return 0

            logger.info("Found %d user(s) with duplicate running timers:", len(duplicates))
            for user_id, count in duplicates:
                affected_users += 1
                entries = await _list_running_entries_for_user(db, user_id)
                logger.info(
                    "  user_id=%s running_count=%d entries=%s",
                    user_id,
                    count,
                    [
                        {"id": e.id, "start_time": e.start_time.isoformat() if e.start_time else None}
                        for e in entries
                    ],
                )

                if not apply:
                    continue

                # Keep the most recent (first after desc order). Close the rest.
                keeper = entries[0]
                losers = entries[1:]
                for entry in losers:
                    if entry.start_time is None:
                        # Defensive: should not happen for a running entry,
                        # but skip rather than corrupt data.
                        logger.warning(
                            "Skipping entry id=%s for user_id=%s (start_time is NULL)",
                            entry.id,
                            user_id,
                        )
                        continue
                    new_end = entry.start_time + timedelta(seconds=1)
                    entry.end_time = new_end
                    entry.duration_seconds = 1
                    entry.is_running = False
                    closed_total += 1
                    logger.info(
                        "  CLOSED entry id=%s user_id=%s start_time=%s end_time=%s "
                        "(kept running entry id=%s)",
                        entry.id,
                        user_id,
                        entry.start_time.isoformat(),
                        new_end.isoformat(),
                        keeper.id,
                    )

            if apply:
                await db.commit()
                logger.info(
                    "Cleanup complete: closed %d duplicate running entries across %d user(s).",
                    closed_total,
                    affected_users,
                )
            else:
                logger.info(
                    "Dry-run summary: %d user(s) affected, %d entries would be closed.",
                    affected_users,
                    sum(c - 1 for _, c in duplicates),
                )
        return 0
    except Exception:
        logger.exception("Cleanup failed")
        return 1
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="List duplicates without writing (default).")
    group.add_argument("--apply", action="store_true", help="Close duplicate running entries.")
    args = parser.parse_args()

    apply = bool(args.apply)
    return asyncio.run(run(apply=apply))


if __name__ == "__main__":
    sys.exit(main())
