"""Add unique partial index: one running timer per user (B2)

Revision ID: 021_unique_running_timer
Revises: 020_mt_perf_indexes
Create Date: 2026-04-27

PURPOSE
-------
Audit finding B2: a SELECT-then-INSERT in ``POST /time-entries/start``
allowed two simultaneous requests for the same user to each create a
running ``TimeEntry`` row (``end_time IS NULL``). The handler-level
pre-check is racy; only a database constraint can serialize the
write.

This migration adds a UNIQUE PARTIAL INDEX on
``time_entries(user_id) WHERE end_time IS NULL`` so PostgreSQL refuses
the second concurrent insert. The handler now catches the resulting
``IntegrityError`` and returns HTTP 409.

SAFETY
------
Before creating the index, the migration scans for users that already
have multiple running entries. If any are found the migration ABORTS
with a clear error message naming the affected ``user_id`` values; it
does NOT delete or modify data. The operator must run
``backend/scripts/cleanup_duplicate_running_timers.py --apply`` first,
then re-run ``alembic upgrade head``.
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "021_unique_running_timer"
down_revision = "020_mt_perf_indexes"
branch_labels = None
depends_on = None


INDEX_NAME = "ux_time_entries_one_running_per_user"


def upgrade() -> None:
    bind = op.get_bind()

    # Pre-flight duplicate detection. Refuse to create the unique index
    # while existing rows would violate it; surface offending user_ids
    # so the operator can run the cleanup script.
    duplicates = bind.execute(
        sa.text(
            """
            SELECT user_id, COUNT(*) AS n
            FROM time_entries
            WHERE end_time IS NULL
            GROUP BY user_id
            HAVING COUNT(*) > 1
            ORDER BY user_id
            """
        )
    ).fetchall()

    if duplicates:
        affected = ", ".join(f"user_id={row[0]} ({row[1]} running)" for row in duplicates)
        raise RuntimeError(
            "Refusing to create unique partial index "
            f"{INDEX_NAME!r}: {len(duplicates)} user(s) currently have "
            "multiple running TimeEntry rows (end_time IS NULL). "
            f"Affected: {affected}. "
            "Run backend/scripts/cleanup_duplicate_running_timers.py --apply "
            "to close duplicates, then retry alembic upgrade."
        )

    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX {INDEX_NAME} "
            "ON time_entries (user_id) WHERE end_time IS NULL"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))
