"""Backfill empty time_entries.description from tasks.name

Revision ID: 029_backfill_time_entry_desc
Revises: 028_tasks_name_text
Create Date: 2026-05-27
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "029_backfill_time_entry_desc"
down_revision = "028_tasks_name_text"
branch_labels = None
depends_on = None


BACKFILL_SQL = """
UPDATE time_entries te
SET description = t.name
FROM tasks t
WHERE te.task_id = t.id
  AND te.task_id IS NOT NULL
  AND (
    te.description IS NULL
    OR btrim(te.description, E' \t\n\r') = ''
  )
"""


def upgrade() -> None:
    op.execute(BACKFILL_SQL)


def downgrade() -> None:
    # Data migration is intentionally irreversible without information loss:
    # once backfilled, we cannot distinguish generated values from user-entered
    # descriptions that coincidentally equal the task name.
    pass
