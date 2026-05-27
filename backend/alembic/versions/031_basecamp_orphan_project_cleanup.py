"""Delete orphan Basecamp-created projects from 2026-05-27 incident window.

Revision ID: 031_basecamp_orphan_cleanup
Revises: 030_bc_step_sync_nesting
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "031_basecamp_orphan_cleanup"
down_revision = "030_bc_step_sync_nesting"
branch_labels = None
depends_on = None


DELETE_ORPHAN_PROJECTS_SQL = """
DELETE FROM projects p
WHERE p.created_at >= '2026-05-27 00:00:00+00'
  AND p.created_at < '2026-05-28 00:00:00+00'
  AND NOT EXISTS (
    SELECT 1 FROM basecamp_project_mappings bpm
    WHERE bpm.internal_project_id = p.id
  )
  AND NOT EXISTS (
    SELECT 1 FROM tasks t WHERE t.project_id = p.id
  )
  AND NOT EXISTS (
    SELECT 1 FROM time_entries te WHERE te.project_id = p.id
  )
"""


def run_orphan_project_cleanup(connection: sa.Connection) -> None:
    connection.execute(sa.text(DELETE_ORPHAN_PROJECTS_SQL))


def upgrade() -> None:
    run_orphan_project_cleanup(op.get_bind())


def downgrade() -> None:
    # Data cleanup migration is intentionally irreversible.
    # Deleted project identities cannot be reconstructed safely.
    pass
